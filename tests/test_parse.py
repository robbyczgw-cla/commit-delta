from __future__ import annotations

from commit_delta.parse import parse_unified_diff
from commit_delta.types import FileKind


def test_parse_modify_hunks():
    diff = """\
diff --git a/foo.py b/foo.py
index 111..222 100644
--- a/foo.py
+++ b/foo.py
@@ -2 +2 @@
-old
+new
@@ -10 +10 @@ def bar():
-    return 1
+    return 2
"""
    files, binary, other = parse_unified_diff(diff)
    assert binary == []
    assert other == []
    assert len(files) == 1
    assert files[0].path == "foo.py"
    assert files[0].kind is FileKind.MODIFY
    assert len(files[0].hunks) == 2
    assert files[0].hunks[0].old_start == 2
    assert files[0].hunks[0].old_lines == ["old"]
    assert files[0].hunks[0].new_lines == ["new"]


def test_parse_new_file():
    diff = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..abc
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+hello
+world
"""
    files, _, _ = parse_unified_diff(diff)
    assert files[0].kind is FileKind.ADD
    assert files[0].hunks[0].old_start == 0
    assert files[0].hunks[0].old_count == 0
    assert files[0].hunks[0].new_lines == ["hello", "world"]


def test_parse_deleted_file():
    diff = """\
diff --git a/old.py b/old.py
deleted file mode 100644
index abc..0000000
--- a/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-gone
-away
"""
    files, _, _ = parse_unified_diff(diff)
    assert files[0].kind is FileKind.DELETE
    assert files[0].hunks[0].old_lines == ["gone", "away"]


def test_parse_skips_empty():
    files, binary, other = parse_unified_diff("")
    assert files == []
    assert binary == []
    assert other == []


def test_parse_binary_is_flagged():
    diff = """\
diff --git a/pic.bin b/pic.bin
index 111..222 100644
Binary files a/pic.bin and b/pic.bin differ
"""
    files, _, _ = parse_unified_diff(diff)
    assert files[0].binary is True
    assert files[0].hunks == []


def test_parse_rename_keeps_destination():
    diff = """\
diff --git a/old name.py b/new name.py
similarity index 90%
rename from old name.py
rename to new name.py
index 111..222 100644
--- a/old name.py
+++ b/new name.py
@@ -1 +1 @@
-a
+b
"""
    files, _, _ = parse_unified_diff(diff)
    assert files[0].path == "new name.py"
    assert files[0].hunks[0].old_lines == ["a"]


def test_parse_default_hunk_counts():
    diff = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -3 +3 @@ ctx
-old
+new
"""
    files, _, _ = parse_unified_diff(diff)
    h = files[0].hunks[0]
    assert h.old_count == 1
    assert h.new_count == 1
    assert h.section == "ctx"


def test_parse_mode_headers():
    diff = """\
diff --git a/s.py b/s.py
old mode 100644
new mode 100755
index 111..222
--- a/s.py
+++ b/s.py
@@ -1 +1 @@
-a
+b
"""
    files, _, _ = parse_unified_diff(diff)
    assert files[0].old_mode == "100644"
    assert files[0].new_mode == "100755"


def test_capture_exclude_and_include(tmp_path):
    from commit_delta.parse import capture_snapshot
    from tests.support.gitrepo import commit_all, init_repo, write

    repo = init_repo(tmp_path / "f")
    write(repo / "keep.py", "x = 1\n")
    write(repo / "drop.py", "y = 1\n")
    commit_all(repo, "base")
    write(repo / "keep.py", "x = 2\n")
    write(repo / "drop.py", "y = 2\n")
    snap = capture_snapshot(repo, exclude=["drop.py"])
    assert {f.path for f in snap.files} == {"keep.py"}
    snap2 = capture_snapshot(repo, include=["drop.py"])
    assert {f.path for f in snap2.files} == {"drop.py"}


def test_capture_skips_untracked_binary(tmp_path):
    from commit_delta.parse import capture_snapshot
    from tests.support.gitrepo import commit_all, init_repo, write

    repo = init_repo(tmp_path / "bin")
    write(repo / "ok.py", "x = 1\n")
    commit_all(repo, "base")
    (repo / "blob.bin").write_bytes(b"hello\x00world")
    snap = capture_snapshot(repo)
    assert "blob.bin" in snap.skipped_binary
    assert all(f.path != "blob.bin" for f in snap.files)


def test_capture_includes_untracked_text(tmp_path):
    from commit_delta.parse import capture_snapshot
    from tests.support.gitrepo import commit_all, init_repo, write

    repo = init_repo(tmp_path / "u")
    write(repo / "kept.py", "x = 1\n")
    commit_all(repo, "base")
    write(repo / "kept.py", "x = 2\n")
    write(repo / "brand_new.py", "y = 3\n")
    snap = capture_snapshot(repo)
    paths = {f.path for f in snap.files}
    assert "kept.py" in paths
    assert "brand_new.py" in paths
    added = next(f for f in snap.files if f.path == "brand_new.py")
    assert added.kind.value == "add"
    assert added.hunks[0].new_lines == ["y = 3"]
