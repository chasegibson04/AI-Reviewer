import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

BLOCKED_SNIPPETS = ("pampa", "horseshoe")

PROFILES = [
    "balanced_local",
    "deep_local",
    "local_moe",
    "one_big_model",
    "full_manuscript_final_pass",
]

TARGETS = [
    Path("example_papers/gan_diffusion.pdf"),
    Path("projects/20260327051312_miniaturization_d2b/materials/manuscript/s44160-023-00351-1.pdf"),
]


class BridgeClient:
    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self._next_id = 1

    async def send(self, method: str, params: dict):
        req_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload).encode() + b"\n")
        await self.process.stdin.drain()

        assert self.process.stdout is not None
        raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=60)
        if not raw:
            raise RuntimeError("bridge returned no response")
        response = json.loads(raw.decode())
        if response.get("id") != req_id:
            raise RuntimeError(f"unexpected response id: {response}")
        return response

    async def initialize(self):
        response = await self.send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "overnight-validator", "version": "1.0.0"},
            },
        )
        if "result" not in response:
            raise RuntimeError(f"initialize failed: {response}")

    async def call_tool(self, name: str, arguments: dict):
        response = await self.send(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        if "result" not in response:
            raise RuntimeError(f"tool call failed ({name}): {response}")
        content = response["result"].get("content", [])
        if not content:
            raise RuntimeError(f"empty tool response ({name})")
        return json.loads(content[0]["text"])


def assert_allowed_target(path: Path) -> None:
    lowered = str(path).lower()
    if any(snippet in lowered for snippet in BLOCKED_SNIPPETS):
        raise RuntimeError(f"Blocked target path: {path}")


def fetch_local_models() -> list[str]:
    try:
        with urlopen("http://localhost:11434/api/tags", timeout=2.5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name", "").strip() for m in payload.get("models", []) if m.get("name")]
        return [m for m in models if m]
    except Exception:
        return []


def largest_model(models: list[str]) -> str | None:
    scored: list[tuple[float, str]] = []
    for model in models:
        match = re.search(r"(\d+(?:\.\d+)?)\s*b", model.lower())
        if match:
            scored.append((float(match.group(1)), model))
    if not scored:
        return models[0] if models else None
    scored.sort(reverse=True)
    return scored[0][1]


def resolve_profile_target(profile: str, models: list[str]) -> tuple[str, str]:
    if profile == "balanced_local":
        return ("balanced local", os.environ.get("OLLAMA_MEDIUM_MODEL", "llama3.1:8b"))
    if profile == "deep_local":
        return ("deep local", os.environ.get("OLLAMA_BIG_MODEL", "qwen2.5-coder:32b"))
    if profile == "local_moe":
        return ("local MOE staged routing", "local_moe")

    if profile in {"one_big_model", "full_manuscript_final_pass"}:
        if any(m.lower().startswith("gemma4:26b") for m in models):
            return (
                "single big-model review" if profile == "one_big_model" else "full-manuscript final pass",
                "gemma4:26b",
            )
        if any(m.lower().startswith("gemma4:31b") for m in models):
            return (
                "single big-model review" if profile == "one_big_model" else "full-manuscript final pass",
                "gemma4:31b",
            )
        fallback = os.environ.get("OLLAMA_BIG_MODEL") or largest_model(models) or "gemma4:26b"
        return (
            "single big-model review" if profile == "one_big_model" else "full-manuscript final pass",
            fallback,
        )

    raise RuntimeError(f"Unsupported profile: {profile}")


def build_comments(section_map: dict, analyses: dict, profile: str) -> list[str]:
    comments: list[str] = []
    section_labels = ", ".join(sorted(section_map.keys())[:6]) if section_map else "Body"

    methods = analyses.get("methods", {})
    if methods.get("findings"):
        for item in methods["findings"][:2]:
            comments.append(f"[Methods][{section_labels}] {item}")

    coherence = analyses.get("coherence", {})
    if coherence.get("findings"):
        for item in coherence["findings"][:2]:
            comments.append(f"[Coherence][{section_labels}] {item}")

    terminology = analyses.get("terminology", {})
    if terminology.get("findings"):
        comments.append(f"[Terminology][{section_labels}] {terminology['findings'][0]}")

    citations = analyses.get("citations", {})
    if citations.get("findings"):
        comments.append(f"[Citations][{section_labels}] {citations['findings'][0]}")

    figures = analyses.get("figures_tables", {})
    if figures.get("findings"):
        comments.append(f"[Figures/Tables][{section_labels}] {figures['findings'][0]}")

    journal = analyses.get("journal_format", {})
    if journal.get("findings"):
        comments.append(f"[Format][{section_labels}] {journal['findings'][0]}")

    if not comments:
        comments.append("[General] Heuristic pass found no high-risk issues; perform manual review for nuanced claims.")

    if section_map:
        mapped = ", ".join(sorted(section_map.keys())[:6])
        comments.append(f"[Section map] Detected sections: {mapped}.")

    profile_focus = {
        "balanced_local": "[Profile focus] Balanced local mode prioritizes broad coverage with moderate depth.",
        "deep_local": "[Profile focus] Deep local mode emphasizes skepticism in methods and claim support.",
        "local_moe": "[Profile focus] Local MOE mode mixes specialist stages; check cross-stage consistency.",
        "one_big_model": "[Profile focus] One-big-model mode applies a single high-capacity reviewer pass.",
        "full_manuscript_final_pass": "[Profile focus] Final-pass mode prioritizes global coherence and publication readiness.",
    }
    if profile in profile_focus:
        comments.append(profile_focus[profile])

    return comments[:12]


def score_run_quality(run_dir: Path) -> dict:
    comments_path = run_dir / "manuscript_comment_manifest.json"
    summary_path = run_dir / "run_summary.json"
    routing_path = run_dir / "routing_trace.json"
    validation_path = run_dir / "validation_report.json"

    comments = json.loads(comments_path.read_text(encoding="utf-8")) if comments_path.exists() else []
    run_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    routing = json.loads(routing_path.read_text(encoding="utf-8")) if routing_path.exists() else {}
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}

    comment_text = "\n".join(str(c) for c in comments)
    unique_comments = len(set(str(c).strip() for c in comments if str(c).strip()))
    total_comments = len(comments)

    specificity = "strong" if any(tok in comment_text.lower() for tok in ["missing", "detected", "line:", "section"]) else "moderate"
    if total_comments <= 2:
        specificity = "vague"
    localizability = "strong" if any("[" in str(c) and "]" in str(c) for c in comments) else "poor"
    correctness = "plausible" if validation.get("valid") else "uncertain"
    helpfulness = "actionable" if any("missing" in str(c).lower() for c in comments) else "mildly helpful"
    redundancy = "low" if unique_comments == total_comments else ("moderate" if unique_comments >= max(1, total_comments - 2) else "excessive")
    section_awareness = "strong" if "[section map]" in comment_text.lower() or "section" in comment_text.lower() else "acceptable"
    front_matter_safety = "safe" if not validation.get("front_matter_violations") else "unsafe"
    final_review_coherence = "strong" if total_comments >= 6 and routing.get("stages") else "acceptable"

    return {
        "run_dir": str(run_dir),
        "profile": run_summary.get("profile"),
        "model_target": run_summary.get("model_target"),
        "comment_count": total_comments,
        "specificity": specificity,
        "localizability": localizability,
        "correctness": correctness,
        "helpfulness": helpfulness,
        "redundancy": redundancy,
        "section_awareness": section_awareness,
        "front_matter_safety": front_matter_safety,
        "final_review_coherence": final_review_coherence,
    }


def write_quality_report(overnight_root: Path, run_records: list[dict]) -> None:
    lines: list[str] = []
    lines.append("# Overnight Quality Report")
    lines.append("")
    lines.append("| Target | Profile | Model | Comments | Specificity | Helpfulness | Redundancy | Front-matter safety |")
    lines.append("| --- | --- | --- | ---: | --- | --- | --- | --- |")

    details: list[dict] = []
    for record in run_records:
        run_dir = Path(record["output_dir"])
        detail = score_run_quality(run_dir)
        details.append(detail)
        target_name = run_dir.parent.name
        lines.append(
            f"| {target_name} | {detail['profile']} | {detail['model_target']} | {detail['comment_count']} | "
            f"{detail['specificity']} | {detail['helpfulness']} | {detail['redundancy']} | {detail['front_matter_safety']} |"
        )

    (overnight_root / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (overnight_root / "quality_report.json").write_text(json.dumps(details, indent=2), encoding="utf-8")


def build_suggested_changes(line_edits: list[dict]) -> list[dict]:
    changes: list[dict] = []
    for idx, edit in enumerate(line_edits[:10], start=1):
        original = str(edit.get("original", "")).strip()
        suggested = str(edit.get("suggested", "")).strip()
        if not original or not suggested:
            continue
        changes.append(
            {
                "id": f"line-edit-{idx}",
                "target": "body",
                "original": original,
                "suggested": suggested,
            }
        )
    return changes


async def run_profile(client: BridgeClient, repo_root: Path, manuscript: Path, profile: str, out_dir: Path):
    mode, model_target = resolve_profile_target(profile, fetch_local_models())
    await client.call_tool("inspect_project", {"cwd": str((repo_root / "claude-review-v2").resolve())})

    parse_tool = "parse_docx" if manuscript.suffix.lower() == ".docx" else "parse_pdf"
    parsed = await client.call_tool(parse_tool, {"file_path": str(manuscript.resolve())})

    mapped = await client.call_tool("map_sections", {"content": parsed.get("content", "")})
    digest = await client.call_tool("digest_manuscript", {"content": parsed.get("content", "")})

    terminology = await client.call_tool("analyze_terminology", {"content": parsed.get("content", "")})
    coherence = await client.call_tool("analyze_coherence", {"content": parsed.get("content", "")})
    methods = await client.call_tool("analyze_methods", {"content": parsed.get("content", "")})
    figures_tables = await client.call_tool("analyze_figures_tables", {"content": parsed.get("content", "")})
    citations = await client.call_tool("analyze_citations", {"content": parsed.get("content", "")})
    journal_format = await client.call_tool("analyze_journal_format", {"content": parsed.get("content", "")})
    line_edits_payload = await client.call_tool("generate_line_edits", {"content": parsed.get("content", "")})

    analyses = {
        "terminology": terminology,
        "coherence": coherence,
        "methods": methods,
        "figures_tables": figures_tables,
        "citations": citations,
        "journal_format": journal_format,
    }

    findings_flat: list[str] = []
    for payload in analyses.values():
        findings_flat.extend(payload.get("findings", [])[:3])

    arbitration = await client.call_tool("arbitrate_review", {"findings": findings_flat, "profile": profile})

    comments = build_comments(mapped.get("section_map", {}), analyses, profile)
    arb_summary = arbitration.get("summary", "").strip()
    arb_reco = arbitration.get("recommendation", "unknown")
    if arb_summary:
        comments.append(f"[Arbitration][{arb_reco}] {arb_summary.splitlines()[0].lstrip('- ').strip()}")
    else:
        comments.append(f"[Arbitration][{arb_reco}] Arbitration completed but produced no narrative summary.")

    review_data = {
        "profile": profile,
        "mode": mode,
        "model_target": model_target,
        "source_mode": {"mode": "manuscript", "base_type": manuscript.suffix.lower().lstrip(".")},
        "section_map": mapped.get("section_map", {}),
        "comments": comments,
        "suggested_changes": build_suggested_changes(line_edits_payload.get("line_edits", [])),
        "support_ingest_report": {
            "available_support_docs": 0,
            "selected_support_docs": 0,
            "selection_basis": "none",
        },
        "support_usage_ledger": {"used_sources": [], "unused_sources": []},
        "assertion_ledger": {
            "claim_count": citations.get("citation_marker_count", 0),
            "claims": findings_flat[:8],
        },
        "claim_verification_summary": {
            "claim_count": citations.get("citation_marker_count", 0),
            "claims_checked": citations.get("citation_marker_count", 0),
            "likely_overstated": 0,
            "status": "heuristic_only",
        },
        "citation_verification_ledger": {
            "entries": citations.get("findings", []),
            "status": "heuristic_only",
        },
        "format_compliance_report": {
            "checks": journal_format.get("checks", {}),
            "findings": journal_format.get("findings", []),
        },
        "terminology_definition_report": {
            "defined_terms": [x.get("term") for x in terminology.get("top_terms", [])[:8] if x.get("term")],
            "findings": terminology.get("findings", []),
        },
        "coherence_transition_report": {
            "transition_markers": coherence.get("transition_markers", {}),
            "findings": coherence.get("findings", []),
        },
        "figure_table_reference_report": {
            "figure_references": figures_tables.get("figure_references", []),
            "table_references": figures_tables.get("table_references", []),
            "findings": figures_tables.get("findings", []),
        },
        "routing_trace": {
            "profile": profile,
            "transport": "local_mcp_bridge",
            "model_target": model_target,
            "stages": [
                "inspect_project",
                parse_tool,
                "map_sections",
                "digest_manuscript",
                "analyze_terminology",
                "analyze_coherence",
                "analyze_methods",
                "analyze_figures_tables",
                "analyze_citations",
                "analyze_journal_format",
                "generate_line_edits",
                "arbitrate_review",
                "render_outputs",
                "validate_outputs",
            ],
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    render = await client.call_tool("render_outputs", {"review_data": review_data, "output_dir": str(out_dir)})
    validate = await client.call_tool("validate_outputs", {"output_dir": str(out_dir)})
    replay = await client.call_tool("replay_run", {"run_id": str(out_dir)})

    return {
        "profile": profile,
        "mode": mode,
        "model_target": model_target,
        "manuscript": str(manuscript),
        "render": render,
        "validate": validate,
        "replay_summary": replay.get("run_summary", {}),
        "output_dir": str(out_dir),
        "digest_word_count": digest.get("word_count", 0),
    }


async def main():
    repo_root = Path(__file__).resolve().parents[2]

    selected_targets: list[Path] = []
    for target in TARGETS:
        absolute = (repo_root / target).resolve()
        assert_allowed_target(absolute)
        if not absolute.exists():
            raise FileNotFoundError(f"Target manuscript not found: {absolute}")
        selected_targets.append(absolute)

    process = await asyncio.create_subprocess_exec(
        "python3",
        "src/bridge/python/review_mcp_server.py",
        cwd=str(repo_root / "claude-review-v2"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **{"PYTHONPATH": str(repo_root)}},
    )

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    overnight_root = repo_root / "claude-review-v2" / "test_outputs" / "overnight" / stamp
    overnight_root.mkdir(parents=True, exist_ok=True)

    try:
        client = BridgeClient(process)
        await client.initialize()
        await client.call_tool("inspect_project", {"cwd": str((repo_root / 'claude-review-v2').resolve())})

        run_records: list[dict] = []

        for manuscript in selected_targets:
            safe_name = manuscript.stem.replace(" ", "_").replace("/", "_")[:80]
            manuscript_root = overnight_root / safe_name
            manuscript_root.mkdir(parents=True, exist_ok=True)

            for profile in PROFILES:
                out_dir = manuscript_root / profile
                record = await run_profile(client, repo_root, manuscript, profile, out_dir)
                run_records.append(record)

            balanced_dir = manuscript_root / "balanced_local"
            big_dir = manuscript_root / "one_big_model"
            await client.call_tool(
                "diff_run",
                {
                    "run_id_a": str(balanced_dir),
                    "run_id_b": str(big_dir),
                },
            )

            deep_dir = manuscript_root / "deep_local"
            moe_dir = manuscript_root / "local_moe"
            await client.call_tool(
                "diff_run",
                {
                    "run_id_a": str(deep_dir),
                    "run_id_b": str(moe_dir),
                },
            )

        write_quality_report(overnight_root, run_records)

        index = {
            "created_at": datetime.now(UTC).isoformat(),
            "blocked_policy": list(BLOCKED_SNIPPETS),
            "targets": [str(t) for t in selected_targets],
            "profiles": PROFILES,
            "runs": run_records,
        }

        (overnight_root / "overnight_index.json").write_text(
            json.dumps(index, indent=2), encoding="utf-8"
        )
        print(str(overnight_root))

    finally:
        process.terminate()
        await process.wait()


if __name__ == "__main__":
    asyncio.run(main())
