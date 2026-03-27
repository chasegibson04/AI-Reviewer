from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.tools.availability import scan_tool_availability
from ai_reviewer.tools.docx_tools import create_commented_docx_copy, parse_docx_structured
from ai_reviewer.tools.pdf_tools import parse_pdf_structured
from ai_reviewer.tools.scholarly_tools import lookup_doi_metadata, normalize_doi


@dataclass
class ToolRegistry:
    cfg: ReviewerConfig

    def availability(self) -> dict:
        return {k: v.__dict__ for k, v in scan_tool_availability().items()}

    def parse_pdf(self, path: Path) -> dict:
        return parse_pdf_structured(path)

    def parse_docx(self, path: Path) -> dict:
        return parse_docx_structured(path)

    def comment_docx_copy(self, source_docx: Path, output_docx: Path, comments: list[dict]) -> dict:
        return create_commented_docx_copy(source_docx, output_docx, comments)

    def lookup_doi(self, text: str) -> dict:
        doi = normalize_doi(text)
        if not doi:
            return {"enabled": not self.cfg.defaults.strict_offline, "error": "doi_not_detected"}
        return lookup_doi_metadata(doi, self.cfg)
