import json
import asyncio
from pathlib import Path

async def test_mcp():
    process = await asyncio.create_subprocess_exec(
        "python3", "src/bridge/python/review_mcp_server.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"PYTHONPATH": "../../.."}
    )

    async def send_json(obj):
        process.stdin.write(json.dumps(obj).encode() + b"\n")
        await process.stdin.drain()

    # Initialize
    print("Sending initialize...")
    await send_json({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    })

    response = await process.stdout.readline()
    print("Init response:", response.decode())

    # Call inspect_project
    await send_json({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "inspect_project",
            "arguments": {"cwd": str(Path.cwd())}
        }
    })

    response = await process.stdout.readline()
    print("inspect_project response:", response.decode())

    # Call parse_pdf
    print("Sending parse_pdf...")
    await send_json({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "parse_pdf",
            "arguments": {"file_path": str(Path("../example_papers/gan_diffusion.pdf").absolute())}
        }
    })

    response = await process.stdout.readline()
    print("parse_pdf response:", response.decode()[:500] + "...")

    # Call render_outputs
    await send_json({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "render_outputs",
            "arguments": {
                "review_data": {"comments": ["Test comment"], "section_map": {"Abstract": "p1"}},
                "output_dir": "test_outputs"
            }
        }
    })
    response = await process.stdout.readline()
    print("render_outputs response:", response.decode())

    # Call validate_outputs
    await send_json({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "validate_outputs",
            "arguments": {"output_dir": "test_outputs"}
        }
    })
    response = await process.stdout.readline()
    print("validate_outputs response:", response.decode())

    process.terminate()
    await process.wait()

if __name__ == "__main__":
    asyncio.run(test_mcp())
