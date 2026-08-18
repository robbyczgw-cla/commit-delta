from __future__ import annotations

import json
from typing import Any

from commit_delta import __version__
from commit_delta.apply import render_patch
from commit_delta.types import Outcome, ReductionResult


def format_report(result: ReductionResult) -> str:
    lines: list[str] = []
    lines.append("Minimal failure-inducing change set:")
    lines.append("")
    if not result.minimal:
        lines.append("(empty)")
    else:
        current_path = None
        for hunk in result.minimal:
            if hunk.path != current_path:
                if current_path is not None:
                    lines.append("")
                lines.append(hunk.path)
                current_path = hunk.path
            extra = f"  {hunk.section}" if hunk.section else ""
            lines.append(f"  hunk {hunk.hunk_index}{extra}")
            for preview in hunk.preview(limit=4):
                lines.append(f"    {preview}")
    lines.append("")
    stats = result.stats
    lines.append(
        f"Full working tree: FAIL  "
        f"{stats.input_files} files, {stats.input_hunks} hunks, "
        f"{stats.input_lines} changed lines"
    )
    lines.append(
        f"Reduced patch:     FAIL  "
        f"{stats.output_files} files, {stats.output_hunks} hunks, "
        f"{stats.output_lines} changed lines"
    )
    if stats.input_hunks:
        pct = 100.0 * (1.0 - stats.hunk_ratio)
        lines.append(
            f"Reduction:         {stats.input_hunks} -> {stats.output_hunks} hunks "
            f"({pct:.0f}% fewer), "
            f"{stats.input_lines} -> {stats.output_lines} lines"
        )
    lines.append("")
    lines.append("Removing any remaining hunk:")
    interesting = [w for w in result.witnesses if w.removed_id != "(empty / HEAD)"]
    if not interesting:
        lines.append("  (single remaining hunk; HEAD already verified PASS)")
    else:
        still_fail = False
        for w in interesting:
            lines.append(f"  without {w.removed_id}: {w.outcome.value}")
            if w.outcome is Outcome.FAIL:
                still_fail = True
        if still_fail:
            lines.append(
                "  1-minimal: no (a leftover hunk can be dropped and it still FAILs)"
            )
        else:
            lines.append(
                "  1-minimal: yes (dropping any leftover hunk PASSes or will not run)"
            )
    lines.append("")
    lines.append(
        f"Trials: {stats.trials}  "
        f"(PASS {stats.pass_n}, FAIL {stats.fail_n}, "
        f"UNRESOLVED {stats.unresolved_n}, cache hits {stats.cache_hits})"
    )
    lines.append(f"Elapsed: {stats.elapsed_s:.2f}s")
    if result.notes:
        lines.append("")
        for note in result.notes:
            lines.append(f"Note: {note}")
    lines.append("")
    lines.append(
        "This is a minimal failure-inducing change set, not 'the' cause. "
        "Multiple hunks may interact; another 1-minimal subset may also fail."
    )
    return "\n".join(lines) + "\n"


def result_to_dict(result: ReductionResult) -> dict[str, Any]:
    interesting = [w for w in result.witnesses if w.removed_id != "(empty / HEAD)"]
    one_minimal = not any(w.outcome is Outcome.FAIL for w in interesting)
    stats = result.stats
    return {
        "version": __version__,
        "unique_not_guaranteed": True,
        "one_minimal": one_minimal,
        "minimal": [
            {
                "id": h.id,
                "path": h.path,
                "hunk_index": h.hunk_index,
                "kind": h.kind.value,
                "changed_lines": h.changed_line_count,
                "section": h.section,
                "preview": h.preview(limit=8),
            }
            for h in result.minimal
        ],
        "stats": {
            "input_files": stats.input_files,
            "input_hunks": stats.input_hunks,
            "input_lines": stats.input_lines,
            "output_files": stats.output_files,
            "output_hunks": stats.output_hunks,
            "output_lines": stats.output_lines,
            "hunk_ratio": stats.hunk_ratio,
            "line_ratio": stats.line_ratio,
            "trials": stats.trials,
            "cache_hits": stats.cache_hits,
            "pass": stats.pass_n,
            "fail": stats.fail_n,
            "unresolved": stats.unresolved_n,
            "elapsed_s": stats.elapsed_s,
        },
        "witnesses": [
            {"removed_id": w.removed_id, "outcome": w.outcome.value, "detail": w.detail}
            for w in result.witnesses
        ],
        "trials": [
            {
                "n": t.n,
                "label": t.label,
                "outcome": t.outcome.value,
                "elapsed_s": t.elapsed_s,
                "detail": t.detail,
                "cached": t.cached,
                "exit_code": t.exit_code,
            }
            for t in result.trials
        ],
        "notes": list(result.notes),
        "patch": render_patch(result.minimal),
        "head": result.snapshot.head,
        "repo": result.snapshot.repo,
    }


def format_json(result: ReductionResult) -> str:
    return json.dumps(result_to_dict(result), indent=2) + "\n"


def format_log(result: ReductionResult) -> str:
    lines = ["# commit-delta execution log", ""]
    for trial in result.trials:
        cache = " cache" if trial.cached else ""
        lines.append(
            f"{trial.n:4d}  {trial.outcome.value:<11}  "
            f"{trial.elapsed_s:7.2f}s  {trial.label}  {trial.detail}{cache}"
        )
    return "\n".join(lines) + "\n"
