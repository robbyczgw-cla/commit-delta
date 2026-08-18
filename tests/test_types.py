from __future__ import annotations

from commit_delta.types import (
    FileDiff,
    FileKind,
    Hunk,
    Outcome,
    ReductionStats,
    Snapshot,
    hunk_ids,
)


def _hunk(**kwargs) -> Hunk:
    defaults = dict(
        id="f#1",
        path="f.py",
        kind=FileKind.MODIFY,
        old_start=1,
        old_count=2,
        new_start=1,
        new_count=2,
        section="def f",
        body=("-old", "+new", " keep", "\\ No newline at end of file"),
        file_index=0,
        hunk_index=1,
    )
    defaults.update(kwargs)
    return Hunk(**defaults)


def test_hunk_line_splits_ignore_no_newline_marker():
    h = _hunk()
    assert h.old_lines == ["old", "keep"]
    assert h.new_lines == ["new", "keep"]
    assert h.added_line_count == 1
    assert h.deleted_line_count == 1
    assert h.changed_line_count == 2
    assert h.preview(limit=1) == ["-old"]


def test_snapshot_hunks_for():
    a = _hunk(id="a#1", path="a.py")
    b = _hunk(id="b#1", path="b.py", hunk_index=1)
    snap = Snapshot(
        repo="/tmp/x",
        head="abc",
        files=[
            FileDiff("a.py", FileKind.MODIFY, [a]),
            FileDiff("b.py", FileKind.MODIFY, [b]),
        ],
    )
    assert hunk_ids(snap.hunks) == ("a#1", "b#1")
    assert snap.hunks_for(["b#1"]) == [b]


def test_ratio_zero_inputs():
    empty = ReductionStats(
        input_files=0,
        input_hunks=0,
        input_lines=0,
        output_files=0,
        output_hunks=0,
        output_lines=0,
        trials=0,
        cache_hits=0,
        pass_n=0,
        fail_n=0,
        unresolved_n=0,
        elapsed_s=0.0,
    )
    assert empty.hunk_ratio == 1.0
    assert empty.line_ratio == 1.0
    filled = ReductionStats(
        input_files=2,
        input_hunks=10,
        input_lines=20,
        output_files=1,
        output_hunks=2,
        output_lines=4,
        trials=3,
        cache_hits=1,
        pass_n=1,
        fail_n=1,
        unresolved_n=1,
        elapsed_s=1.0,
    )
    assert filled.hunk_ratio == 0.2
    assert filled.line_ratio == 0.2
    assert Outcome.FAIL.value == "FAIL"
