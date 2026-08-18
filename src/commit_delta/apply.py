from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from commit_delta.types import FileKind, Hunk


class ApplyError(RuntimeError):
    """A hunk subset cannot be applied to HEAD content."""


def apply_hunks_to_lines(original: list[str], hunks: list[Hunk]) -> list[str]:
    """Apply hunks against original-file coordinates, bottom to top.

    Git unified-diff hunks record *old* positions on the a/ (HEAD) side.
    Selecting a subset therefore does not require shifting later hunks:
    each hunk is an independent edit of the original file.
    """
    if not hunks:
        return list(original)
    lines = list(original)
    ordered = sorted(
        hunks,
        key=lambda h: (h.old_start, h.old_count, h.hunk_index),
        reverse=True,
    )
    for hunk in ordered:
        start = _old_index(hunk)
        end = start + hunk.old_count
        expected = hunk.old_lines
        actual = lines[start:end]
        if actual != expected:
            raise ApplyError(
                f"{hunk.id}: original slice {start}:{end} does not match hunk "
                f"(expected {expected!r}, got {actual!r})"
            )
        lines[start:end] = hunk.new_lines
    return lines


def _old_index(hunk: Hunk) -> int:
    # GNU/git empty-range convention: -N,0 means "insert after line N"
    # (or at 0 for a new file). Non-empty ranges are 1-based inclusive.
    if hunk.old_count == 0:
        return hunk.old_start
    return hunk.old_start - 1


def group_by_path(hunks: list[Hunk]) -> dict[str, list[Hunk]]:
    grouped: dict[str, list[Hunk]] = defaultdict(list)
    for hunk in hunks:
        grouped[hunk.path].append(hunk)
    return dict(grouped)


def materialize(
    worktree: Path,
    head_root: Path,
    hunks: list[Hunk],
) -> None:
    """Write a hunk subset into `worktree`, which currently matches HEAD."""
    by_path = group_by_path(hunks)
    for path, file_hunks in by_path.items():
        kind = file_hunks[0].kind
        dest = worktree / path
        if kind == FileKind.ADD:
            dest.parent.mkdir(parents=True, exist_ok=True)
            new_lines = _synthesize_new_file(file_hunks)
            _write_lines(dest, new_lines)
            continue
        src = head_root / path
        if kind == FileKind.DELETE:
            # A delete is represented as one or more hunks that remove
            # the whole file. Selecting any delete hunk for the file
            # removes it; partial deletes fall through to apply.
            if _is_full_delete(file_hunks, src):
                if dest.exists():
                    dest.unlink()
                continue
        original = _read_lines(src)
        updated = apply_hunks_to_lines(original, file_hunks)
        dest.parent.mkdir(parents=True, exist_ok=True)
        _write_lines(dest, updated)


def _is_full_delete(hunks: list[Hunk], src: Path) -> bool:
    if not hunks:
        return False
    if any(h.kind != FileKind.DELETE for h in hunks):
        return False
    if not src.exists():
        return True
    original = _read_lines(src)
    try:
        result = apply_hunks_to_lines(original, hunks)
    except ApplyError:
        return False
    return result == []


def _synthesize_new_file(hunks: list[Hunk]) -> list[str]:
    # New files are usually one hunk from -0,0. If split, apply in order
    # onto an empty original.
    ordered = sorted(hunks, key=lambda h: (h.new_start, h.hunk_index))
    lines: list[str] = []
    for hunk in ordered:
        if hunk.old_count != 0 and hunk.old_lines:
            raise ApplyError(f"{hunk.id}: added file hunk is not insert-only")
        start = _old_index(hunk)
        if start < 0 or start > len(lines):
            # Fall back to append — still better than dying if git's
            # empty-range numbering is surprising on a brand-new file.
            lines.extend(hunk.new_lines)
        else:
            lines[start:start] = hunk.new_lines
    return lines


def _read_lines(path: Path) -> list[str]:
    data = path.read_bytes()
    if not data:
        return []
    text = data.decode("utf-8")
    # Preserve whether the file ended with a newline by using splitlines
    # (which drops the final newline) — apply math is line-based.
    # We restore a trailing newline on write if the original had one
    # or if the resulting text is non-empty (normal source files).
    return text.splitlines()


def _write_lines(path: Path, lines: list[str]) -> None:
    if not lines:
        path.write_text("", encoding="utf-8")
        return
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_patch(hunks: list[Hunk]) -> str:
    """Render a unified diff that applies to HEAD for the remaining hunks."""
    if not hunks:
        return ""
    by_path = group_by_path(hunks)
    chunks: list[str] = []
    for path, file_hunks in by_path.items():
        kind = file_hunks[0].kind
        chunks.append(f"diff --git a/{path} b/{path}")
        if kind == FileKind.ADD:
            chunks.append("new file mode 100644")
            chunks.append("--- /dev/null")
            chunks.append(f"+++ b/{path}")
        elif kind == FileKind.DELETE:
            chunks.append("deleted file mode 100644")
            chunks.append(f"--- a/{path}")
            chunks.append("+++ /dev/null")
        else:
            chunks.append(f"--- a/{path}")
            chunks.append(f"+++ b/{path}")
        # Recalculate new-side line numbers so the patch is self-consistent
        # when hunks were dropped.
        offset = 0
        for hunk in sorted(file_hunks, key=lambda h: (h.old_start, h.hunk_index)):
            new_start = _emitted_new_start(hunk, offset)
            old_count = hunk.old_count
            new_count = len(hunk.new_lines)
            old_part = _range(hunk.old_start, old_count)
            new_part = _range(new_start, new_count)
            header = f"@@ -{old_part} +{new_part} @@"
            if hunk.section:
                header += f" {hunk.section}"
            chunks.append(header)
            chunks.extend(hunk.body)
            offset += new_count - old_count
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def _emitted_new_start(hunk: Hunk, offset: int) -> int:
    if hunk.old_count == 0:
        base = hunk.old_start + 1 if hunk.old_start > 0 else 1
    else:
        base = hunk.old_start
    return max(0, base + offset)


def _range(start: int, count: int) -> str:
    if count == 1:
        return f"{start}"
    return f"{start},{count}"
