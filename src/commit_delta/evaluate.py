from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from commit_delta.heuristic import heuristic_unresolved
from commit_delta.types import Outcome


# Match git bisect run: 0 = good/PASS, 125 = skip/UNRESOLVED, else bad/FAIL.
UNRESOLVED_EXIT = 125


@dataclass
class CommandResult:
    outcome: Outcome
    exit_code: int | None
    elapsed_s: float
    detail: str
    stdout: str = ""
    stderr: str = ""


def run_command(
    command: Sequence[str],
    *,
    cwd: str | Path,
    timeout: float | None,
    env: dict[str, str] | None = None,
    heuristics: bool = True,
) -> CommandResult:
    start = time.monotonic()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            list(command),
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            env=merged_env,
            check=False,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            outcome=Outcome.UNRESOLVED,
            exit_code=None,
            elapsed_s=time.monotonic() - start,
            detail=f"command not found: {exc.filename or command[0]}",
        )
    except subprocess.TimeoutExpired as exc:
        _kill_session(exc)
        return CommandResult(
            outcome=Outcome.UNRESOLVED,
            exit_code=None,
            elapsed_s=time.monotonic() - start,
            detail=f"timeout after {timeout}s",
            stdout=_decode(exc.stdout),
            stderr=_decode(exc.stderr),
        )
    except OSError as exc:
        return CommandResult(
            outcome=Outcome.UNRESOLVED,
            exit_code=None,
            elapsed_s=time.monotonic() - start,
            detail=f"exec error: {exc}",
        )

    elapsed = time.monotonic() - start
    code = proc.returncode
    if code == 0:
        outcome = Outcome.PASS
        detail = "exit 0"
    elif code == UNRESOLVED_EXIT:
        outcome = Outcome.UNRESOLVED
        detail = "exit 125 (unresolved)"
    else:
        hint = heuristic_unresolved(proc.stdout or "", proc.stderr or "") if heuristics else None
        if hint:
            outcome = Outcome.UNRESOLVED
            detail = f"{hint} (exit {code})"
        else:
            outcome = Outcome.FAIL
            detail = f"exit {code}"
    return CommandResult(
        outcome=outcome,
        exit_code=code,
        elapsed_s=elapsed,
        detail=detail,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def confirm_outcome(
    run_once: callable,
    confirm: int,
) -> CommandResult:
    """Run `confirm` times. Mixed PASS/FAIL is UNRESOLVED (flaky).

    A FAIL is only accepted if every confirmation is FAIL.
    A PASS is only accepted if every confirmation is PASS.
    Any UNRESOLVED, or a mix, is UNRESOLVED.
    """
    confirm = max(1, int(confirm))
    results: list[CommandResult] = []
    for _ in range(confirm):
        results.append(run_once())
    outcomes = {r.outcome for r in results}
    last = results[-1]
    elapsed = sum(r.elapsed_s for r in results)
    if outcomes == {Outcome.FAIL}:
        return CommandResult(
            outcome=Outcome.FAIL,
            exit_code=last.exit_code,
            elapsed_s=elapsed,
            detail=f"FAIL {confirm}/{confirm}" + (f" ({last.detail})" if confirm == 1 else ""),
            stdout=last.stdout,
            stderr=last.stderr,
        )
    if outcomes == {Outcome.PASS}:
        return CommandResult(
            outcome=Outcome.PASS,
            exit_code=last.exit_code,
            elapsed_s=elapsed,
            detail=f"PASS {confirm}/{confirm}" + (f" ({last.detail})" if confirm == 1 else ""),
            stdout=last.stdout,
            stderr=last.stderr,
        )
    if outcomes == {Outcome.UNRESOLVED}:
        return CommandResult(
            outcome=Outcome.UNRESOLVED,
            exit_code=last.exit_code,
            elapsed_s=elapsed,
            detail=f"UNRESOLVED {confirm}/{confirm} ({last.detail})",
            stdout=last.stdout,
            stderr=last.stderr,
        )
    counts = ", ".join(
        f"{o.value}={sum(1 for r in results if r.outcome is o)}"
        for o in (Outcome.PASS, Outcome.FAIL, Outcome.UNRESOLVED)
        if any(r.outcome is o for r in results)
    )
    return CommandResult(
        outcome=Outcome.UNRESOLVED,
        exit_code=last.exit_code,
        elapsed_s=elapsed,
        detail=f"inconsistent ({counts})",
        stdout=last.stdout,
        stderr=last.stderr,
    )


def _kill_session(exc: subprocess.TimeoutExpired) -> None:
    proc = getattr(exc, "process", None)
    pid = getattr(proc, "pid", None) if proc is not None else None
    if pid is None:
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")
