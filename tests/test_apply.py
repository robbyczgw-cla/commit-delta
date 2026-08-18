from __future__ import annotations

import pytest

from commit_delta.apply import ApplyError, apply_hunks_to_lines, render_patch
from commit_delta.parse import parse_unified_diff
from commit_delta.types import FileKind, Hunk


def _hunk(
    path: str,
    old_start: int,
    old_count: int,
    body: list[str],
    *,
    kind: FileKind = FileKind.MODIFY,
    hunk_index: int = 1,
    new_start: int = 1,
) -> Hunk:
    new_lines = [b[1:] for b in body if b.startswith("+") or b.startswith(" ")]
    return Hunk(
        id=f"{path}#{hunk_index}",
        path=path,
        kind=kind,
        old_start=old_start,
        old_count=old_count,
        new_start=new_start,
        new_count=len(new_lines),
        section="",
        body=tuple(body),
        file_index=0,
        hunk_index=hunk_index,
    )


def test_replace_middle():
    original = ["a", "b", "c"]
    hunk = _hunk("f", 2, 1, ["-b", "+B"])
    assert apply_hunks_to_lines(original, [hunk]) == ["a", "B", "c"]


def test_insert_after_line():
    original = ["a", "b", "c"]
    hunk = _hunk("f", 2, 0, ["+x"], new_start=3)
    assert apply_hunks_to_lines(original, [hunk]) == ["a", "b", "x", "c"]


def test_insert_at_start():
    original = ["a", "b"]
    hunk = _hunk("f", 0, 0, ["+x"], kind=FileKind.ADD, new_start=1)
    assert apply_hunks_to_lines(original, [hunk]) == ["x", "a", "b"]


def test_delete_line():
    original = ["a", "b", "c"]
    hunk = _hunk("f", 2, 1, ["-b"])
    assert apply_hunks_to_lines(original, [hunk]) == ["a", "c"]


def test_two_hunks_bottom_up():
    original = ["one", "two", "three", "four"]
    h1 = _hunk("f", 1, 1, ["-one", "+ONE"], hunk_index=1)
    h2 = _hunk("f", 4, 1, ["-four", "+FOUR"], hunk_index=2)
    assert apply_hunks_to_lines(original, [h1, h2]) == ["ONE", "two", "three", "FOUR"]
    assert apply_hunks_to_lines(original, [h1]) == ["ONE", "two", "three", "four"]
    assert apply_hunks_to_lines(original, [h2]) == ["one", "two", "three", "FOUR"]


def test_mismatch_raises():
    original = ["a", "b"]
    hunk = _hunk("f", 1, 1, ["-z", "+Z"])
    with pytest.raises(ApplyError):
        apply_hunks_to_lines(original, [hunk])


def test_empty_hunk_list_is_noop():
    assert apply_hunks_to_lines(["a"], []) == ["a"]


def test_group_by_path():
    from commit_delta.apply import group_by_path

    h1 = _hunk("a.py", 1, 1, ["-a", "+A"], hunk_index=1)
    h2 = _hunk("b.py", 1, 1, ["-b", "+B"], hunk_index=1)
    grouped = group_by_path([h1, h2, h1])
    assert set(grouped) == {"a.py", "b.py"}
    assert len(grouped["a.py"]) == 2


def test_materialize_modify_add_delete(tmp_path):
    from commit_delta.apply import materialize

    head = tmp_path / "head"
    probe = tmp_path / "probe"
    (head / "sub").mkdir(parents=True)
    (probe / "sub").mkdir(parents=True)
    (head / "sub" / "mod.py").write_text("a\nb\nc\n", encoding="utf-8")
    (probe / "sub" / "mod.py").write_text("a\nb\nc\n", encoding="utf-8")
    (head / "gone.py").write_text("dead\n", encoding="utf-8")
    (probe / "gone.py").write_text("dead\n", encoding="utf-8")

    modify = _hunk("sub/mod.py", 2, 1, ["-b", "+B"])
    added = _hunk(
        "new.py",
        0,
        0,
        ["+hello"],
        kind=FileKind.ADD,
        new_start=1,
    )
    deleted = _hunk("gone.py", 1, 1, ["-dead"], kind=FileKind.DELETE)
    materialize(probe, head, [modify, added, deleted])
    assert (probe / "sub" / "mod.py").read_text() == "a\nB\nc\n"
    assert (probe / "new.py").read_text() == "hello\n"
    assert not (probe / "gone.py").exists()


def test_render_add_and_delete_headers():
    from commit_delta.parse import _number_hunks

    add_diff = """\
diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1 @@
+hi
"""
    files, _, _ = parse_unified_diff(add_diff)
    _number_hunks(files)
    text = render_patch(files[0].hunks)
    assert "new file mode" in text
    assert "+hi" in text

    del_diff = """\
diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1 +0,0 @@
-bye
"""
    files, _, _ = parse_unified_diff(del_diff)
    _number_hunks(files)
    text = render_patch(files[0].hunks)
    assert "deleted file mode" in text
    assert "-bye" in text


def test_render_empty():
    assert render_patch([]) == ""


def test_render_patch_roundtrip_headers():
    diff = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -2 +2 @@
-old
+new
"""
    files, _, _ = parse_unified_diff(diff)
    from commit_delta.parse import _number_hunks

    _number_hunks(files)
    text = render_patch(files[0].hunks)
    assert "diff --git a/foo.py b/foo.py" in text
    assert "-old" in text
    assert "+new" in text
