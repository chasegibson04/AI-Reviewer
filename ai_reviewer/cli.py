
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console, Group
from rich.live import Live
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ai_reviewer.benchmarks.runner import benchmark_models, write_benchmark_report
from ai_reviewer.config import load_config, write_example_local_config
from ai_reviewer.ingest.loaders import parse_file, parse_path_with_failures
from ai_reviewer.logging_utils import create_child_bundle, create_run_dir, configure_logging, write_run_metadata
from ai_reviewer.ops.locks import LockError, acquire_project_lock, release_project_lock
from ai_reviewer.models.base import ChatRequest, ProviderError
from ai_reviewer.models.diagnostics import run_diagnostics
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.models.selector import infer_model_roles, model_capability, split_chat_and_embedding_models
from ai_reviewer.orchestrator.controller import OrchestratorController
from ai_reviewer.projects.schema import EvaluationRecord, ProjectDefaults, RunRecord
from ai_reviewer.projects.store import ProjectError, ProjectStore
from ai_reviewer.review.compare import align_sections, detect_claim_changes
from ai_reviewer.review.deep_run import DeepRunError, run_deep_run
from ai_reviewer.review.docx_export import write_markdown_as_docx
from ai_reviewer.review.engine import run_compare, run_review
from ai_reviewer.review.citation_fetcher import fetch_citations_for_documents
from ai_reviewer.review.manuscript_annotation import build_annotated_manuscript_output
from ai_reviewer.review.evaluation import EVALUATION_PROFILES, run_published_paper_evaluation_sweep
from ai_reviewer.review.profiles import get_profile
from ai_reviewer.slack.adapter import build_result_summary, map_slack_command_to_workflow, save_result_summary, save_submission_record
from ai_reviewer.slack.models import SlackSubmission, SlackWorkflowRequest
from ai_reviewer.training.cache import TrainingCacheManager
from ai_reviewer.output_verifier import verify_deep_run, verify_evaluation_run, verify_review_run
from ai_reviewer.paths import REPO_ROOT
from ai_reviewer.tools.registry import ToolRegistry
from ai_reviewer.tools.smoke_tests import run_tool_smoke_tests

app = typer.Typer(help="AI-Reviewer: local-first review platform.", no_args_is_help=True)
project_app = typer.Typer(help="Project management")
slack_app = typer.Typer(help="Slack dev simulation")
training_app = typer.Typer(help="Global lab training materials")
tools_app = typer.Typer(help="Tooling availability and smoke tests")
app.add_typer(project_app, name="project")
app.add_typer(slack_app, name="slack-dev")
app.add_typer(training_app, name="training")
app.add_typer(tools_app, name="tools")
console = Console()

PROFILE_KEYS = ["quick", "balanced", "deep", "adversarial", "methods", "writing", "editor", "revision", "citation", "repro"]
CATEGORIES = [
    "manuscript_draft",
    "published_paper",
    "reviewer_comments",
    "supplemental_document",
    "style_guide",
    "journal_instructions",
    "reference_example",
    "methods_reference",
    "miscellaneous",
]


def _exit(msg: str, code: int = 1) -> None:
    console.print(f"[red]{msg}[/red]")
    raise typer.Exit(code)


def _store() -> ProjectStore:
    return ProjectStore(REPO_ROOT / "projects")


def _resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _project_or_exit(project: Optional[str]):
    try:
        return _store().get_project(project)
    except ProjectError as exc:
        _exit(str(exc))


def _provider_and_config(config_path: Optional[str], output_dir: Optional[Path], cmd: str, debug: bool = False):
    cfg = load_config(config_path)
    output_root = _resolve_repo_path(output_dir or Path(cfg.defaults.output_root))
    run_dir = create_run_dir(output_root, cmd)
    logger = configure_logging(run_dir, level=cfg.defaults.logging_level, debug_console=debug)
    provider = OllamaProvider(
        base_url=cfg.defaults.ollama_base_url,
        strict_offline=cfg.defaults.strict_offline,
        connect_timeout_seconds=cfg.timeouts.connect_seconds,
        chat_attempts=cfg.retries.chat_attempts,
        embed_attempts=cfg.retries.embed_attempts,
        base_backoff_seconds=cfg.retries.base_backoff_seconds,
        logger=logger,
    )
    if cfg.training.enabled and cfg.training.auto_sync_on_start:
        trainer = TrainingCacheManager.from_config(cfg, logger=logger)
        report = trainer.sync(force_rebuild=False)
        logger.info(
            "training_auto_sync added=%s changed=%s removed=%s unchanged=%s failed=%s active=%s",
            report.added,
            report.changed,
            report.removed,
            report.unchanged,
            report.failed,
            report.active_files,
        )
    return provider, cfg, run_dir, logger


def _project_scoped_root(project_id: str, scope: str) -> Path:
    pdir, _ = _store().get_project(project_id)
    root = pdir / scope
    root.mkdir(parents=True, exist_ok=True)
    return root


def _provider_for_workflow(
    config_path: Optional[str],
    output_dir: Optional[Path],
    cmd: str,
    debug: bool = False,
    project_id: Optional[str] = None,
    scope: str = "runs",
):
    if project_id:
        if output_dir is not None:
            console.print(
                "[yellow]Ignoring --output-dir for project-scoped run; using project-local storage.[/yellow]"
            )
        project_root = _project_scoped_root(project_id, scope)
        return _provider_and_config(config_path, project_root, cmd, debug)
    return _provider_and_config(config_path, output_dir, cmd, debug)


def _build_orchestrator(cfg, provider, logger) -> OrchestratorController:
    orch = OrchestratorController(
        provider=provider,
        model=cfg.orchestrator.model,
        temperature=cfg.orchestrator.temperature,
        require_json=cfg.orchestrator.require_json,
        fail_open=cfg.orchestrator.fail_open,
        enabled=cfg.orchestrator.enabled,
    )
    logger.info(
        "orchestrator_init enabled=%s model=%s max_stage_retries=%s max_total_retries=%s fail_open=%s",
        cfg.orchestrator.enabled,
        cfg.orchestrator.model,
        cfg.orchestrator.max_stage_retries,
        cfg.orchestrator.max_total_retries,
        cfg.orchestrator.fail_open,
    )
    return orch


def _resolve_run_output(project_id: str, output_dir: str, run_id: str) -> Path:
    candidate = Path(output_dir)
    if candidate.exists():
        return candidate.resolve()
    pdir, _ = _store().get_project(project_id)
    for alt in [pdir / "runs" / run_id, pdir / "evaluations" / run_id, REPO_ROOT / "outputs" / run_id]:
        if alt.exists():
            return alt.resolve()
    return candidate


def _model_table(installed: list[str], cfg):
    chat, emb = split_chat_and_embedding_models(installed)
    roles = infer_model_roles(installed, cfg)
    table = Table(title="Detected Ollama Models")
    table.add_column("Model")
    table.add_column("Type")
    table.add_column("Size")
    table.add_column("Recommendation")
    for model in chat:
        cap = model_capability(model)
        rec = []
        if model == roles.balanced_model:
            rec.append("default balanced")
        if model == roles.deep_model:
            rec.append("default deep")
        if model in roles.repair_candidates:
            rec.append("repair")
        if model == "gemma2:27b":
            rec.append("legacy")
        model_type = "multimodal" if cap.kind == "multimodal" else "chat"
        table.add_row(model, model_type, cap.size_hint, ", ".join(rec))
    for model in emb:
        cap = model_capability(model)
        rec = "default" if model == roles.embedding_model else ("fallback" if model == roles.embedding_fallback else "")
        table.add_row(model, "embedding", cap.size_hint, rec)
    console.print(table)
    return chat, emb, roles


def _record_run(project_id: str | None, run_dir: Path, workflow: str, profile: str | None, model: str | None, embedding: str | None, status: str, settings: dict, warning_count: int = 0) -> None:
    if not project_id:
        return
    _store().add_run_record(
        project_id,
        RunRecord(
            run_id=run_dir.name,
            workflow=workflow,
            status=status,
            profile=profile,
            model=model,
            embedding_model=embedding,
            output_dir=str(run_dir.resolve()),
            settings=settings,
            warning_count=warning_count,
        ),
    )


def _print_run_outcome(title: str, run_dir: Path, key_files: list[Path], verified: bool, issues: list[str] | None = None) -> None:
    resolved = run_dir.resolve()
    lines = [f"[bold]{title}[/bold]", f"Run directory: {resolved}"]
    if key_files:
        lines.append("Key files:")
        for path in key_files[:8]:
            lines.append(f"- {path.resolve()}")
    if verified:
        lines.append("[green]Output verification: passed[/green]")
    else:
        lines.append("[red]Output verification: failed[/red]")
        for issue in issues or []:
            lines.append(f"- {issue}")
    console.print(Panel.fit("\n".join(lines), title="Run Summary"))


def _resolve_docs(input_path: Optional[Path], project: Optional[str], material_ids: Optional[str]):
    docs = []
    supporting_docs = []
    failures = []
    project_id = None
    if project:
        store = _store()
        pdir, meta = store.get_project(project)
        store.sync_project_material_inventory(meta.project_id)
        pdir, meta = store.get_project(meta.project_id)
        project_id = meta.project_id
        mids = [x.strip() for x in material_ids.split(",")] if material_ids else None
        if mids:
            selected = [m for m in meta.materials if m.material_id in set(mids)]
            support = []
        else:
            manuscripts = [m for m in meta.materials if m.category == "manuscript_draft"]
            if manuscripts:
                selected = manuscripts
                support = [m for m in meta.materials if m.category != "manuscript_draft"]
            else:
                selected = []
                support = [m for m in meta.materials if m.category != "manuscript_draft"]

        for material in selected:
            src = store.material_path(pdir, material)
            if not src.exists():
                failures.append({"source": str(src), "error": "Material file not found."})
                continue
            try:
                docs.append(parse_file(src))
            except Exception as exc:
                failures.append({"source": str(src), "error": str(exc)})
        for material in support:
            src = store.material_path(pdir, material)
            if not src.exists():
                failures.append({"source": str(src), "error": "Supporting material file not found."})
                continue
            try:
                supporting_docs.append(parse_file(src))
            except Exception as exc:
                failures.append({"source": str(src), "error": f"Supporting parse failed: {exc}"})
    else:
        assert input_path is not None
        if not input_path.exists():
            _exit(f"Input path not found: {input_path}")
        docs, parse_failures = parse_path_with_failures(input_path, continue_on_error=True)
        failures.extend([f.__dict__ for f in parse_failures])
    return docs, supporting_docs, failures, project_id


def _training_injection(cfg, logger, profile_key: str, disable_training_guidance: bool):
    if disable_training_guidance or not cfg.training.enabled or not cfg.training.inject_by_default:
        return None, []
    trainer = TrainingCacheManager.from_config(cfg, logger=logger)
    injection = trainer.injection_for_profile(profile_key, max_chars=cfg.training.max_injection_chars)
    if injection.enabled:
        logger.info(
            "training_injection enabled categories=%s source_count=%s",
            ",".join(injection.categories_used),
            injection.source_count,
        )
        return injection.prompt_block, injection.categories_used
    logger.info("training_injection disabled reason=no_active_guidance")
    return None, []


@app.command("list-models")
def list_models(config_path: Optional[str] = typer.Option(None)):
    provider, cfg, run_dir, logger = _provider_and_config(config_path, None, "list_models")
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    chat, emb, _ = _model_table(installed, cfg)
    write_run_metadata(run_dir, {"command": "list-models", "chat": chat, "embedding": emb})
    logger.info("list-models complete")


@app.command("diagnose")
def diagnose(config_path: Optional[str] = typer.Option(None), output_dir: Optional[Path] = typer.Option(None)):
    provider, cfg, run_dir, logger = _provider_and_config(config_path, output_dir, "diagnose")
    report = run_diagnostics(provider, cfg, run_dir.parent)
    table = Table(title="Diagnostics")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for item in report.items:
        table.add_row(item.name, item.status, item.detail)
    trainer = TrainingCacheManager.from_config(cfg, logger=logger)
    t_status = trainer.status()
    table.add_row("training_enabled", "checked" if cfg.training.enabled else "warning", str(cfg.training.enabled))
    table.add_row("training_tracked_files", "checked", str(t_status["tracked_files"]))
    table.add_row("training_active_guidance_files", "checked", str(t_status["active_guidance_files"]))
    if t_status.get("parse_failures", 0) > 0:
        table.add_row("training_parse_failures", "warning", str(t_status["parse_failures"]))
    tool_avail = ToolRegistry(cfg).availability()
    missing_required = [name for name, meta in tool_avail.items() if (not meta["optional"] and not meta["installed"])]
    table.add_row("tools_installed", "checked", str(sum(1 for _, x in tool_avail.items() if x["installed"])))
    table.add_row("tools_required_missing", "error" if missing_required else "checked", ",".join(missing_required) if missing_required else "none")
    console.print(table)
    write_run_metadata(run_dir, {"command": "diagnose", "ok": report.ok, "items": [i.__dict__ for i in report.items]})
    logger.info("diagnose ok=%s", report.ok)
    if not report.ok:
        raise typer.Exit(2)


@app.command("doctor")
def doctor(config_path: Optional[str] = typer.Option(None), output_dir: Optional[Path] = typer.Option(None), apply_safe_fixes: bool = typer.Option(False)):
    provider, cfg, run_dir, logger = _provider_and_config(config_path, output_dir, "doctor")
    report = run_diagnostics(provider, cfg, run_dir.parent)
    fixes = []
    for item in report.items:
        if item.status == "checked":
            continue
        fixes.append({"check": item.name, "status": "manual", "fix": item.detail})
    if apply_safe_fixes:
        cfg_path = Path("config/local.yaml")
        if not cfg_path.exists():
            write_example_local_config(cfg_path)
            fixes.append({"check": "config/local.yaml", "status": "fixed", "fix": "Created local config template."})
    for fix in fixes:
        console.print(f"{fix['status']}: {fix['check']} -> {fix['fix']}")
    (run_dir / "artifacts" / "doctor_report.json").write_text(json.dumps(fixes, indent=2), encoding="utf-8")
    logger.info("doctor complete")


@app.command("ingest")
def ingest(input_path: Path = typer.Argument(...), output_dir: Optional[Path] = typer.Option(None), config_path: Optional[str] = typer.Option(None), continue_on_error: bool = typer.Option(True)):
    if not input_path.exists():
        _exit(f"Input path not found: {input_path}")
    _, _, run_dir, logger = _provider_and_config(config_path, output_dir, "ingest")
    docs, failures = parse_path_with_failures(input_path, continue_on_error=continue_on_error)
    payload = [{"source": str(d.source_path), "type": d.document_type, "warnings": d.parse_warnings} for d in docs]
    (run_dir / "artifacts" / "ingest_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (run_dir / "artifacts" / "ingest_failures.json").write_text(json.dumps([f.__dict__ for f in failures], indent=2, default=str), encoding="utf-8")
    write_run_metadata(run_dir, {"command": "ingest", "count": len(docs), "failures": len(failures)})
    logger.info("ingest complete docs=%s failures=%s", len(docs), len(failures))
    console.print(f"Ingested {len(docs)} documents. Output: {run_dir.resolve()}")

@app.command("review")
def review(
    input_path: Optional[Path] = typer.Argument(None),
    profile: str = typer.Option("balanced"),
    model: Optional[str] = typer.Option(None),
    embedding_model: Optional[str] = typer.Option(None),
    disable_embeddings: bool = typer.Option(False),
    strict_schema: Optional[bool] = typer.Option(None),
    output_dir: Optional[Path] = typer.Option(None),
    config_path: Optional[str] = typer.Option(None),
    keep_raw: Optional[bool] = typer.Option(None),
    continue_on_error: bool = typer.Option(True),
    project: Optional[str] = typer.Option(None),
    material_ids: Optional[str] = typer.Option(None),
    debug: bool = typer.Option(False),
    disable_training_guidance: bool = typer.Option(False, help="Disable global training-material guidance injection."),
):
    if input_path is None and project is None:
        _exit("Provide INPUT_PATH or --project")
    provider, cfg, run_dir, logger = _provider_for_workflow(
        config_path=config_path,
        output_dir=output_dir,
        cmd="review",
        debug=debug,
        project_id=project,
        scope="runs",
    )
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    chat, emb, roles = _model_table(installed, cfg)

    prof = get_profile(profile)
    selected_model = model or (roles.deep_model if profile == "deep" else roles.balanced_model)
    if selected_model not in chat:
        _exit(f"Model not installed: {selected_model}")

    selected_embed = None
    if not disable_embeddings and prof.use_retrieval and cfg.retrieval.enabled:
        selected_embed = embedding_model or roles.embedding_model
        if selected_embed and selected_embed not in emb:
            selected_embed = None

    if keep_raw is not None:
        cfg.defaults.keep_raw_outputs = keep_raw

    provider.chat(
        ChatRequest(
            model=selected_model,
            system_prompt="json",
            user_prompt='{"ok":true}',
            max_tokens=64,
            timeout_seconds=cfg.timeouts.chat_seconds,
        )
    )

    docs, supporting_docs, failures, project_id = _resolve_docs(input_path, project, material_ids)
    if not docs:
        if project:
            _exit(
                "No parseable manuscript docs found for project. Add a file under "
                "`projects/<project_id>/materials/manuscript` (primary target), or provide explicit "
                "`--material-ids` for a non-manuscript target."
            )
        _exit("No parseable docs")
    lock_info = None
    project_root = None
    if project_id and cfg.concurrency.enable_project_locks:
        project_root, _ = _store().get_project(project_id)
        try:
            lock_info = acquire_project_lock(
                project_root=project_root,
                run_id=run_dir.name,
                allow_same_project=cfg.concurrency.allow_same_project_concurrency,
                ttl_seconds=cfg.concurrency.lock_ttl_seconds,
            )
            (run_dir / "artifacts" / "lock_info.json").write_text(
                json.dumps(
                    {"lock_path": str(lock_info.path), "acquired": lock_info.acquired, "metadata": lock_info.metadata},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except LockError as exc:
            _exit(str(exc))
    elif project_id:
        project_root, _ = _store().get_project(project_id)

    if project_id and project_root:
        fetch_citations_for_documents(docs, project_root, cfg, logger, run_dir=run_dir)

    guidance_text, guidance_categories = _training_injection(cfg, logger, prof.key, disable_training_guidance)
    orchestrator = _build_orchestrator(cfg, provider, logger)

    results = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=36),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )
    status = {"line": "Starting review pipeline..."}
    main_task_desc = "Reviewing documents"
    try:
        with Live(console=console, auto_refresh=True, refresh_per_second=8) as live:
            progress.start()
            task_id = progress.add_task(main_task_desc, total=len(docs))
            for idx, doc in enumerate(docs, start=1):
                status["line"] = f"[{idx}/{len(docs)}] Preparing {doc.source_path.name}"
                live.update(Group(Panel(status["line"], title="Status"), progress))
                try:
                    bundle = create_child_bundle(run_dir, doc.source_path.stem, idx)

                    def _status_hook(step: str):
                        status["line"] = f"[{idx}/{len(docs)}] {doc.source_path.name}: {step}"
                        live.update(Group(Panel(status["line"], title="Status"), progress))

                    review_result = run_review(
                        provider=provider,
                        doc=doc,
                        profile=prof,
                        model=selected_model,
                        repair_models=roles.repair_candidates,
                        config=cfg,
                        bundle_dir=bundle,
                        embedding_model=selected_embed,
                        strict_schema_override=strict_schema,
                        logger=logger,
                        guidance_text=guidance_text,
                        guidance_categories=guidance_categories,
                        status_hook=_status_hook,
                        supporting_docs=supporting_docs,
                        orchestrator=orchestrator,
                    )
                    annotation = build_annotated_manuscript_output(
                        source_path=doc.source_path_abs,
                        doc=doc,
                        review=review_result.review,
                        output_dir=bundle,
                        project_id=project_id,
                        run_id=run_dir.name,
                        provider=provider,
                        model=selected_model,
                        timeout_seconds=cfg.timeouts.chat_seconds,
                    )
                    (bundle / "manuscript_comment_manifest.json").write_text(json.dumps(annotation, indent=2), encoding="utf-8")
                    if isinstance(annotation.get("section_map"), list):
                        (bundle / "section_map.json").write_text(
                            json.dumps(annotation.get("section_map"), indent=2),
                            encoding="utf-8",
                        )
                    source_mode_payload = annotation.get("source_mode_artifact", {})
                    if isinstance(source_mode_payload, dict):
                        source_mode_payload["project_id"] = project_id
                        (bundle / "source_mode.json").write_text(json.dumps(source_mode_payload, indent=2), encoding="utf-8")
                    validation_payload = annotation.get("validation", {})
                    if isinstance(validation_payload, dict):
                        (bundle / "commented_docx_validation.json").write_text(
                            json.dumps(validation_payload, indent=2),
                            encoding="utf-8",
                        )
                    results.append({"source": str(doc.source_path), "bundle": str(bundle), "warnings": len(review_result.warnings)})
                except Exception as exc:
                    failures.append({"source": str(doc.source_path), "error": str(exc)})
                    logger.exception("review failed for %s", doc.source_path)
                    status["line"] = f"[{idx}/{len(docs)}] FAILED {doc.source_path.name}: {exc}"
                    live.update(Group(Panel(status["line"], title="Status"), progress))
                    if not continue_on_error:
                        break
                finally:
                    progress.advance(task_id, 1)
                    live.update(Group(Panel(status["line"], title="Status"), progress))
            progress.stop()
    finally:
        if lock_info:
            try:
                release_project_lock(lock_info)
            except LockError:
                logger.warning("lock_release_failed run_id=%s lock=%s", run_dir.name, lock_info.path)

    summary = {
        "command": "review",
        "project_id": project_id,
        "profile": profile,
        "model": selected_model,
        "embedding_model": selected_embed,
        "processed": len(results),
        "failures": len(failures),
        "supporting_context_docs": len(supporting_docs),
        "results": results,
        "errors": failures,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "guidance_injected": bool(guidance_text),
        "guidance_categories": guidance_categories,
    }
    (run_dir / "artifacts" / "batch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_run_metadata(run_dir, summary)
    verification = verify_review_run(run_dir)
    status = "success" if not failures else "partial"
    if not verification.ok:
        status = "failed"
    _record_run(
        project_id,
        run_dir,
        "review",
        profile,
        selected_model,
        selected_embed,
        status,
        {"material_ids": material_ids, "strict_schema": strict_schema, "verification_issues": verification.issues},
        sum(int(r.get("warnings", 0)) for r in results),
    )
    _print_run_outcome("Review complete", run_dir, verification.key_files, verification.ok, verification.issues)
    if not verification.ok:
        _exit("Review finished but output verification failed. See debug.log and listed issues.")


@app.command("compare")
def compare(
    old_draft: Path = typer.Argument(...),
    new_draft: Path = typer.Argument(...),
    model: Optional[str] = typer.Option(None),
    output_dir: Optional[Path] = typer.Option(None),
    config_path: Optional[str] = typer.Option(None),
    project: Optional[str] = typer.Option(None),
    disable_training_guidance: bool = typer.Option(False),
):
    if not old_draft.exists() or not new_draft.exists():
        _exit("Both old and new draft paths must exist.")
    provider, cfg, run_dir, logger = _provider_for_workflow(
        config_path=config_path,
        output_dir=output_dir,
        cmd="compare",
        project_id=project,
        scope="runs",
    )
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    chat, _, roles = _model_table(installed, cfg)
    selected_model = model or roles.balanced_model
    if selected_model not in chat:
        _exit(f"Model not installed: {selected_model}")

    old_doc = parse_file(old_draft)
    new_doc = parse_file(new_draft)
    alignment = align_sections(old_doc, new_doc)
    added_claims, removed_claims, changed_claims = detect_claim_changes(old_doc, new_doc)
    guidance_text, guidance_categories = _training_injection(cfg, logger, "revision", disable_training_guidance)

    cmp = run_compare(
        provider=provider,
        old_text=old_doc.cleaned_text,
        new_text=new_doc.cleaned_text,
        model=selected_model,
        profile_prompt="revision comparison with unresolved issues and regressions",
        timeout_seconds=cfg.timeouts.chat_seconds,
        max_old_chars=cfg.compare.max_old_chars,
        max_new_chars=cfg.compare.max_new_chars,
        logger=logger,
        guidance_text=guidance_text,
    )
    payload = cmp.model_dump()
    payload["section_alignment"] = [{"old": o, "new": n, "score": s} for o, n, s in alignment]
    payload["heuristic_claim_changes"] = {
        "added_claims": added_claims,
        "removed_claims": removed_claims,
        "changed_claims": changed_claims,
    }
    (run_dir / "artifacts" / "compare.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    compare_md = (
        "# Revision Comparison\n\n"
        f"## Major Revisions\n{chr(10).join(f'- {x}' for x in cmp.summary_of_major_revisions) or '- None'}\n\n"
        f"## Unresolved Issues\n{chr(10).join(f'- {x}' for x in cmp.unresolved_issues) or '- None'}\n\n"
        f"## Regressions\n{chr(10).join(f'- {x}' for x in cmp.regressions) or '- None'}\n\n"
        f"## Response To Reviewers Bullets\n{chr(10).join(f'- {x}' for x in cmp.response_to_reviewers_bullets) or '- None'}\n",
    )
    (run_dir / "reports" / "compare.md").write_text(compare_md, encoding="utf-8")
    write_markdown_as_docx(compare_md, run_dir / "reports" / "compare.docx")
    write_run_metadata(
        run_dir,
        {
            "command": "compare",
            "model": selected_model,
            "old_draft": str(old_draft),
            "new_draft": str(new_draft),
            "added_claims": len(added_claims),
            "removed_claims": len(removed_claims),
            "changed_claims": len(changed_claims),
            "guidance_injected": bool(guidance_text),
            "guidance_categories": guidance_categories,
        },
    )
    _record_run(project, run_dir, "compare", "revision", selected_model, None, "success", {})
    console.print(f"Compare complete: {run_dir.resolve()}")


@app.command("evaluate-paper")
def evaluate_paper(
    anchor_paper: Path = typer.Argument(...),
    project: Optional[str] = typer.Option(None),
    model: Optional[str] = typer.Option(None),
    embedding_model: Optional[str] = typer.Option(None),
    profiles: Optional[str] = typer.Option(None, help="Comma-separated profile keys."),
    output_dir: Optional[Path] = typer.Option(None),
    config_path: Optional[str] = typer.Option(None),
    disable_training_guidance: bool = typer.Option(False),
):
    if not anchor_paper.exists():
        _exit(f"Anchor paper not found: {anchor_paper}")
    provider, cfg, run_dir, logger = _provider_for_workflow(
        config_path=config_path,
        output_dir=output_dir,
        cmd="evaluate_paper",
        project_id=project,
        scope="evaluations",
    )
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    chat, emb, roles = _model_table(installed, cfg)

    selected_model = model or roles.deep_model or roles.balanced_model
    if selected_model not in chat:
        _exit(f"Model not installed: {selected_model}")
    selected_embed = embedding_model or roles.embedding_model
    if selected_embed not in emb:
        selected_embed = None
    requested_profiles = [p.strip() for p in profiles.split(",")] if profiles else list(EVALUATION_PROFILES)

    def _guidance_getter(profile_key: str):
        return _training_injection(cfg, logger, profile_key, disable_training_guidance)
    orchestrator = _build_orchestrator(cfg, provider, logger)

    result = run_published_paper_evaluation_sweep(
        provider=provider,
        config=cfg,
        logger=logger,
        run_id=run_dir.name,
        anchor_path=anchor_paper,
        output_dir=run_dir,
        model=selected_model,
        embedding_model=selected_embed,
        repair_models=roles.repair_candidates,
        profiles=requested_profiles,
        guidance_getter=_guidance_getter,
        orchestrator=orchestrator,
    )
    write_run_metadata(
        run_dir,
        {
            "command": "evaluate-paper",
            "run_id": result.run_id,
            "profiles": requested_profiles,
            "model": selected_model,
            "embedding_model": selected_embed,
            "warnings": result.warnings,
            "workflow_count": len(result.per_profile_outputs),
        },
    )
    verification = verify_evaluation_run(run_dir)
    status = "success" if verification.ok else "failed"
    if project:
        _record_run(
            project,
            run_dir,
            "evaluate-paper",
            "multi",
            selected_model,
            selected_embed,
            status,
            {"profiles": requested_profiles, "verification_issues": verification.issues},
        )
        _store().add_evaluation_record(
            project,
            EvaluationRecord(
                evaluation_id=run_dir.name,
                anchor_material_id="external_anchor",
                run_id=run_dir.name,
                profiles=requested_profiles,
                output_dir=str(run_dir.resolve()),
            ),
        )
    _print_run_outcome("Evaluation sweep complete", run_dir, verification.key_files, verification.ok, verification.issues)
    if not verification.ok:
        _exit("Evaluation sweep finished but output verification failed. See debug.log and listed issues.")


@app.command("deep-run")
def deep_run_cmd(
    project: str = typer.Option(..., help="Project id/name/slug"),
    manuscript_id: Optional[str] = typer.Option(None),
    output_dir: Optional[Path] = typer.Option(None),
    config_path: Optional[str] = typer.Option(None),
    embedding_model: Optional[str] = typer.Option(None),
    disable_training_guidance: bool = typer.Option(False),
):
    provider, cfg, run_dir, logger = _provider_for_workflow(
        config_path=config_path,
        output_dir=output_dir,
        cmd="deep_run",
        project_id=project,
        scope="runs",
    )
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    _, emb, roles = _model_table(installed, cfg)
    selected_embed = embedding_model or roles.embedding_model
    if selected_embed not in emb:
        selected_embed = None
    lock_info = None
    if cfg.concurrency.enable_project_locks:
        pdir, _ = _store().get_project(project)
        try:
            lock_info = acquire_project_lock(
                project_root=pdir,
                run_id=run_dir.name,
                allow_same_project=cfg.concurrency.allow_same_project_concurrency,
                ttl_seconds=cfg.concurrency.lock_ttl_seconds,
            )
            (run_dir / "artifacts" / "lock_info.json").write_text(
                json.dumps(
                    {"lock_path": str(lock_info.path), "acquired": lock_info.acquired, "metadata": lock_info.metadata},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except LockError as exc:
            _exit(str(exc))
    else:
        pdir, _ = _store().get_project(project)

    docs, _, _, _ = _resolve_docs(None, project, manuscript_id)
    fetch_citations_for_documents(docs, pdir, cfg, logger, run_dir=run_dir)
    store = _store()
    try:
        orchestrator = _build_orchestrator(cfg, provider, logger)
        result = run_deep_run(
            provider=provider,
            cfg=cfg,
            logger=logger,
            run_dir=run_dir,
            project_id=project,
            store=store,
            manuscript_id=manuscript_id,
            embedding_model=selected_embed,
            disable_training_guidance=disable_training_guidance,
            orchestrator=orchestrator,
        )
    except DeepRunError as exc:
        _exit(str(exc))
    except Exception as exc:
        logger.exception("deep_run_failed")
        _exit(f"Deep run failed: {exc}")
    finally:
        if lock_info:
            try:
                release_project_lock(lock_info)
            except LockError:
                logger.warning("lock_release_failed run_id=%s lock=%s", run_dir.name, lock_info.path)

    verification = verify_deep_run(run_dir)
    status = result.status if verification.ok else "failed"
    _record_run(
        project,
        run_dir,
        "deep-run",
        "deep",
        None,
        selected_embed,
        status,
        {"manuscript_id": manuscript_id, "verification_issues": verification.issues},
        warning_count=len(result.warnings),
    )
    _print_run_outcome("Deep run complete", result.run_dir, verification.key_files, verification.ok, verification.issues)
    if not verification.ok:
        _exit("Deep run finished but output verification failed. See debug.log and listed issues.")

@app.command("test-models")
def test_models(
    models: Optional[str] = typer.Option(None),
    output_dir: Optional[Path] = typer.Option(None),
    config_path: Optional[str] = typer.Option(None),
    include_embeddings: bool = typer.Option(True),
):
    provider, cfg, run_dir, logger = _provider_and_config(config_path, output_dir, "test_models")
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    chat, emb, _ = _model_table(installed, cfg)
    selected = [m.strip() for m in models.split(",")] if models else chat
    selected = [m for m in selected if m in chat]

    rows = []
    for model in selected:
        status = "pass"
        detail = "ok"
        repair_needed = False
        latency = 0.0
        try:
            start = datetime.now(timezone.utc)
            response = provider.chat(
                ChatRequest(
                    model=model,
                    system_prompt="Return strict JSON only",
                    user_prompt='{"document_metadata":{"title":"T"},"summary":"ok","major_strengths":["a"],"major_weaknesses":["b"],"novelty_concerns":[],"methodological_concerns":[],"statistical_concerns":[],"writing_organization_concerns":[],"figure_table_concerns":[],"citation_reference_concerns":[],"reproducibility_concerns":[],"suggested_experiments_analyses":[],"recommendation":{"decision":"revise","rationale":"r"},"confidence":0.5,"detailed_reviewer_comments":["c"],"section_specific_comments":[],"extracted_action_items":[],"model_debug_metadata":{"provider":"ollama","model":"x","temperature":0.1,"parse_failures":0}}',
                    temperature=0.1,
                    timeout_seconds=cfg.timeouts.chat_seconds,
                )
            )
            latency = (datetime.now(timezone.utc) - start).total_seconds()
            repair_needed = "```" in response.content
        except Exception as exc:
            status = "fail"
            detail = str(exc)
        rows.append({"model": model, "status": status, "latency": latency, "repair_needed": repair_needed, "detail": detail})

    embed_rows = []
    if include_embeddings:
        for model in emb:
            try:
                provider.embed("embedding smoke text", model, timeout_seconds=cfg.timeouts.embed_seconds)
                embed_rows.append({"model": model, "status": "pass"})
            except Exception as exc:
                embed_rows.append({"model": model, "status": "fail", "detail": str(exc)})

    out = {"chat_tests": rows, "embedding_tests": embed_rows, "timestamp": datetime.now(timezone.utc).isoformat()}
    (run_dir / "artifacts" / "model_tests.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    write_run_metadata(run_dir, {"command": "test-models", "chat": len(rows), "embedding": len(embed_rows)})
    table = Table(title="Model Tests")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Latency")
    table.add_column("Repair?")
    for row in rows:
        table.add_row(row["model"], row["status"], f"{row['latency']:.2f}s", "yes" if row["repair_needed"] else "no")
    console.print(table)
    console.print(f"Saved: {run_dir.resolve()}")


@app.command("benchmark")
def benchmark(models: Optional[str] = typer.Option(None), output_dir: Optional[Path] = typer.Option(None), config_path: Optional[str] = typer.Option(None)):
    provider, cfg, run_dir, logger = _provider_and_config(config_path, output_dir, "benchmark")
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    chat, _, roles = _model_table(installed, cfg)
    selected = [m.strip() for m in models.split(",")] if models else chat[: cfg.benchmark.max_models]
    selected = [m for m in selected if m in chat]
    if not selected:
        _exit("No benchmark models selected.")
    results = benchmark_models(
        provider=provider,
        models=selected,
        short_fixture=Path(cfg.benchmark.short_fixture),
        long_fixture=Path(cfg.benchmark.long_fixture),
        malformed_fixture=Path(cfg.benchmark.malformed_fixture),
        repair_models=roles.repair_candidates,
        timeout_seconds=cfg.timeouts.chat_seconds,
        logger=logger,
    )
    write_benchmark_report(run_dir / "artifacts" / "benchmark_summary.json", results)
    write_run_metadata(run_dir, {"command": "benchmark", "models": selected, "count": len(results)})
    table = Table(title="Benchmark Results")
    table.add_column("Model")
    table.add_column("Success")
    table.add_column("Latency")
    table.add_column("Structured")
    table.add_column("Repair")
    table.add_column("Completeness")
    table.add_column("Tag")
    for r in results:
        table.add_row(r.model, "yes" if r.success else "no", f"{r.latency_seconds:.2f}s", "pass" if r.structured_pass else "fail", "yes" if r.repair_needed else "no", f"{r.completeness_score:.2f}", r.recommendation_tag)
    console.print(table)
    console.print(f"Benchmark complete: {run_dir.resolve()}")


def _interactive_project_select() -> Optional[str]:
    store = _store()
    projects = store.list_projects()
    if not projects:
        return None
    table = Table(title="Projects")
    table.add_column("#")
    table.add_column("Project")
    table.add_column("Materials")
    table.add_column("Runs")
    for i, (_, meta) in enumerate(projects, start=1):
        table.add_row(str(i), f"{meta.name} ({meta.project_id})", str(len(meta.materials)), str(len(meta.runs)))
    console.print(table)
    raw = Prompt.ask("Select project number or 'new'", default="1")
    if raw.lower() == "new":
        return None
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(projects):
            return projects[idx][1].project_id
    except Exception:
        pass
    return projects[0][1].project_id


@app.command("launch")
def launch(config_path: Optional[str] = typer.Option(None), output_dir: Optional[Path] = typer.Option(None)):
    console.print(Panel.fit("[bold cyan]AI-Reviewer[/bold cyan]\nProject-first, local-only paper review workflow.\nDefault mode keeps data local and uses Ollama models.", title="Welcome"))
    provider, cfg, _, _ = _provider_and_config(config_path, output_dir, "launch")
    ok, msg = provider.health()
    if not ok:
        _exit(msg)
    installed = provider.list_models()
    chat, emb, roles = _model_table(installed, cfg)
    if cfg.training.enabled:
        trainer = TrainingCacheManager.from_config(cfg)
        t_sync = trainer.sync(force_rebuild=False)
        console.print(
            f"Training materials synced: {t_sync.added} new, {t_sync.changed} changed, "
            f"{t_sync.removed} removed, {t_sync.unchanged} unchanged."
        )
        t_status = trainer.status()
        console.print(
            f"Training guidance active: {t_status['active_guidance_files']} files "
            f"across {len(t_status['files_by_category'])} categories."
        )

    selected_project = _interactive_project_select()
    store = _store()
    if not selected_project:
        name = Prompt.ask("New project name")
        desc = Prompt.ask("Description", default="")
        pdir, meta = store.create_project(
            name=name,
            description=desc,
            tags=[],
            defaults=ProjectDefaults(
                review_model=roles.balanced_model,
                embedding_model=roles.embedding_model,
                profile=cfg.defaults.default_profile,
                strict_schema=cfg.defaults.strict_schema,
                retrieval_enabled=cfg.retrieval.enabled,
                keep_raw_outputs=cfg.defaults.keep_raw_outputs,
            ),
        )
        selected_project = meta.project_id
        console.print(f"Created project: {meta.name} ({meta.project_id}) at {pdir}")
    pdir, pmeta = store.get_project(selected_project)
    added_manual, changed_manual, removed_manual = store.sync_project_material_inventory(selected_project)
    if any([added_manual, changed_manual, removed_manual]):
        console.print(
            f"Project material sync: {added_manual} new, {changed_manual} changed, {removed_manual} removed from manuscript/other."
        )
        pdir, pmeta = store.get_project(selected_project)

    if Confirm.ask("Add new material now?", default=True):
        src = Path(Prompt.ask("Material file path"))
        if not src.exists():
            _exit(f"Material path not found: {src}")
        category = Prompt.ask("Material category", choices=CATEGORIES, default="manuscript_draft")
        desc = Prompt.ask("Material note", default="")
        material = store.add_material(selected_project, src, category, desc, [])
        console.print(f"Added material: {material.material_id} ({material.filename})")
        pdir, pmeta = store.get_project(selected_project)

    if not pmeta.materials:
        console.print(
            "Project has no indexed materials yet. Add files to "
            "`materials/manuscript` or `materials/other`, or use `project add-material`, then run launch/review again."
        )
        raise typer.Exit(0)
    table = Table(title=f"Materials in {pmeta.name}")
    table.add_column("ID")
    table.add_column("File")
    table.add_column("Category")
    for material in pmeta.materials:
        table.add_row(material.material_id, material.filename, material.category)
    console.print(table)
    workflow = Prompt.ask(
        "Workflow",
        choices=["single-review", "batch-review", "deep-run", "compare-drafts", "full-evaluation-sweep", "benchmark-models", "diagnose"],
        default="single-review",
    )
    if workflow == "diagnose":
        diagnose(config_path=config_path, output_dir=output_dir)
        return
    if workflow == "benchmark-models":
        benchmark(models=None, output_dir=output_dir, config_path=config_path)
        return
    if workflow == "compare-drafts":
        old_path = Path(Prompt.ask("Old draft path"))
        new_path = Path(Prompt.ask("New draft path"))
        compare(old_draft=old_path, new_draft=new_path, model=roles.balanced_model, output_dir=output_dir, config_path=config_path, project=selected_project)
        return
    if workflow == "deep-run":
        deep_run_cmd(
            project=selected_project,
            manuscript_id=None,
            output_dir=output_dir,
            config_path=config_path,
            embedding_model=roles.embedding_model if roles.embedding_model in emb else None,
            disable_training_guidance=False,
        )
        return
    if workflow == "full-evaluation-sweep":
        anchor = Path(Prompt.ask("Anchor published paper path"))
        evaluate_paper(
            anchor_paper=anchor,
            project=selected_project,
            model=roles.deep_model if roles.deep_model in chat else roles.balanced_model,
            embedding_model=roles.embedding_model if roles.embedding_model in emb else None,
            profiles=",".join(EVALUATION_PROFILES),
            output_dir=output_dir,
            config_path=config_path,
        )
        return

    profile = Prompt.ask("Profile", choices=PROFILE_KEYS, default=pmeta.defaults.profile)
    selected_model = Prompt.ask("Review model", default=pmeta.defaults.review_model if pmeta.defaults.review_model in chat else roles.balanced_model)
    selected_embed = Prompt.ask("Embedding model (or 'none')", default=pmeta.defaults.embedding_model if pmeta.defaults.embedding_model else "none")
    disable_embeddings = selected_embed.lower() == "none"
    if workflow == "batch-review":
        material_ids = ",".join([m.material_id for m in pmeta.materials])
    else:
        # manuscript-first default; supporting docs are injected as context by review().
        material_ids = None
    review(
        input_path=None,
        profile=profile,
        model=selected_model,
        embedding_model=None if disable_embeddings else selected_embed,
        disable_embeddings=disable_embeddings,
        strict_schema=pmeta.defaults.strict_schema,
        output_dir=output_dir,
        config_path=config_path,
        keep_raw=pmeta.defaults.keep_raw_outputs,
        continue_on_error=True,
        project=selected_project,
        material_ids=material_ids,
        debug=False,
    )


@project_app.command("create")
def project_create(name: str = typer.Argument(...), description: str = typer.Option(""), tags: str = typer.Option(""), review_model: Optional[str] = typer.Option(None), embedding_model: Optional[str] = typer.Option(None), profile: str = typer.Option("balanced")):
    cfg = load_config()
    defaults = ProjectDefaults(
        review_model=review_model or cfg.defaults.balanced_review_model,
        embedding_model=embedding_model or cfg.defaults.embedding_model,
        profile=profile,
        strict_schema=cfg.defaults.strict_schema,
        retrieval_enabled=cfg.retrieval.enabled,
        keep_raw_outputs=cfg.defaults.keep_raw_outputs,
    )
    pdir, meta = _store().create_project(name, description, [t.strip() for t in tags.split(",") if t.strip()], defaults)
    console.print(f"Created project {meta.project_id}: {meta.name} at {pdir}")


@project_app.command("list")
def project_list(include_archived: bool = typer.Option(False)):
    rows = _store().list_projects(include_archived=include_archived)
    table = Table(title="Projects")
    table.add_column("Project ID")
    table.add_column("Name")
    table.add_column("Archived")
    table.add_column("Materials")
    table.add_column("Runs")
    for _, meta in rows:
        table.add_row(meta.project_id, meta.name, str(meta.archived), str(len(meta.materials)), str(len(meta.runs)))
    console.print(table)


@project_app.command("use")
def project_use(project_id: str = typer.Argument(...)):
    _store().set_active_project(project_id)
    console.print(f"Active project set: {project_id}")


@project_app.command("rename")
def project_rename(project_id: str = typer.Argument(...), new_name: str = typer.Argument(...)):
    meta = _store().rename_project(project_id, new_name)
    console.print(f"Renamed: {meta.project_id} -> {meta.name}")


@project_app.command("archive")
def project_archive(project_id: str = typer.Argument(...), archived: bool = typer.Option(True)):
    meta = _store().archive_project(project_id, archived=archived)
    console.print(f"Archive set for {meta.project_id}: {meta.archived}")


@project_app.command("delete")
def project_delete(project_id: str = typer.Argument(...), force: bool = typer.Option(False)):
    _store().delete_project(project_id, force=force)
    console.print(f"Deleted project: {project_id}")


@project_app.command("add-material")
def project_add_material(source: Path = typer.Argument(...), category: str = typer.Option("manuscript_draft"), project: Optional[str] = typer.Option(None), description: str = typer.Option(""), tags: str = typer.Option("")):
    if category not in CATEGORIES:
        _exit(f"Unsupported category: {category}")
    _, meta = _project_or_exit(project)
    material = _store().add_material(meta.project_id, source, category, description, [t.strip() for t in tags.split(",") if t.strip()])
    console.print(f"Added material {material.material_id} to {meta.project_id}")


@project_app.command("remove-material")
def project_remove_material(material_id: str = typer.Argument(...), project: Optional[str] = typer.Option(None)):
    _, meta = _project_or_exit(project)
    _store().remove_material(meta.project_id, material_id)
    console.print(f"Removed material {material_id}")


@project_app.command("inspect")
def project_inspect(project: Optional[str] = typer.Option(None)):
    pdir, meta = _project_or_exit(project)
    _store().sync_project_material_inventory(meta.project_id)
    _, meta = _store().get_project(meta.project_id)
    manuscript_dir = pdir / "materials" / "manuscript"
    other_dir = pdir / "materials" / "other"
    console.print(
        Panel(
            f"Name: {meta.name}\n"
            f"Project ID: {meta.project_id}\n"
            f"Description: {meta.description}\n"
            f"Tags: {', '.join(meta.tags) if meta.tags else '-'}\n"
            f"Defaults: model={meta.defaults.review_model}, embedding={meta.defaults.embedding_model}, profile={meta.defaults.profile}\n"
            f"Manual material folders: {manuscript_dir} and {other_dir}",
            title="Project Summary",
        )
    )
    table = Table(title="Materials")
    table.add_column("Material ID")
    table.add_column("File")
    table.add_column("Category")
    for material in meta.materials:
        table.add_row(material.material_id, material.filename, material.category)
    console.print(table)
    run_table = Table(title="Run History")
    run_table.add_column("Run ID")
    run_table.add_column("Workflow")
    run_table.add_column("Status")
    run_table.add_column("Model")
    for run in reversed(meta.runs[-20:]):
        run_table.add_row(run.run_id, run.workflow, run.status, run.model or "-")
    console.print(run_table)


@project_app.command("runs")
def project_runs(project: Optional[str] = typer.Option(None)):
    _, meta = _project_or_exit(project)
    table = Table(title="Runs")
    table.add_column("Run ID")
    table.add_column("Workflow")
    table.add_column("Profile")
    table.add_column("Model")
    table.add_column("Warnings")
    table.add_column("Status")
    table.add_column("Output Exists")
    table.add_column("Output Dir")
    for run in reversed(meta.runs):
        out_path = _resolve_run_output(meta.project_id, run.output_dir, run.run_id)
        table.add_row(
            run.run_id,
            run.workflow,
            run.profile or "-",
            run.model or "-",
            str(run.warning_count),
            run.status,
            "yes" if out_path.exists() else "no",
            str(out_path),
        )
    console.print(table)


@project_app.command("last-output")
def project_last_output(project: Optional[str] = typer.Option(None)):
    _, meta = _project_or_exit(project)
    if not meta.runs:
        _exit("No runs found for project.")
    run = meta.runs[-1]
    out = _resolve_run_output(meta.project_id, run.output_dir, run.run_id)
    lines = [
        f"Project: {meta.project_id}",
        f"Run ID: {run.run_id}",
        f"Workflow: {run.workflow}",
        f"Status: {run.status}",
        f"Output dir: {out}",
        f"Exists: {out.exists()}",
    ]
    if out.exists():
        reports = list(out.rglob("review_report.md"))[:3]
        if reports:
            lines.append("Sample reports:")
            for p in reports:
                lines.append(f"- {p.resolve()}")
    console.print(Panel.fit("\n".join(lines), title="Last Output"))


@project_app.command("migrate-outputs")
def project_migrate_outputs(
    project: Optional[str] = typer.Option(None),
    dry_run: bool = typer.Option(True, help="Show planned moves without applying."),
):
    pdir, meta = _project_or_exit(project)
    moves: list[tuple[Path, Path, str]] = []
    for run in meta.runs:
        current = Path(run.output_dir)
        if current.exists() and str(current.resolve()).startswith(str(pdir.resolve())):
            continue
        resolved = _resolve_run_output(meta.project_id, run.output_dir, run.run_id)
        if not resolved.exists():
            continue
        scope = "evaluations" if run.workflow == "evaluate-paper" else "runs"
        dest = pdir / scope / run.run_id
        if resolved.resolve() == dest.resolve():
            continue
        moves.append((resolved, dest, run.run_id))
    eval_moves: list[tuple[Path, Path, str]] = []
    for ev in meta.evaluations:
        current = Path(ev.output_dir)
        if current.exists() and str(current.resolve()).startswith(str(pdir.resolve())):
            continue
        resolved = current if current.exists() else (REPO_ROOT / "outputs" / ev.evaluation_id)
        if not resolved.exists():
            continue
        dest = pdir / "evaluations" / ev.evaluation_id
        if resolved.resolve() == dest.resolve():
            continue
        eval_moves.append((resolved, dest, ev.evaluation_id))

    if not moves and not eval_moves:
        console.print("No migratable outputs found for project.")
        return

    table = Table(title="Planned Output Migration")
    table.add_column("Run ID")
    table.add_column("From")
    table.add_column("To")
    for src, dst, rid in moves:
        table.add_row(rid, str(src), str(dst))
    for src, dst, rid in eval_moves:
        table.add_row(f"eval:{rid}", str(src), str(dst))
    console.print(table)
    if dry_run:
        console.print("Dry run only. Re-run with --no-dry-run to apply.")
        return

    for src, dst, rid in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst = dst.parent / f"{dst.name}_migrated"
        shutil.move(str(src), str(dst))
        for run in meta.runs:
            if run.run_id == rid:
                run.output_dir = str(dst.resolve())
                break
    for src, dst, rid in eval_moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst = dst.parent / f"{dst.name}_migrated"
        shutil.move(str(src), str(dst))
        for ev in meta.evaluations:
            if ev.evaluation_id == rid:
                ev.output_dir = str(dst.resolve())
                break
    (pdir / "project.json").write_text(meta.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"Migrated {len(moves)} runs and {len(eval_moves)} evaluations into project-local storage.")

@project_app.command("rerun")
def project_rerun(run_id: str = typer.Argument(...), project: Optional[str] = typer.Option(None), output_dir: Optional[Path] = typer.Option(None), config_path: Optional[str] = typer.Option(None)):
    _, meta = _project_or_exit(project)
    run = _store().get_run_record(meta.project_id, run_id)
    if run.workflow == "review":
        review(
            input_path=None,
            profile=run.profile or meta.defaults.profile,
            model=run.model or meta.defaults.review_model,
            embedding_model=run.embedding_model or meta.defaults.embedding_model,
            disable_embeddings=not bool(run.embedding_model or meta.defaults.embedding_model),
            strict_schema=meta.defaults.strict_schema,
            output_dir=output_dir,
            config_path=config_path,
            keep_raw=meta.defaults.keep_raw_outputs,
            continue_on_error=True,
            project=meta.project_id,
            material_ids=run.settings.get("material_ids"),
            debug=False,
        )
        return
    _exit(f"Unsupported rerun workflow for now: {run.workflow}")


@project_app.command("set-defaults")
def project_set_defaults(project: Optional[str] = typer.Option(None), review_model: Optional[str] = typer.Option(None), embedding_model: Optional[str] = typer.Option(None), profile: Optional[str] = typer.Option(None), strict_schema: Optional[bool] = typer.Option(None), retrieval_enabled: Optional[bool] = typer.Option(None), keep_raw_outputs: Optional[bool] = typer.Option(None)):
    _, meta = _project_or_exit(project)
    defaults = ProjectDefaults(
        review_model=review_model or meta.defaults.review_model,
        embedding_model=embedding_model if embedding_model is not None else meta.defaults.embedding_model,
        profile=profile or meta.defaults.profile,
        strict_schema=meta.defaults.strict_schema if strict_schema is None else strict_schema,
        retrieval_enabled=meta.defaults.retrieval_enabled if retrieval_enabled is None else retrieval_enabled,
        keep_raw_outputs=meta.defaults.keep_raw_outputs if keep_raw_outputs is None else keep_raw_outputs,
    )
    updated = _store().set_defaults(meta.project_id, defaults)
    console.print(f"Updated defaults for {updated.project_id}")


@project_app.command("mark-baseline")
def project_mark_baseline(run_id: str = typer.Argument(...), project: Optional[str] = typer.Option(None)):
    _, meta = _project_or_exit(project)
    _store().mark_run_baseline(meta.project_id, run_id)
    console.print(f"Marked baseline run: {run_id}")


@slack_app.command("simulate")
def slack_simulate(file: Path = typer.Option(...), command: str = typer.Option(...), user_id: str = typer.Option("UDEV"), channel_id: str = typer.Option("CDEV"), project: Optional[str] = typer.Option(None), output_dir: Optional[Path] = typer.Option(None), config_path: Optional[str] = typer.Option(None)):
    if not file.exists():
        _exit(f"File not found: {file}")
    req = map_slack_command_to_workflow(command)
    request_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    submission = SlackSubmission(
        request_id=request_id,
        user_id=user_id,
        channel_id=channel_id,
        file_path=str(file),
        file_name=file.name,
        workflow=SlackWorkflowRequest(command=command, project=project, profile=req.get("profile"), strict_schema=True, retrieval=True),
    )
    store = _store()
    if project:
        _, meta = store.get_project(project)
        project_id = meta.project_id
    else:
        cfg = load_config(config_path)
        _, meta = store.create_project(
            name=f"slack_{file.stem}",
            description=f"Auto-created from Slack simulation for {file.name}",
            tags=["slack-dev"],
            defaults=ProjectDefaults(
                review_model=cfg.defaults.balanced_review_model,
                embedding_model=cfg.defaults.embedding_model,
                profile=cfg.defaults.default_profile,
                strict_schema=cfg.defaults.strict_schema,
                retrieval_enabled=cfg.retrieval.enabled,
                keep_raw_outputs=cfg.defaults.keep_raw_outputs,
            ),
        )
        project_id = meta.project_id
    added = store.add_material(project_id, file, "published_paper", "Slack-submitted file")
    if output_dir is not None:
        console.print("[yellow]Ignoring --output-dir for project-scoped Slack simulation; using project-local storage.[/yellow]")
    pdir, _ = store.get_project(project_id)
    submissions_dir = pdir / "notes" / "slack_submissions"
    submissions_dir.mkdir(parents=True, exist_ok=True)
    save_submission_record(submission, submissions_dir)
    if req["workflow"] == "evaluate_paper":
        evaluate_paper(
            anchor_paper=file,
            project=project_id,
            model=None,
            embedding_model=None,
            profiles=",".join(EVALUATION_PROFILES),
            output_dir=None,
            config_path=config_path,
        )
    else:
        review(
            input_path=None,
            profile=req["profile"],
            model=None,
            embedding_model=None,
            disable_embeddings=False,
            strict_schema=None,
            output_dir=None,
            config_path=config_path,
            keep_raw=None,
            continue_on_error=True,
            project=project_id,
            material_ids=added.material_id,
            debug=False,
        )
    _, updated = store.get_project(project_id)
    if updated.runs:
        run = updated.runs[-1]
        out_dir = _resolve_run_output(project_id, run.output_dir, run.run_id)
        summary = build_result_summary(
            submission=submission,
            store=store,
            project_id=project_id,
            run_id=run.run_id,
            status=run.status,
            outputs=[str(out_dir)],
            warnings=[],
        )
        save_result_summary(summary, out_dir / "artifacts" / "slack_result_summary.json")
        console.print(f"Slack simulation complete: {out_dir}")
    else:
        console.print("Slack simulation completed, but no run record was found.")


@training_app.command("sync")
def training_sync(config_path: Optional[str] = typer.Option(None), force_rebuild: bool = typer.Option(False)):
    cfg = load_config(config_path)
    trainer = TrainingCacheManager.from_config(cfg)
    report = trainer.sync(force_rebuild=force_rebuild)
    console.print(
        f"Training materials synced: {report.added} new, {report.changed} changed, {report.removed} removed, "
        f"{report.unchanged} unchanged, {report.failed} failed."
    )
    console.print(f"Global lab guidance active: {report.active_files} files across {len(report.by_category)} categories.")


@training_app.command("status")
def training_status(config_path: Optional[str] = typer.Option(None)):
    cfg = load_config(config_path)
    trainer = TrainingCacheManager.from_config(cfg)
    status = trainer.status()
    table = Table(title="Training Materials Status")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["source_root", "cache_root", "tracked_files", "active_guidance_files", "parse_failures", "last_sync"]:
        table.add_row(key, str(status.get(key)))
    console.print(table)
    by_cat = status.get("files_by_category", {})
    ctab = Table(title="Training Files By Category")
    ctab.add_column("Category")
    ctab.add_column("Count")
    for cat, count in sorted(by_cat.items()):
        ctab.add_row(cat, str(count))
    console.print(ctab)


@training_app.command("rebuild")
def training_rebuild(config_path: Optional[str] = typer.Option(None)):
    training_sync(config_path=config_path, force_rebuild=True)


@training_app.command("list")
def training_list(config_path: Optional[str] = typer.Option(None)):
    cfg = load_config(config_path)
    trainer = TrainingCacheManager.from_config(cfg)
    records = trainer.list_records()
    table = Table(title="Training Files")
    table.add_column("ID")
    table.add_column("Category")
    table.add_column("Path")
    table.add_column("Status")
    for record in records:
        status = "ok" if record.included_in_guidance else "excluded"
        table.add_row(record.file_id, record.category, record.relative_path, status)
    console.print(table)


@training_app.command("show")
def training_show(key: str = typer.Argument(...), config_path: Optional[str] = typer.Option(None)):
    cfg = load_config(config_path)
    trainer = TrainingCacheManager.from_config(cfg)
    try:
        payload = trainer.show_record(key)
    except KeyError as exc:
        _exit(str(exc))
    console.print_json(data=payload)


@tools_app.command("list")
def tools_list(config_path: Optional[str] = typer.Option(None)):
    cfg = load_config(config_path)
    reg = ToolRegistry(cfg)
    avail = reg.availability()
    table = Table(title="Tool Availability")
    table.add_column("Tool")
    table.add_column("Installed")
    table.add_column("Optional")
    table.add_column("Detail")
    for name, data in sorted(avail.items()):
        table.add_row(name, "yes" if data["installed"] else "no", "yes" if data["optional"] else "no", data.get("detail", ""))
    console.print(table)


@tools_app.command("diagnose")
def tools_diagnose(config_path: Optional[str] = typer.Option(None)):
    cfg = load_config(config_path)
    reg = ToolRegistry(cfg)
    avail = reg.availability()
    missing_required = [name for name, data in avail.items() if (not data["optional"] and not data["installed"])]
    console.print_json(data={"strict_offline": cfg.defaults.strict_offline, "availability": avail, "missing_required": missing_required})
    if missing_required:
        raise typer.Exit(2)


@tools_app.command("smoke-test")
def tools_smoke_test(
    config_path: Optional[str] = typer.Option(None),
    sample_pdf: Optional[Path] = typer.Option(None),
    sample_docx: Optional[Path] = typer.Option(None),
):
    cfg = load_config(config_path)
    out = run_tool_smoke_tests(cfg, sample_pdf=sample_pdf, sample_docx=sample_docx)
    console.print_json(data=out)


@app.command("init-config")
def init_config(path: Path = typer.Option(Path("config/local.example.yaml"))):
    write_example_local_config(path)
    console.print(f"Wrote config template to {path}")


def main() -> None:
    try:
        app()
    except ProviderError as exc:
        console.print(f"[red]Provider error:[/red] {exc}")
        raise typer.Exit(2)
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted by user.[/yellow]")
        raise typer.Exit(130)
    except Exception as exc:
        console.print(f"[red]Unhandled error:[/red] {exc}")
        console.print("[red]Check the latest run debug.log in the run directory for full traceback.[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    main()
