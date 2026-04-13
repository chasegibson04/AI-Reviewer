import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path


ALLOWED_PROJECT_IDS = {
    "20260325163524_test-existingphactorpaper",
    "20260327051312_miniaturization_d2b",
}

BLOCKED_SNIPPETS = ("pampa", "horseshoe", "test-d2b")
BRIDGE_CALL_TIMEOUT_SECONDS = 1200


class BridgeClient:
    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self._next_id = 1

    async def send(self, method: str, params: dict):
        req_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload).encode() + b"\n")
        await self.process.stdin.drain()

        assert self.process.stdout is not None
        raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=BRIDGE_CALL_TIMEOUT_SECONDS)
        if not raw:
            raise RuntimeError("bridge returned no response")
        response = json.loads(raw.decode())
        if response.get("id") != req_id:
            raise RuntimeError(f"unexpected response id: {response}")
        if "result" not in response:
            raise RuntimeError(f"bridge call failed: {response}")
        return response

    async def initialize(self):
        await self.send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "allowed-project-validator", "version": "1.0.0"},
            },
        )

    async def call_tool(self, name: str, arguments: dict):
        response = await self.send("tools/call", {"name": name, "arguments": arguments})
        content = response["result"].get("content", [])
        if not content:
            raise RuntimeError(f"empty tool response: {name}")
        return json.loads(content[0]["text"])


def ensure_allowed_path(path: Path) -> None:
    path_text = str(path)
    lowered = path_text.lower()
    if any(token in lowered for token in BLOCKED_SNIPPETS):
        raise RuntimeError(f"Blocked project path: {path}")
    if not any(project_id in path_text for project_id in ALLOWED_PROJECT_IDS):
        raise RuntimeError(f"Non-allowed project path: {path}")


async def run_deep_validation(
    client: BridgeClient,
    manuscript: Path,
    *,
    profile: str,
    reasoning_mode: str,
    output_dir: Path,
):
    parse_tool = "parse_docx" if manuscript.suffix.lower() == ".docx" else "parse_pdf"
    parsed = await client.call_tool(parse_tool, {"file_path": str(manuscript.resolve())})
    parsed_content = str(parsed.get("content", "") or "")
    if len(parsed_content) > 28000:
        parsed_content = (
            parsed_content[:18000]
            + "\n\n[...validation payload truncated for runtime stability...]\n\n"
            + parsed_content[-8000:]
        )

    section_map = await client.call_tool("map_sections", {"content": parsed_content})
    digest = await client.call_tool("digest_manuscript", {"content": parsed_content})

    model_target = "gemma4:31b" if reasoning_mode == "gemma_single" else "local_moe"
    deep = await client.call_tool(
        "generate_deep_review",
        {
            "content": parsed_content,
            "profile": profile,
            "reasoning_mode": reasoning_mode,
            "model_target": model_target,
            "section_map": section_map.get("section_map", {}),
            "manuscript_path": str(manuscript.resolve()),
            "allow_abstract_fallback": True,
        },
    )

    findings = []
    for row in deep.get("comment_details", []):
        if isinstance(row, dict):
            issue = str(row.get("issue", "")).strip()
            if issue:
                findings.append(issue)
    arbitration = await client.call_tool("arbitrate_review", {"findings": findings, "profile": profile})

    routing = deep.get("routing_trace", {})
    reports = deep.get("reports", {})
    review_data = {
        "profile": profile,
        "mode": "deep_review",
        "model_target": routing.get("model_target", model_target),
        "reasoning_mode_requested": routing.get("reasoning_mode_requested", reasoning_mode),
        "reasoning_mode_effective": routing.get("reasoning_mode_effective", reasoning_mode),
        "degraded": bool(routing.get("degraded", False)),
        "fallback_reason": routing.get("fallback_reason", ""),
        "comments": deep.get("comments", []),
        "comment_details": deep.get("comment_details", []),
        "suggested_changes": deep.get("suggested_changes", []),
        "section_map": section_map.get("section_map", {}),
        "routing_trace": routing,
        "digest": digest,
        "terminology_definition_report": reports.get("terminology", {}),
        "coherence_transition_report": reports.get("coherence", {}),
        "methods_report": reports.get("methods", {}),
        "figure_table_reference_report": reports.get("figures_tables", {}),
        "support_ingest_report": reports.get("support_ingest_report", {}),
        "support_usage_ledger": reports.get("support_usage_ledger", {}),
        "support_ingest_cache_index": reports.get("support_ingest_cache_preview", []),
        "assertion_ledger": reports.get("assertion_ledger", {}),
        "claim_verification_summary": reports.get("claim_verification_summary", {}),
        "citation_verification_ledger": reports.get("citation_verification_ledger", reports.get("citations", {})),
        "format_compliance_report": reports.get("journal_format", {}),
        "arbitration": arbitration,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    await client.call_tool("render_outputs", {"review_data": review_data, "output_dir": str(output_dir)})
    validation = await client.call_tool("validate_outputs", {"output_dir": str(output_dir)})
    replay = await client.call_tool("replay_run", {"run_id": str(output_dir)})

    return {
        "manuscript": str(manuscript),
        "output_dir": str(output_dir),
        "validation": validation,
        "run_summary": replay.get("run_summary", {}),
        "routing_trace": routing,
        "support_ingest_report": reports.get("support_ingest_report", {}),
        "claim_verification_summary": reports.get("claim_verification_summary", {}),
        "citation_status": reports.get("citation_verification_ledger", {}).get("status"),
        "comment_samples": (deep.get("comments", []) or [])[:5],
    }


async def main():
    project_root = Path(__file__).resolve().parents[1]
    allowed_root = (project_root / ".." / "projects").resolve()

    manuscript_a = allowed_root / "20260325163524_test-existingphactorpaper" / "materials" / "manuscript" / "designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf"
    manuscript_b = allowed_root / "20260327051312_miniaturization_d2b" / "materials" / "manuscript" / "s44160-023-00351-1.pdf"

    for manuscript in (manuscript_a, manuscript_b):
        ensure_allowed_path(manuscript)
        if not manuscript.exists():
            raise FileNotFoundError(f"Missing manuscript: {manuscript}")

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_root = project_root / "test_outputs" / "allowed_project_validation" / stamp
    out_root.mkdir(parents=True, exist_ok=True)

    process = await asyncio.create_subprocess_exec(
        "python3",
        "src/bridge/python/review_mcp_server.py",
        cwd=str(project_root),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=4 * 1024 * 1024,
        env={**os.environ},
    )
    try:
        client = BridgeClient(process)
        await client.initialize()

        runs = []
        runs.append(
            await run_deep_validation(
                client,
                manuscript_a,
                profile="local_moe",
                reasoning_mode="moe",
                output_dir=out_root / "moe_allowed_project_a",
            )
        )
        runs.append(
            await run_deep_validation(
                client,
                manuscript_b,
                profile="one_big_model",
                reasoning_mode="gemma_single",
                output_dir=out_root / "gemma_single_allowed_project_b",
            )
        )

        index = {
            "created_at": datetime.now(UTC).isoformat(),
            "allowed_projects_only": sorted(ALLOWED_PROJECT_IDS),
            "runs": runs,
        }
        (out_root / "validation_index.json").write_text(
            json.dumps(index, indent=2), encoding="utf-8"
        )
        print(str(out_root))
    finally:
        process.terminate()
        await process.wait()


if __name__ == "__main__":
    asyncio.run(main())
