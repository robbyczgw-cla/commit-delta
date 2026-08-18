from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=True,
    )


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-b", "main"], cwd=path)
    run(["git", "config", "user.name", "commit-delta-fixture"], cwd=path)
    run(["git", "config", "user.email", "fixture@example.com"], cwd=path)
    run(["git", "config", "commit.gpgsign", "false"], cwd=path)
    return path


def write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)


def commit_all(repo: Path, message: str) -> None:
    run(["git", "add", "-A"], cwd=repo)
    run(["git", "commit", "-m", message], cwd=repo)


def write_reproduce(repo: Path, python_body: str) -> None:
    script = f"""#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure the worktree root is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))

{python_body}
"""
    write(repo / "reproduce.sh", script, mode=0o755)
