from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Sequence


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNRESOLVED = "UNRESOLVED"


class FileKind(str, Enum):
    MODIFY = "modify"
    ADD = "add"
    DELETE = "delete"


@dataclass(frozen=True)
class Hunk:
    """One unified-diff hunk captured from `git diff HEAD`."""

    id: str
    path: str
    kind: FileKind
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    section: str
    body: tuple[str, ...]
    file_index: int
    hunk_index: int  # 1-based per file

    @property
    def old_lines(self) -> list[str]:
        lines: list[str] = []
        for raw in self.body:
            if raw.startswith("\\"):
                continue
            if raw.startswith("-") or raw.startswith(" "):
                lines.append(raw[1:])
        return lines

    @property
    def new_lines(self) -> list[str]:
        lines: list[str] = []
        for raw in self.body:
            if raw.startswith("\\"):
                continue
            if raw.startswith("+") or raw.startswith(" "):
                lines.append(raw[1:])
        return lines

    @property
    def added_line_count(self) -> int:
        return sum(1 for raw in self.body if raw.startswith("+"))

    @property
    def deleted_line_count(self) -> int:
        return sum(1 for raw in self.body if raw.startswith("-"))

    @property
    def changed_line_count(self) -> int:
        return self.added_line_count + self.deleted_line_count

    def preview(self, limit: int = 6) -> list[str]:
        out: list[str] = []
        for raw in self.body:
            if raw.startswith("\\"):
                continue
            if raw.startswith(("+", "-")):
                out.append(raw)
            if len(out) >= limit:
                break
        return out


@dataclass
class FileDiff:
    path: str
    kind: FileKind
    hunks: list[Hunk]
    old_mode: str | None = None
    new_mode: str | None = None
    binary: bool = False


@dataclass
class Snapshot:
    """Immutable capture of tracked working-tree changes vs HEAD."""

    repo: str
    head: str
    files: list[FileDiff]
    skipped_binary: list[str] = field(default_factory=list)
    skipped_other: list[str] = field(default_factory=list)

    @property
    def hunks(self) -> list[Hunk]:
        out: list[Hunk] = []
        for fd in self.files:
            out.extend(fd.hunks)
        return out

    def hunks_for(self, ids: Iterable[str]) -> list[Hunk]:
        wanted = set(ids)
        return [h for h in self.hunks if h.id in wanted]


@dataclass
class Trial:
    n: int
    label: str
    outcome: Outcome
    elapsed_s: float
    detail: str = ""
    cached: bool = False
    exit_code: int | None = None


@dataclass
class ReductionStats:
    input_files: int
    input_hunks: int
    input_lines: int
    output_files: int
    output_hunks: int
    output_lines: int
    trials: int
    cache_hits: int
    pass_n: int
    fail_n: int
    unresolved_n: int
    elapsed_s: float

    @property
    def hunk_ratio(self) -> float:
        if self.input_hunks == 0:
            return 1.0
        return self.output_hunks / self.input_hunks

    @property
    def line_ratio(self) -> float:
        if self.input_lines == 0:
            return 1.0
        return self.output_lines / self.input_lines


@dataclass
class Witness:
    removed_id: str
    outcome: Outcome
    detail: str = ""


@dataclass
class ReductionResult:
    snapshot: Snapshot
    minimal: list[Hunk]
    stats: ReductionStats
    trials: list[Trial]
    witnesses: list[Witness]
    notes: list[str] = field(default_factory=list)

    @property
    def unique_not_guaranteed(self) -> bool:
        return True


def hunk_ids(hunks: Sequence[Hunk]) -> tuple[str, ...]:
    return tuple(h.id for h in hunks)
