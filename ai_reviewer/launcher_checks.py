from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LauncherCheck:
    name: str
    ok: bool
    detail: str


def check_python() -> LauncherCheck:
    path = shutil.which("python") or shutil.which("python3")
    return LauncherCheck("python", bool(path), f"found={path}" if path else "python not found on PATH")


def check_ollama() -> LauncherCheck:
    curl = shutil.which("curl")
    if curl:
        try:
            proc = subprocess.run([curl, "-sf", "http://127.0.0.1:11434/api/version"], capture_output=True, text=True, timeout=4)
            if proc.returncode == 0:
                return LauncherCheck("ollama", True, "reachable")
        except Exception:
            pass
    try:
        import requests
        resp = requests.get("http://127.0.0.1:11434/api/version", timeout=4)
        if resp.status_code == 200:
            return LauncherCheck("ollama", True, "reachable")
    except Exception as exc:
        return LauncherCheck("ollama", False, f"unreachable: {exc}")
    return LauncherCheck("ollama", False, "unreachable")


def check_space_path_support(path: Path) -> LauncherCheck:
    has_space = " " in str(path)
    return LauncherCheck("path_spaces", True, f"space_in_path={has_space}")


def run_launcher_selfcheck(repo_root: Path) -> list[LauncherCheck]:
    checks = [
        check_python(),
        check_ollama(),
        check_space_path_support(repo_root),
    ]
    return checks


def main() -> None:
    root = Path.cwd()
    checks = run_launcher_selfcheck(root)
    payload = [c.__dict__ for c in checks]
    print(json.dumps(payload, indent=2))
    if not all(c.ok for c in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
