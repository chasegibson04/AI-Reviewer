from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.models.base import Provider
from ai_reviewer.models.selector import infer_model_roles, split_chat_and_embedding_models


@dataclass
class DiagnosticItem:
    name: str
    status: str  # checked | warning | error | fixed | manual
    detail: str

    @property
    def ok(self) -> bool:
        return self.status in {"checked", "fixed", "warning", "manual"}


@dataclass
class DiagnosticReport:
    items: list[DiagnosticItem]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.items)


def _check_dependency(module_name: str) -> tuple[bool, str]:
    try:
        __import__(module_name)
        return True, "installed"
    except Exception as exc:
        return False, str(exc)


def run_diagnostics(provider: Provider, config: ReviewerConfig, output_root: Path) -> DiagnosticReport:
    items: list[DiagnosticItem] = []

    py_ok = shutil.which("python") is not None
    items.append(DiagnosticItem("python_binary", "checked" if py_ok else "error", f"python found={py_ok}"))
    items.append(DiagnosticItem("python_version", "checked", sys.version.split()[0]))

    venv_active = bool(os.getenv("VIRTUAL_ENV"))
    items.append(DiagnosticItem("venv", "checked" if venv_active else "warning", f"active={venv_active}"))

    os_name = platform.system()
    items.append(DiagnosticItem("platform", "checked", f"detected={os_name}"))

    dep_checks = {
        "typer": "typer",
        "rich": "rich",
        "requests": "requests",
        "pydantic": "pydantic",
        "yaml": "yaml",
        "pypdf": "pypdf",
        "docx": "docx",
    }
    for label, module in dep_checks.items():
        ok, detail = _check_dependency(module)
        items.append(DiagnosticItem(f"dep_{label}", "checked" if ok else "error", detail))

    health_ok, health_msg = provider.health()
    items.append(DiagnosticItem("ollama_health", "checked" if health_ok else "error", health_msg))

    installed: list[str] = []
    if health_ok:
        try:
            installed = provider.list_models()
            items.append(DiagnosticItem("models_detected", "checked" if installed else "error", f"count={len(installed)}"))
        except Exception as exc:
            items.append(DiagnosticItem("models_detected", "error", str(exc)))
    else:
        items.append(DiagnosticItem("models_detected", "error", "Skipped: Ollama unreachable"))

    if installed:
        chat, embed = split_chat_and_embedding_models(installed)
        roles = infer_model_roles(installed, config)

        items.append(DiagnosticItem("chat_models", "checked" if chat else "error", ", ".join(chat[:10]) or "none"))
        items.append(DiagnosticItem("embedding_models", "checked" if embed else "warning", ", ".join(embed[:10]) or "none"))

        balanced_ok = roles.balanced_model in installed
        deep_ok = roles.deep_model in installed
        embed_ok = (roles.embedding_model in installed) if roles.embedding_model else False

        items.append(
            DiagnosticItem(
                "default_model_policy",
                "checked" if balanced_ok and deep_ok else "warning",
                f"balanced={roles.balanced_model} present={balanced_ok}, deep={roles.deep_model} present={deep_ok}",
            )
        )
        items.append(
            DiagnosticItem(
                "embedding_policy",
                "checked" if embed_ok else "warning",
                f"embedding={roles.embedding_model}, fallback={roles.embedding_fallback}",
            )
        )

    writable = True
    detail = "ok"
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        test_path = output_root / ".write_test"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
    except Exception as exc:
        writable = False
        detail = str(exc)
    items.append(DiagnosticItem("output_dir", "checked" if writable else "error", detail))

    if config.defaults.strict_offline:
        strict_status = "checked"
        strict_detail = f"enabled, ollama_url={config.defaults.ollama_base_url}"
    else:
        strict_status = "warning"
        strict_detail = "disabled: outbound network protections reduced"
    items.append(DiagnosticItem("strict_offline", strict_status, strict_detail))

    items.append(
        DiagnosticItem(
            "legacy_execution_warning",
            "warning",
            "Legacy AI-Scientist autonomous code execution remains available and risky.",
        )
    )

    return DiagnosticReport(items)
