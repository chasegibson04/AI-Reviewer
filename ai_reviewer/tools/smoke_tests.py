from __future__ import annotations

from pathlib import Path

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.tools.registry import ToolRegistry


def run_tool_smoke_tests(cfg: ReviewerConfig, sample_pdf: Path | None = None, sample_docx: Path | None = None) -> dict:
    reg = ToolRegistry(cfg)
    out: dict = {"availability": reg.availability(), "tests": []}
    if sample_pdf and sample_pdf.exists():
        try:
            parsed = reg.parse_pdf(sample_pdf)
            out["tests"].append({"tool": "parse_pdf", "status": "pass", "engine": parsed.get("tool"), "chars": len(parsed.get("text", ""))})
        except Exception as exc:
            out["tests"].append({"tool": "parse_pdf", "status": "fail", "error": str(exc)})
    if sample_docx and sample_docx.exists():
        try:
            parsed = reg.parse_docx(sample_docx)
            out["tests"].append({"tool": "parse_docx", "status": "pass", "paragraph_count": parsed.get("paragraph_count", 0)})
        except Exception as exc:
            out["tests"].append({"tool": "parse_docx", "status": "fail", "error": str(exc)})
    return out
