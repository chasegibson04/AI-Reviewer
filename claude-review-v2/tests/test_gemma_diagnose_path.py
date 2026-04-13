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
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload).encode() + b"\n")
        await self.process.stdin.drain()
        assert self.process.stdout is not None
        raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=240)
        assert raw
        response = json.loads(raw.decode())
        assert response.get("id") == req_id
        return response

    async def initialize(self):
        response = await self.send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest-gemma-diagnose", "version": "1.0.0"},
            },
        )
        assert "result" in response

    async def call_tool(self, name: str, arguments: dict):
        response = await self.send("tools/call", {"name": name, "arguments": arguments})
        assert "result" in response
        payload = json.loads(response["result"]["content"][0]["text"])
        return payload


async def _run():
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
        payload = await client.call_tool("diagnose_model", {"model": "gemma4:31b"})
        for key in [
            "short_prompt",
            "medium_prompt",
            "json_prompt",
            "ingest_prompt",
            "citation_prompt",
            "long_review_prompt",
        ]:
            assert key in payload
            assert "status" in payload[key]
    finally:
        process.terminate()
        await process.wait()


def test_gemma_diagnose_path():
    asyncio.run(_run())
