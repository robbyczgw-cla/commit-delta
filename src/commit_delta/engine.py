from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from commit_delta.apply import ApplyError, render_patch
from commit_delta.ddmin import ddmin
from commit_delta.evaluate import CommandResult, confirm_outcome, run_command
from commit_delta.parse import line_count
from commit_delta.types import (
    Hunk,
    Outcome,
    ReductionResult,
    ReductionStats,
    Snapshot,
    Trial,
    Witness,
)
from commit_delta.util import CommitDeltaError, format_hunk_set
from commit_delta.worktree import IsolatedTree


@dataclass
class EngineConfig:
    command: list[str]
    timeout: float | None = 60.0
    confirm: int = 1
    verbose: bool = False
    heuristics: bool = True
    log: Callable[[str], None] = field(default=lambda _m: None)


class Engine:
    def __init__(
        self,
        snapshot: Snapshot,
        tree: IsolatedTree,
        config: EngineConfig,
    ) -> None:
        self.snapshot = snapshot
        self.tree = tree
        self.config = config
        self.cache: OrderedDict[frozenset[str], Outcome] = OrderedDict()
        self.trials: list[Trial] = []
        self.cache_hits = 0
        self._t0 = time.monotonic()

    def reduce(self) -> ReductionResult:
        hunks = self.snapshot.hunks
        if not hunks:
            raise CommitDeltaError("no tracked hunks to reduce")

        self._log("verify HEAD is GOOD")
        head_result = self._run_in_tree([], label="HEAD")
        if head_result.outcome is not Outcome.PASS:
            raise CommitDeltaError(
                f"HEAD is not GOOD ({head_result.outcome.value}: {head_result.detail}). "
                "commit-delta needs a known-good HEAD."
            )

        self._log("verify full working tree is BAD")
        full_result = self._run_in_tree(hunks, label="working-tree")
        if full_result.outcome is Outcome.PASS:
            raise CommitDeltaError(
                "full working tree is GOOD. nothing to reduce "
                "(the command already passes)."
            )
        if full_result.outcome is Outcome.UNRESOLVED:
            raise CommitDeltaError(
                f"full working tree is UNRESOLVED ({full_result.detail}). "
                "the reproduction command must FAIL on the complete change set."
            )

        self._log(
            f"captured {len(self.snapshot.files)} files, "
            f"{len(hunks)} hunks, {line_count(hunks)} changed lines"
        )

        # Phase 1: file-level atoms (coarse).
        by_file = _group_file_atoms(hunks)
        file_atoms = list(by_file.values())
        if len(file_atoms) > 1:
            self._log(f"phase 1: file-level ddmin ({len(file_atoms)} files)")
            file_min = ddmin(
                file_atoms,
                lambda atoms: self._test_file_atoms(atoms),
                log=self._log,
            )
        else:
            file_min = file_atoms
        remaining = [h for atom in file_min for h in atom]
        self._log(f"phase 1 kept {len(file_min)} files / {len(remaining)} hunks")

        # Phase 2: hunk-level atoms (fine).
        if len(remaining) > 1:
            self._log(f"phase 2: hunk-level ddmin ({len(remaining)} hunks)")
            minimal = ddmin(
                remaining,
                lambda atoms: self._test_hunks(list(atoms), label="hunk-subset"),
                log=self._log,
            )
        else:
            minimal = remaining
            self._test_hunks(minimal, label="hunk-subset")

        witnesses = self._witness_1_minimal(minimal)
        stats = self._stats(hunks, minimal)
        notes = []
        if self.snapshot.skipped_binary:
            notes.append(
                "skipped binary paths: " + ", ".join(self.snapshot.skipped_binary)
            )
        notes.append(
            "uniqueness is not guaranteed: another 1-minimal subset may also FAIL"
        )
        return ReductionResult(
            snapshot=self.snapshot,
            minimal=minimal,
            stats=stats,
            trials=self.trials,
            witnesses=witnesses,
            notes=notes,
        )

    def write_patch(self, hunks: list[Hunk], dest: Path) -> None:
        dest.write_text(render_patch(hunks), encoding="utf-8")

    def _test_file_atoms(self, atoms: Sequence[list[Hunk]]) -> Outcome:
        hunks = [h for atom in atoms for h in atom]
        return self._test_hunks(hunks, label="file-subset")

    def _test_hunks(self, hunks: Sequence[Hunk], *, label: str) -> Outcome:
        key = frozenset(h.id for h in hunks)
        if key in self.cache:
            self.cache_hits += 1
            outcome = self.cache[key]
            self.trials.append(
                Trial(
                    n=len(self.trials) + 1,
                    label=label,
                    outcome=outcome,
                    elapsed_s=0.0,
                    detail="cache",
                    cached=True,
                )
            )
            self._log(
                f"  [{len(self.trials)}] {label} {format_hunk_set(list(key))} "
                f"{outcome.value} (cache)"
            )
            return outcome

        result = self._run_in_tree(list(hunks), label=label)
        self.cache[key] = result.outcome
        return result.outcome

    def _run_in_tree(self, hunks: list[Hunk], *, label: str) -> CommandResult:
        ids = [h.id for h in hunks]

        def once() -> CommandResult:
            try:
                self.tree.apply_subset(hunks)
            except ApplyError as exc:
                return CommandResult(
                    outcome=Outcome.UNRESOLVED,
                    exit_code=None,
                    elapsed_s=0.0,
                    detail=f"apply failed: {exc}",
                )
            assert self.tree.path is not None
            return run_command(
                self.config.command,
                cwd=self.tree.path,
                timeout=self.config.timeout,
                heuristics=self.config.heuristics,
            )

        result = confirm_outcome(once, self.config.confirm)
        self.trials.append(
            Trial(
                n=len(self.trials) + 1,
                label=label,
                outcome=result.outcome,
                elapsed_s=result.elapsed_s,
                detail=result.detail,
                exit_code=result.exit_code,
            )
        )
        self._log(
            f"  [{len(self.trials)}] {label} {format_hunk_set(ids)} "
            f"{result.outcome.value} {result.detail} ({result.elapsed_s:.2f}s)"
        )
        return result

    def _witness_1_minimal(self, minimal: list[Hunk]) -> list[Witness]:
        witnesses: list[Witness] = []
        if len(minimal) <= 1:
            # Still record that the empty set (HEAD) passed.
            witnesses.append(
                Witness(removed_id="(empty / HEAD)", outcome=Outcome.PASS)
            )
            return witnesses
        for drop in minimal:
            subset = [h for h in minimal if h.id != drop.id]
            outcome = self._test_hunks(subset, label=f"without {drop.id}")
            witnesses.append(Witness(removed_id=drop.id, outcome=outcome))
        return witnesses

    def _stats(self, original: list[Hunk], minimal: list[Hunk]) -> ReductionStats:
        real = [t for t in self.trials if not t.cached]
        return ReductionStats(
            input_files=len({h.path for h in original}),
            input_hunks=len(original),
            input_lines=line_count(original),
            output_files=len({h.path for h in minimal}),
            output_hunks=len(minimal),
            output_lines=line_count(minimal),
            trials=len(self.trials),
            cache_hits=self.cache_hits,
            pass_n=sum(1 for t in real if t.outcome is Outcome.PASS),
            fail_n=sum(1 for t in real if t.outcome is Outcome.FAIL),
            unresolved_n=sum(1 for t in real if t.outcome is Outcome.UNRESOLVED),
            elapsed_s=time.monotonic() - self._t0,
        )

    def _log(self, message: str) -> None:
        self.config.log(message)


def _group_file_atoms(hunks: list[Hunk]) -> dict[str, list[Hunk]]:
    grouped: dict[str, list[Hunk]] = {}
    for hunk in hunks:
        grouped.setdefault(hunk.path, []).append(hunk)
    return grouped
