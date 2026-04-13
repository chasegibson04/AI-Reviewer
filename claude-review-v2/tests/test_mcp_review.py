import asyncio
import json
import os
from pathlib import Path

BRIDGE_CALL_TIMEOUT_SECONDS = 420


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
        raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=BRIDGE_CALL_TIMEOUT_SECONDS)
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
        env={**os.environ},
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
                    (project_root / "fixtures" / "manuscripts" / "gan_diffusion.pdf").resolve()
                )
            },
        )
        assert parse_payload["full_content_length"] > 1000
        assert "content" in parse_payload
        parsed_content = str(parse_payload["content"])
        if len(parsed_content) > 14000:
            parsed_content = (
                parsed_content[:9000]
                + "\n\n[...pytest deep-review payload truncated for runtime stability...]\n\n"
                + parsed_content[-3000:]
            )

        section_payload = await client.call_tool(
            "map_sections", {"content": parsed_content}
        )
        assert section_payload.get("section_count", 0) >= 1

        methods_payload = await client.call_tool(
            "analyze_methods", {"content": parsed_content}
        )
        assert "skepticism_score" in methods_payload

        model_diag_payload = await client.call_tool(
            "diagnose_model", {"model": "gemma4:31b"}
        )
        assert "short_prompt" in model_diag_payload
        assert "medium_prompt" in model_diag_payload
        assert "json_prompt" in model_diag_payload
        assert "ingest_prompt" in model_diag_payload
        assert "citation_prompt" in model_diag_payload
        assert "long_review_prompt" in model_diag_payload

        edits_payload = await client.call_tool(
            "generate_line_edits", {"content": parsed_content}
        )
        assert isinstance(edits_payload.get("line_edits"), list)

        deep_payload = await client.call_tool(
            "generate_deep_review",
            {
                "content": parsed_content,
                "profile": "local_moe",
                "reasoning_mode": "moe",
                "model_target": "local_moe",
                "section_map": section_payload["section_map"],
                "manuscript_path": str(
                    (project_root / "fixtures" / "manuscripts" / "gan_diffusion.pdf").resolve()
                ),
            },
        )
        assert "comments" in deep_payload
        assert "routing_trace" in deep_payload
        assert "model_plan" in deep_payload
        reports = deep_payload.get("reports", {})
        assert "support_ingest_report" in reports
        assert "citation_verification_ledger" in reports

        output_dir = project_root / "test_outputs" / "pytest_bridge_run_a"
        output_dir.mkdir(parents=True, exist_ok=True)
        render_payload = await client.call_tool(
            "render_outputs",
            {
                "review_data": {
                    "profile": "balanced_local",
                    "comments": deep_payload.get("comments", []),
                    "comment_details": deep_payload.get("comment_details", []),
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
                    "profile": "one_big_model",
                    "mode": "single big-model review",
                    "model_target": "gemma4:31b",
                    "comments": [
                        "Add explicit baseline description in Methods.",
                    ],
                    "section_map": section_payload["section_map"],
                },
                "output_dir": str(output_dir_b),
            },
        )

        replay_b_payload = await client.call_tool(
            "replay_run", {"run_id": str(output_dir_b)}
        )
        run_summary_b = replay_b_payload.get("run_summary", {})
        assert run_summary_b.get("profile") == "one_big_model"
        assert run_summary_b.get("mode") == "single big-model review"
        assert run_summary_b.get("model_target") == "gemma4:31b"

        diff_payload = await client.call_tool(
            "diff_run",
            {
                "run_id_a": str(output_dir),
                "run_id_b": str(output_dir_b),
            },
        )
        assert "comment_delta" in diff_payload

        blocked_payload = await client.call_tool(
            "benchmark_project", {"project_id": "pampa-j-chemed", "cwd": str(project_root)}
        )
        assert "error" in blocked_payload

    finally:
        process.terminate()
        await process.wait()



def test_bridge_end_to_end():
    asyncio.run(_run_bridge_test())
