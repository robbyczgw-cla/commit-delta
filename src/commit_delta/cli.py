from __future__ import annotations

import argparse
import sys
from pathlib import Path

from commit_delta import __version__
from commit_delta.engine import Engine, EngineConfig
from commit_delta.parse import capture_snapshot
from commit_delta.report import format_json, format_log, format_report
from commit_delta.util import CommitDeltaError, find_repo, parse_duration
from commit_delta.worktree import IsolatedTree


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-delta",
        description=(
            "Find a minimal failure-inducing subset of the current "
            "dirty Git working tree. Does not modify your working tree."
        ),
        epilog="Example:  commit-delta -- ./reproduce.sh",
    )
    parser.add_argument(
        "--confirm",
        type=int,
        default=1,
        metavar="N",
        help="require N consistent outcomes before accepting FAIL/PASS (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        default="60s",
        metavar="DURATION",
        help="per-trial command timeout (default: 60s). 0 disables.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="PATH",
        help="only consider this path (repeatable; prefix or glob)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATH",
        help="ignore this path (repeatable; prefix or glob)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="print each candidate trial to stderr",
    )
    parser.add_argument(
        "--strict-exits",
        action="store_true",
        help=(
            "only trust exit codes (0=PASS, 125=UNRESOLVED, else FAIL); "
            "disable SyntaxError/ImportError traceback heuristics"
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="write the reduced patch to FILE",
    )
    parser.add_argument(
        "--log-file",
        metavar="FILE",
        help="write the detailed execution log to FILE",
    )
    parser.add_argument(
        "--json",
        metavar="FILE",
        help="write a machine-readable result JSON to FILE (for agents)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"commit-delta {__version__}",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="reproduction command after --  (exit 0=PASS, 125=UNRESOLVED, else FAIL)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    command = _extract_command(args.command)
    if not command:
        parser.error("missing command after --  (example: commit-delta -- npm test)")

    try:
        timeout = parse_duration(args.timeout)
    except CommitDeltaError as exc:
        parser.error(str(exc))
    if timeout <= 0:
        timeout = None
    if args.confirm < 1:
        parser.error("--confirm must be >= 1")

    def log(message: str) -> None:
        if args.verbose:
            print(message, file=sys.stderr, flush=True)

    try:
        repo = find_repo()
        snapshot = capture_snapshot(
            repo,
            include=args.include,
            exclude=args.exclude,
        )
        if not snapshot.hunks:
            raise CommitDeltaError(
                "working tree has no reducible tracked text changes vs HEAD"
            )
        if snapshot.skipped_binary:
            print(
                "warning: skipping binary paths: "
                + ", ".join(snapshot.skipped_binary),
                file=sys.stderr,
            )
        with IsolatedTree(repo) as tree:
            engine = Engine(
                snapshot,
                tree,
                EngineConfig(
                    command=command,
                    timeout=timeout,
                    confirm=args.confirm,
                    verbose=args.verbose,
                    heuristics=not args.strict_exits,
                    log=log,
                ),
            )
            result = engine.reduce()
            if args.output:
                engine.write_patch(result.minimal, Path(args.output))
        report = format_report(result)
        sys.stdout.write(report)
        if args.log_file:
            Path(args.log_file).write_text(format_log(result), encoding="utf-8")
        if args.json:
            Path(args.json).write_text(format_json(result), encoding="utf-8")
        return 0
    except CommitDeltaError as exc:
        print(f"commit-delta: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("commit-delta: interrupted", file=sys.stderr)
        return 130


def _extract_command(remainder: list[str]) -> list[str]:
    if remainder and remainder[0] == "--":
        return remainder[1:]
    return list(remainder)
