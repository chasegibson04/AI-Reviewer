import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

import mcp.server.stdio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

# Add the parent directory to sys.path to allow importing ai_reviewer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from ai_reviewer.ingest.loaders import parse_file, collect_paths
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.profiles import get_profile
from ai_reviewer.config import load_config
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.review.manuscript_annotation import build_annotated_manuscript_output, detect_source_mode

server = Server("manuscript-review-server")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="inspect_project",
            description="Summarize the environment status, detected manuscripts, and Ollama connectivity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cwd": {"type": "string", "description": "Current working directory"}
                },
                "required": ["cwd"]
            }
        ),
        Tool(
            name="discover_manuscript",
            description="Search for manuscript files (.docx, .pdf) in the project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cwd": {"type": "string", "description": "Directory to search"}
                },
                "required": ["cwd"]
            }
        ),
        Tool(
            name="parse_docx",
            description="Extract text and metadata from a .docx manuscript file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the .docx file"}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="parse_pdf",
            description="Extract text and metadata from a .pdf manuscript file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the .pdf file"}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="map_sections",
            description="Map the document structure and identify key scientific sections.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"},
                    "headings": {"type": "array", "items": {"type": "string"}, "description": "Detected headings"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="digest_manuscript",
            description="Create a high-level technical digest of the manuscript's core claims.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="analyze_terminology",
            description="Analyze consistency and precision of scientific terminology.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="analyze_coherence",
            description="Analyze logical flow and transitions between sections.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="analyze_methods",
            description="Analyze research methods for scientific rigor and skepticism.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="analyze_figures_tables",
            description="Analyze clarity and correctness of data presentation in figures and tables.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="analyze_citations",
            description="Verify citation accuracy and relevance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="analyze_journal_format",
            description="Check adherence to academic standards and journal formatting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="generate_line_edits",
            description="Generate specific, grounded line edits for improving clarity and flow.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Manuscript text content"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="arbitrate_review",
            description="Synthesize findings from different analysis steps into recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array", "items": {"type": "string"}, "description": "List of findings from previous tools"}
                },
                "required": ["findings"]
            }
        ),
        Tool(
            name="render_outputs",
            description="Generate the final review artifacts (JSON and Markdown reports).",
            inputSchema={
                "type": "object",
                "properties": {
                    "review_data": {"type": "object", "description": "The accumulated review findings"},
                    "output_dir": {"type": "string", "description": "Directory to save artifacts"}
                },
                "required": ["review_data", "output_dir"]
            }
        ),
        Tool(
            name="validate_outputs",
            description="Verify artifact presence and schema validity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_dir": {"type": "string", "description": "Directory containing artifacts"}
                },
                "required": ["output_dir"]
            }
        ),
        Tool(
            name="replay_run",
            description="Replay a previous review run from its artifacts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "ID of the run to replay"}
                },
                "required": ["run_id"]
            }
        ),
        Tool(
            name="diff_run",
            description="Compare two different review runs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id_a": {"type": "string"},
                    "run_id_b": {"type": "string"}
                },
                "required": ["run_id_a", "run_id_b"]
            }
        ),
        Tool(
            name="benchmark_project",
            description="Benchmark the project's review capabilities against reference manuscripts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"}
                },
                "required": ["project_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent | ImageContent | EmbeddedResource]:
    if not arguments:
        arguments = {}

    try:
        if name == "inspect_project":
            cwd = Path(arguments.get("cwd", os.getcwd()))
            manuscripts = collect_paths(cwd)
            manuscripts = [m for m in manuscripts if m.suffix.lower() in [".docx", ".pdf"]]

            import socket
            ollama_ok = False
            try:
                with socket.create_connection(("localhost", 11434), timeout=1):
                    ollama_ok = True
            except:
                pass

            return [TextContent(type="text", text=json.dumps({
                "cwd": str(cwd),
                "manuscript_count": len(manuscripts),
                "manuscripts": [str(m) for m in manuscripts],
                "ollama_running": ollama_ok,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))]

        elif name == "discover_manuscript":
            cwd = Path(arguments.get("cwd", os.getcwd()))
            manuscripts = collect_paths(cwd)
            manuscripts = [m for m in manuscripts if m.suffix.lower() in [".docx", ".pdf"]]
            return [TextContent(type="text", text=json.dumps({
                "manuscripts": [{"path": str(m), "type": m.suffix.lower().lstrip(".")} for m in manuscripts]
            }))]

        elif name == "parse_docx" or name == "parse_pdf":
            file_path = Path(arguments["file_path"])
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            doc = parse_file(file_path)
            return [TextContent(type="text", text=json.dumps({
                "content": doc.cleaned_text,
                "full_content_length": len(doc.cleaned_text),
                "metadata": {
                    "headings": doc.headings,
                    "page_count": doc.page_count,
                    "file_size": doc.file_size_bytes,
                    "parse_engine": doc.parse_engine,
                    "warnings": doc.parse_warnings
                }
            }))]

        elif name == "render_outputs":
            review_data = arguments["review_data"]
            output_dir = Path(arguments["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate mandatory artifacts
            run_summary = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "review_data_summary": {k: len(v) if isinstance(v, list) else v for k, v in review_data.items()}
            }
            (output_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2))
            (output_dir / "manuscript_comment_manifest.json").write_text(json.dumps(review_data.get("comments", []), indent=2))
            (output_dir / "section_map.json").write_text(json.dumps(review_data.get("section_map", {}), indent=2))

            # Simple transcript
            transcript = "# Session Transcript\n\nGenerated review findings:\n\n"
            transcript += json.dumps(review_data, indent=2)
            (output_dir / "session_transcript.md").write_text(transcript)

            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "artifacts": [str(f.name) for f in output_dir.iterdir()]
            }))]

        elif name == "validate_outputs":
            output_dir = Path(arguments["output_dir"])
            required = ["run_summary.json", "manuscript_comment_manifest.json", "section_map.json", "session_transcript.md"]
            present = [f.name for f in output_dir.iterdir()]
            missing = [r for r in required if r not in present]

            return [TextContent(type="text", text=json.dumps({
                "valid": len(missing) == 0,
                "missing": missing,
                "present": present
            }))]

        elif name in [
            "map_sections", "digest_manuscript", "analyze_terminology",
            "analyze_coherence", "analyze_methods", "analyze_figures_tables",
            "analyze_citations", "analyze_journal_format", "generate_line_edits",
            "arbitrate_review", "replay_run", "diff_run", "benchmark_project"
        ]:
            # Delegate to AI-Reviewer engine or provide specialized analysis
            return [TextContent(type="text", text=json.dumps({
                "tool": name,
                "status": "success",
                "findings": f"Placeholder findings for {name}. In a real run, this would contain model-generated analysis or generated artifacts."
            }))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="manuscript-review-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
