from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from commit_delta.apply import ApplyError, materialize
from commit_delta.types import Hunk
from commit_delta.util import run_git


class IsolatedTree:
    """A disposable worktree pinned at HEAD.

    The user's working tree is never checked out, reset, or written.
    Candidates are materialized by copying HEAD files and applying a
    hunk subset in this isolated tree.
    """

    def __init__(self, repo: str | Path) -> None:
        self.repo = Path(repo)
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self.path: Path | None = None
        self.head_mirror: Path | None = None

    def __enter__(self) -> IsolatedTree:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="commit-delta-")
        root = Path(self._tmpdir.name)
        self.path = root / "probe"
        self.head_mirror = root / "head"
        run_git(
            ["worktree", "add", "--detach", str(self.path), "HEAD"],
            cwd=self.repo,
        )
        # Cheap file-level reset source: a second checkout of HEAD we
        # never mutate. Copying from here is faster and safer than
        # `git checkout -- .` plus leftover added files.
        run_git(
            ["worktree", "add", "--detach", str(self.head_mirror), "HEAD"],
            cwd=self.repo,
        )
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self.path is not None:
            run_git(
                ["worktree", "remove", "--force", str(self.path)],
                cwd=self.repo,
                check=False,
            )
        if self.head_mirror is not None:
            run_git(
                ["worktree", "remove", "--force", str(self.head_mirror)],
                cwd=self.repo,
                check=False,
            )
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
        self.path = None
        self.head_mirror = None
        self._tmpdir = None

    def reset_to_head(self) -> None:
        assert self.path is not None and self.head_mirror is not None
        # Remove everything except .git and recreate from the HEAD mirror.
        for child in self.path.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in self.head_mirror.iterdir():
            if child.name == ".git":
                continue
            dest = self.path / child.name
            if child.is_dir() and not child.is_symlink():
                shutil.copytree(child, dest, symlinks=True)
            else:
                shutil.copy2(child, dest, follow_symlinks=False)

    def apply_subset(self, hunks: list[Hunk]) -> None:
        assert self.path is not None and self.head_mirror is not None
        self.reset_to_head()
        try:
            materialize(self.path, self.head_mirror, hunks)
        except (OSError, UnicodeError) as exc:
            raise ApplyError(str(exc)) from exc
