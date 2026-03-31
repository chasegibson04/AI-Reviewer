import logging
from pathlib import Path
from types import SimpleNamespace

from typer.models import OptionInfo

import ai_reviewer.cli as cli
from ai_reviewer.cli import _parse_optional_csv_option
from ai_reviewer.config import ConcurrencyConfig, Defaults, ReviewerConfig


def test_parse_optional_csv_option_handles_typer_optioninfo():
    opt = OptionInfo(default=None)
    assert _parse_optional_csv_option(opt) is None


def test_parse_optional_csv_option_splits_csv_strings():
    assert _parse_optional_csv_option("a,b, c") == ["a", "b", "c"]


def test_deep_run_cmd_direct_call_tolerates_optioninfo_defaults(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    provider = SimpleNamespace(
        health=lambda: (True, "ok"),
        list_models=lambda: ["embed-model"],
    )
    cfg = ReviewerConfig(
        defaults=Defaults(strict_offline=True),
        concurrency=ConcurrencyConfig(enable_project_locks=False),
    )

    monkeypatch.setattr(cli, "_provider_for_workflow", lambda **kwargs: (provider, cfg, run_dir, logging.getLogger("test")))
    monkeypatch.setattr(cli, "_model_table", lambda installed, cfg: ([], ["embed-model"], SimpleNamespace(embedding_model="embed-model")))
    monkeypatch.setattr(cli, "_store", lambda: SimpleNamespace(
        get_project=lambda project: (tmp_path, SimpleNamespace(project_id=project, materials=[])),
        sync_project_material_inventory=lambda project: (0, 0, 0)
    ))
    monkeypatch.setattr(cli, "_resolve_docs", lambda *args, **kwargs: ([SimpleNamespace(source_path=Path("doc.docx"))], [], [], None))
    monkeypatch.setattr(cli, "fetch_citations_for_documents", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli,
        "run_deep_run",
        lambda **kwargs: SimpleNamespace(status="success", run_dir=run_dir, warnings=[]),
    )
    monkeypatch.setattr(cli, "verify_deep_run", lambda run_dir: SimpleNamespace(ok=True, key_files=[], issues=[]))
    monkeypatch.setattr(cli, "_record_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "_print_run_outcome", lambda *args, **kwargs: None)

    cli.deep_run_cmd(
        project="test-project",
        manuscript_id=None,
        output_dir=tmp_path,
        config_path=None,
        embedding_model=None,
        disable_training_guidance=False,
    )
