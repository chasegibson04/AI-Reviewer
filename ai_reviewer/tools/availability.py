from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass


@dataclass
class ToolAvailability:
    name: str
    installed: bool
    optional: bool
    detail: str = ""


def _has_module(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def scan_tool_availability() -> dict[str, ToolAvailability]:
    tools = {
        "python_docx": ToolAvailability("python_docx", _has_module("docx"), optional=False),
        "docx2python": ToolAvailability("docx2python", _has_module("docx2python"), optional=True),
        "mammoth": ToolAvailability("mammoth", _has_module("mammoth"), optional=True),
        "pymupdf": ToolAvailability("pymupdf", _has_module("pymupdf"), optional=False),
        "pymupdf4llm": ToolAvailability("pymupdf4llm", _has_module("pymupdf4llm"), optional=True),
        "pypdf": ToolAvailability("pypdf", _has_module("pypdf"), optional=False),
        "docling": ToolAvailability("docling", _has_module("docling"), optional=True),
        "ocrmypdf": ToolAvailability("ocrmypdf", _has_module("ocrmypdf"), optional=True),
        "grobid_client": ToolAvailability("grobid_client", _has_module("grobid_client"), optional=True),
        "bibtexparser": ToolAvailability("bibtexparser", _has_module("bibtexparser"), optional=True),
        "habanero": ToolAvailability("habanero", _has_module("habanero"), optional=True),
        "pyalex": ToolAvailability("pyalex", _has_module("pyalex"), optional=True),
        "pandoc_binary": ToolAvailability("pandoc_binary", shutil.which("pandoc") is not None, optional=True),
    }
    tools["grobid_server"] = ToolAvailability(
        "grobid_server",
        shutil.which("grobid") is not None,
        optional=True,
        detail="External service; configure separately if needed.",
    )
    return tools
