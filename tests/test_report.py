from __future__ import annotations

import json

from commit_delta.report import format_json, format_log, format_report, result_to_dict
from commit_delta.types import (
    FileDiff,
    FileKind,
    Hunk,
    Outcome,
    ReductionResult,
    ReductionStats,
    Snapshot,
    Trial,
    Witness,
)


def _hunk(path: str = "a.py", idx: int = 1) -> Hunk:
    return Hunk(
        id=f"{path}#{idx}",
        path=path,
        kind=FileKind.MODIFY,
        old_start=1,
        old_count=1,
        new_start=1,
        new_count=1,
        section="def f",
        body=("-x", "+y"),
        file_index=0,
        hunk_index=idx,
    )


def _result(
    hunks: list[Hunk] | None = None,
    witnesses: list[Witness] | None = None,
) -> ReductionResult:
    hunks = hunks if hunks is not None else [_hunk()]
    snap = Snapshot(
        repo="/tmp/repo",
        head="deadbeef",
        files=[FileDiff(h.path, FileKind.MODIFY, [h]) for h in hunks],
    )
    return ReductionResult(
        snapshot=snap,
        minimal=hunks,
        stats=ReductionStats(
            input_files=3,
            input_hunks=10,
            input_lines=40,
            output_files=len({h.path for h in hunks}),
            output_hunks=len(hunks),
            output_lines=sum(h.changed_line_count for h in hunks),
            trials=4,
            cache_hits=1,
            pass_n=1,
            fail_n=2,
            unresolved_n=1,
            elapsed_s=1.25,
        ),
        trials=[
            Trial(1, "HEAD", Outcome.PASS, 0.1, "exit 0"),
            Trial(2, "working-tree", Outcome.FAIL, 0.2, "exit 1"),
        ],
        witnesses=witnesses
        or [Witness(removed_id="(empty / HEAD)", outcome=Outcome.PASS)],
        notes=["uniqueness is not guaranteed"],
    )


def test_format_report_single_hunk():
    text = format_report(_result())
    assert "a.py" in text
    assert "hunk 1" in text
    assert "1-minimal" in text
    assert "10 -> 1 hunks" in text


def test_format_report_empty_minimal():
    text = format_report(_result(hunks=[]))
    assert "(empty)" in text


def test_format_report_not_one_minimal():
    hunks = [_hunk("a.py", 1), _hunk("b.py", 1)]
    result = _result(
        hunks=hunks,
        witnesses=[
            Witness("a.py#1", Outcome.PASS),
            Witness("b.py#1", Outcome.FAIL),
        ],
    )
    text = format_report(result)
    assert "1-minimal: no" in text


def test_format_report_one_minimal_with_unresolved_witness():
    hunks = [_hunk("a.py", 1), _hunk("b.py", 1)]
    result = _result(
        hunks=hunks,
        witnesses=[
            Witness("a.py#1", Outcome.PASS),
            Witness("b.py#1", Outcome.UNRESOLVED),
        ],
    )
    text = format_report(result)
    assert "1-minimal: yes" in text


def test_json_roundtrip_shape():
    data = json.loads(format_json(_result()))
    assert data["version"] == "0.1.0"
    assert data["unique_not_guaranteed"] is True
    assert data["one_minimal"] is True
    assert data["minimal"][0]["id"] == "a.py#1"
    assert data["stats"]["input_hunks"] == 10
    assert "diff --git" in data["patch"]
    assert data["head"] == "deadbeef"
    dumped = result_to_dict(_result())
    assert dumped["trials"][0]["label"] == "HEAD"


def test_format_log_contains_trials():
    log = format_log(_result())
    assert "HEAD" in log
    assert "PASS" in log
