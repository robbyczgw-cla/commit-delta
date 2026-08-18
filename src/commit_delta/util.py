from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Sequence


class CommitDeltaError(RuntimeError):
    """User-facing error with a short message."""


DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")


def parse_duration(text: str) -> float:
    """Parse '60', '60s', '2m', '1h', '500ms' into seconds."""
    match = DURATION_RE.match(text)
    if not match:
        raise CommitDeltaError(f"invalid duration: {text!r}")
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit in ("", "s", "sec", "secs", "second", "seconds"):
        return value
    if unit in ("ms", "msec"):
        return value / 1000.0
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return value * 60.0
    if unit in ("h", "hr", "hrs", "hour", "hours"):
        return value * 3600.0
    raise CommitDeltaError(f"invalid duration unit in {text!r}")


def run_git(
    args: Sequence[str],
    *,
    cwd: str | Path,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise CommitDeltaError(f"git {' '.join(args)} failed: {err}")
    return proc


def git_text(args: Sequence[str], *, cwd: str | Path) -> str:
    return run_git(args, cwd=cwd).stdout


def find_repo(start: str | Path | None = None) -> Path:
    cwd = Path(start or os.getcwd()).resolve()
    proc = run_git(
        ["rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
    )
    if proc.returncode != 0:
        raise CommitDeltaError("not a git repository")
    return Path(proc.stdout.strip()).resolve()


def path_matches(path: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return False
    posix = path.replace(os.sep, "/")
    for raw in patterns:
        pat = raw.replace(os.sep, "/").lstrip("./")
        if not pat:
            continue
        if posix == pat or posix.startswith(pat.rstrip("/") + "/"):
            return True
        if Path(posix).match(pat):
            return True
        if Path(posix).name == pat:
            return True
    return False


def should_keep(path: str, include: Sequence[str], exclude: Sequence[str]) -> bool:
    if include and not path_matches(path, include):
        return False
    if exclude and path_matches(path, exclude):
        return False
    return True


def format_hunk_set(ids: Sequence[str], limit: int = 8) -> str:
    if not ids:
        return "{}"
    shown = list(ids[:limit])
    extra = len(ids) - len(shown)
    body = ", ".join(shown)
    if extra:
        body += f", +{extra} more"
    return "{" + body + "}"
