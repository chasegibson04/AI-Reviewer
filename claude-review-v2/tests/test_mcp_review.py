import asyncio
import json
import os
from pathlib import Path


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
        raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=20)
        assert raw, "bridge returned no response"
        response = json.loads(raw.decode())
        assert response.get("id") == req_id
        return response

    async def initialize(self):
        response = await self.send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest-client", "version": "1.0.0"},
            },
        )
        assert "result" in response

    async def call_tool(self, name: str, arguments: dict):
        response = await self.send(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        assert "result" in response
        content = response["result"].get("content", [])
        assert content and content[0].get("type") == "text"
        payload = json.loads(content[0]["text"])
        return payload


async def _run_bridge_test():
    project_root = Path(__file__).resolve().parents[1]
    process = await asyncio.create_subprocess_exec(
        "python3",
        "src/bridge/python/review_mcp_server.py",
        cwd=str(project_root),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **{"PYTHONPATH": str(project_root.parent)}},
    )

    try:
        client = BridgeClient(process)
        await client.initialize()

        inspect_payload = await client.call_tool(
            "inspect_project", {"cwd": str(project_root)}
        )
        assert "manuscript_count" in inspect_payload
        assert "blocked_project_policy" in inspect_payload

        parse_payload = await client.call_tool(
            "parse_pdf",
            {
                "file_path": str(
                    (project_root.parent / "example_papers" / "gan_diffusion.pdf").resolve()
                )
            },
        )
        assert parse_payload["full_content_length"] > 1000
        assert "content" in parse_payload

        section_payload = await client.call_tool(
            "map_sections", {"content": parse_payload["content"]}
        )
        assert section_payload.get("section_count", 0) >= 1

        methods_payload = await client.call_tool(
            "analyze_methods", {"content": parse_payload["content"]}
        )
        assert "skepticism_score" in methods_payload

        edits_payload = await client.call_tool(
            "generate_line_edits", {"content": parse_payload["content"]}
        )
        assert isinstance(edits_payload.get("line_edits"), list)

        output_dir = project_root / "test_outputs" / "pytest_bridge_run_a"
        output_dir.mkdir(parents=True, exist_ok=True)
        render_payload = await client.call_tool(
            "render_outputs",
            {
                "review_data": {
                    "profile": "balanced_local",
                    "comments": [
                        "Methods section should clarify sampling strategy.",
                        "Discussion overstates causality for observed correlation.",
                    ],
                    "section_map": section_payload["section_map"],
                    "terminology_definition_report": {
                        "defined_terms": ["GAN", "diffusion"],
                        "findings": ["Define GAN acronym at first use."],
                    },
                },
                "output_dir": str(output_dir),
            },
        )
        assert render_payload.get("status") == "success"

        validate_payload = await client.call_tool(
            "validate_outputs", {"output_dir": str(output_dir)}
        )
        assert validate_payload.get("valid") is True

        replay_payload = await client.call_tool(
            "replay_run", {"run_id": str(output_dir)}
        )
        assert "run_summary" in replay_payload

        output_dir_b = project_root / "test_outputs" / "pytest_bridge_run_b"
        output_dir_b.mkdir(parents=True, exist_ok=True)
        await client.call_tool(
            "render_outputs",
            {
                "review_data": {
                    "profile": "deep_local",
                    "comments": [
                        "Add explicit baseline description in Methods.",
                    ],
                    "section_map": section_payload["section_map"],
                },
                "output_dir": str(output_dir_b),
            },
        )

        diff_payload = await client.call_tool(
            "diff_run",
            {
                "run_id_a": str(output_dir),
                "run_id_b": str(output_dir_b),
            },
        )
        assert "comment_delta" in diff_payload

        blocked_payload = await client.call_tool(
            "benchmark_project", {"project_id": "pampa-j-chemed", "cwd": str(project_root.parent)}
        )
        assert "error" in blocked_payload

    finally:
        process.terminate()
        await process.wait()



def test_bridge_end_to_end():
    asyncio.run(_run_bridge_test())
