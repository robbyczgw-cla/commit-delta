from __future__ import annotations

import re
from pathlib import Path

from commit_delta.types import FileDiff, FileKind, Hunk, Snapshot
from commit_delta.util import CommitDeltaError, git_text, should_keep

HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$"
)


def capture_snapshot(
    repo: str | Path,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> Snapshot:
    repo = Path(repo)
    head = git_text(["rev-parse", "HEAD"], cwd=repo).strip()
    # -U0: each contiguous change is its own hunk (better atoms).
    # HEAD vs worktree includes staged + unstaged tracked changes.
    diff = git_text(
        [
            "diff",
            "HEAD",
            "--no-color",
            "--no-ext-diff",
            "--text",
            "-U0",
            "--",
        ],
        cwd=repo,
    )
    files, skipped_binary, skipped_other = parse_unified_diff(diff)
    include = include or []
    exclude = exclude or []
    already = {fd.path for fd in files}
    untracked, u_bin, u_other = _untracked_filediffs(repo)
    skipped_binary.extend(u_bin)
    skipped_other.extend(u_other)
    for fd in untracked:
        if fd.path not in already:
            files.append(fd)
    kept: list[FileDiff] = []
    for fd in files:
        if not should_keep(fd.path, include, exclude):
            continue
        if fd.binary:
            skipped_binary.append(fd.path)
            continue
        if not fd.hunks:
            skipped_other.append(fd.path)
            continue
        kept.append(fd)
    _number_hunks(kept)
    return Snapshot(
        repo=str(repo),
        head=head,
        files=kept,
        skipped_binary=skipped_binary,
        skipped_other=skipped_other,
    )


def _untracked_filediffs(repo: Path) -> tuple[list[FileDiff], list[str], list[str]]:
    """Treat each untracked text file as one ADD hunk.

    Ignored paths stay ignored. Binaries are reported and skipped.
    """
    listing = git_text(
        ["ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo,
    )
    files: list[FileDiff] = []
    skipped_binary: list[str] = []
    skipped_other: list[str] = []
    for raw in listing.split("\0"):
        path = raw.strip()
        if not path:
            continue
        full = repo / path
        if not full.is_file():
            skipped_other.append(path)
            continue
        data = full.read_bytes()
        if b"\0" in data:
            skipped_binary.append(path)
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            skipped_binary.append(path)
            continue
        body_lines = text.splitlines()
        body = tuple(f"+{line}" for line in body_lines)
        hunk = Hunk(
            id="",
            path=path,
            kind=FileKind.ADD,
            old_start=0,
            old_count=0,
            new_start=1,
            new_count=len(body_lines),
            section="",
            body=body,
            file_index=0,
            hunk_index=0,
        )
        files.append(
            FileDiff(path=path, kind=FileKind.ADD, hunks=[hunk])
        )
    return files, skipped_binary, skipped_other


def parse_unified_diff(text: str) -> tuple[list[FileDiff], list[str], list[str]]:
    files: list[FileDiff] = []
    skipped_binary: list[str] = []
    skipped_other: list[str] = []
    if not text.strip():
        return files, skipped_binary, skipped_other

    current: FileDiff | None = None
    hunk_body: list[str] = []
    hunk_meta: tuple[int, int, int, int, str] | None = None

    def flush_hunk() -> None:
        nonlocal hunk_body, hunk_meta
        if current is None or hunk_meta is None:
            hunk_body = []
            hunk_meta = None
            return
        old_s, old_c, new_s, new_c, section = hunk_meta
        current.hunks.append(
            Hunk(
                id="",  # filled in later
                path=current.path,
                kind=current.kind,
                old_start=old_s,
                old_count=old_c,
                new_start=new_s,
                new_count=new_c,
                section=section.strip(),
                body=tuple(hunk_body),
                file_index=0,
                hunk_index=0,
            )
        )
        hunk_body = []
        hunk_meta = None

    def flush_file() -> None:
        nonlocal current
        flush_hunk()
        if current is not None:
            files.append(current)
            current = None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            flush_file()
            path = _paths_from_git_line(line)
            current = FileDiff(path=path, kind=FileKind.MODIFY, hunks=[])
            i += 1
            continue
        if current is None:
            i += 1
            continue
        if line.startswith("old mode "):
            current.old_mode = line[len("old mode ") :].strip()
            i += 1
            continue
        if line.startswith("new mode "):
            current.new_mode = line[len("new mode ") :].strip()
            i += 1
            continue
        if line.startswith("new file mode "):
            current.kind = FileKind.ADD
            current.new_mode = line[len("new file mode ") :].strip()
            i += 1
            continue
        if line.startswith("deleted file mode "):
            current.kind = FileKind.DELETE
            current.old_mode = line[len("deleted file mode ") :].strip()
            i += 1
            continue
        if line.startswith("rename from ") or line.startswith("rename to "):
            # Treat rename as delete+add if git emitted two files; if it
            # emitted a single rename, we keep the destination path and
            # apply hunks there. Full rename fidelity is a v0.1 gap.
            i += 1
            continue
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            current.binary = True
            i += 1
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            i += 1
            continue
        if line.startswith("index ") or line.startswith("similarity index"):
            i += 1
            continue
        match = HUNK_RE.match(line)
        if match:
            flush_hunk()
            hunk_meta = (
                int(match.group(1)),
                int(match.group(2) or "1"),
                int(match.group(3)),
                int(match.group(4) or "1"),
                match.group(5) or "",
            )
            i += 1
            continue
        if hunk_meta is not None and (
            line.startswith("+")
            or line.startswith("-")
            or line.startswith(" ")
            or line.startswith("\\")
        ):
            hunk_body.append(line)
            i += 1
            continue
        i += 1

    flush_file()
    return files, skipped_binary, skipped_other


def _paths_from_git_line(line: str) -> str:
    # diff --git a/foo b/foo  (paths may contain spaces)
    rest = line[len("diff --git ") :]
    marker = " b/"
    # Prefer the b/ path (destination).
    if " b/" in rest:
        # Split on the last " b/" after an "a/" prefix.
        try:
            a_part, b_part = rest.split(" b/", 1)
            if a_part.startswith("a/"):
                return b_part
            return b_part
        except ValueError:
            pass
    if rest.startswith("a/") and " b/" in rest:
        return rest.split(" b/", 1)[1]
    raise CommitDeltaError(f"cannot parse diff header: {line}")


def _number_hunks(files: list[FileDiff]) -> None:
    for fi, fd in enumerate(files):
        numbered: list[Hunk] = []
        for hi, h in enumerate(fd.hunks, start=1):
            numbered.append(
                Hunk(
                    id=f"{fd.path}#{hi}",
                    path=fd.path,
                    kind=fd.kind,
                    old_start=h.old_start,
                    old_count=h.old_count,
                    new_start=h.new_start,
                    new_count=h.new_count,
                    section=h.section,
                    body=h.body,
                    file_index=fi,
                    hunk_index=hi,
                )
            )
        fd.hunks = numbered


def line_count(hunks: list[Hunk]) -> int:
    return sum(h.changed_line_count for h in hunks)
