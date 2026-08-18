from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from commit_delta.engine import Engine, EngineConfig
from commit_delta.parse import capture_snapshot, line_count
from commit_delta.types import Outcome
from commit_delta.util import git_text
from commit_delta.worktree import IsolatedTree
from tests.support.builders import (
    build_demo,
    build_fixture_a,
    build_fixture_b,
    build_fixture_c,
    build_fixture_d,
    build_fixture_dense,
    build_fixture_e,
    build_fixture_delete,
    build_fixture_messy,
)

SRC = Path(__file__).resolve().parents[1] / "src"


def reduce_repo(
    repo: Path,
    *,
    confirm: int = 1,
    timeout: float = 15.0,
    heuristics: bool = True,
):
    snapshot = capture_snapshot(repo)
    before = git_text(["diff", "HEAD"], cwd=repo)
    with IsolatedTree(repo) as tree:
        engine = Engine(
            snapshot,
            tree,
            EngineConfig(
                command=["./reproduce.sh"],
                timeout=timeout,
                confirm=confirm,
                heuristics=heuristics,
            ),
        )
        result = engine.reduce()
    after = git_text(["diff", "HEAD"], cwd=repo)
    assert after == before, "user working tree must be untouched"
    return result


@pytest.mark.e2e
def test_fixture_a_single_bad_hunk(tmp_path):
    repo = build_fixture_a(tmp_path / "a")
    snap = capture_snapshot(repo)
    assert len(snap.hunks) >= 21
    result = reduce_repo(repo)
    ids = [h.id for h in result.minimal]
    assert len(result.minimal) == 1, ids
    assert result.minimal[0].path == "core.py"
    assert result.stats.output_hunks == 1
    assert result.stats.hunk_ratio < 0.15


@pytest.mark.e2e
def test_fixture_b_interacting_pair(tmp_path):
    repo = build_fixture_b(tmp_path / "b")
    result = reduce_repo(repo)
    paths = {h.path for h in result.minimal}
    assert paths == {"flags.py", "app.py"}
    assert all(w.outcome is Outcome.PASS for w in result.witnesses if w.removed_id != "(empty / HEAD)")


@pytest.mark.e2e
def test_fixture_c_unresolved_subsets(tmp_path):
    repo = build_fixture_c(tmp_path / "c")
    result = reduce_repo(repo)
    ids = {h.id for h in result.minimal}
    paths = {h.path for h in result.minimal}
    assert "extras.py" in paths
    assert "app.py" in paths
    assert "noise.py" not in paths
    assert len(result.minimal) >= 2
    unresolved = [t for t in result.trials if t.outcome is Outcome.UNRESOLVED and not t.cached]
    assert unresolved, "expected some UNRESOLVED candidates"
    # Search still converged on a failing subset, not the whole tree.
    assert result.stats.output_hunks < result.stats.input_hunks
    assert ids


@pytest.mark.e2e
def test_fixture_d_one_of_two_minima(tmp_path):
    repo = build_fixture_d(tmp_path / "d")
    result = reduce_repo(repo)
    assert len(result.minimal) == 1
    assert result.minimal[0].path in {"left.py", "right.py"}
    assert any("uniqueness is not guaranteed" in n for n in result.notes)


@pytest.mark.e2e
def test_fixture_e_confirm(tmp_path):
    repo = build_fixture_e(tmp_path / "e")
    result = reduce_repo(repo, confirm=3)
    assert len(result.minimal) == 1
    assert result.minimal[0].path == "core.py"
    # Every accepted FAIL/PASS on real runs used 3 confirmations.
    real_fail = [
        t
        for t in result.trials
        if not t.cached and t.outcome is Outcome.FAIL and t.label in {"working-tree", "hunk-subset", "file-subset"}
    ]
    assert real_fail
    assert any("3/3" in t.detail or t.detail.startswith("FAIL") for t in real_fail)


@pytest.mark.e2e
def test_fixture_messy_heuristic_and_fat_hunk(tmp_path):
    repo = build_fixture_messy(tmp_path / "messy")
    snap = capture_snapshot(repo)
    assert line_count(snap.hunks) >= 40
    result = reduce_repo(repo)
    paths = {h.path for h in result.minimal}
    assert paths == {"checkout.py", "promo.py"}
    checkout = next(h for h in result.minimal if h.path == "checkout.py")
    assert checkout.changed_line_count >= 15
    heuristic_hits = [
        t
        for t in result.trials
        if not t.cached and "heuristic" in t.detail
    ]
    assert heuristic_hits, "expected ImportError subsets classified by heuristic"
    assert "pricing.py" not in paths
    assert "catalog.py" not in paths


@pytest.mark.e2e
def test_fixture_messy_strict_exits_poisons_search(tmp_path):
    repo = build_fixture_messy(tmp_path / "strict")
    poisoned = reduce_repo(repo, heuristics=False)
    paths = {h.path for h in poisoned.minimal}
    # Without heuristics, ImportError is FAIL, so promo.py is unnecessary.
    assert "promo.py" not in paths
    assert "checkout.py" in paths


@pytest.mark.e2e
def test_fixture_dense_keeps_all_required(tmp_path):
    repo = build_fixture_dense(tmp_path / "dense")
    result = reduce_repo(repo)
    paths = {h.path for h in result.minimal}
    assert paths == {"w.py", "x.py", "y.py", "z.py"}
    assert result.stats.output_hunks == 4
    assert result.stats.output_hunks < result.stats.input_hunks


@pytest.mark.e2e
def test_fixture_delete_helper_file(tmp_path):
    repo = build_fixture_delete(tmp_path / "del")
    result = reduce_repo(repo)
    paths = {h.path for h in result.minimal}
    assert "helper.py" in paths
    assert "noise.py" not in paths


@pytest.mark.e2e
def test_working_tree_already_good_aborts(tmp_path):
    from commit_delta.util import CommitDeltaError

    repo = build_fixture_a(tmp_path / "goodwt")
    snap = capture_snapshot(repo)
    with IsolatedTree(repo) as tree:
        engine = Engine(
            snap,
            tree,
            EngineConfig(command=["true"], timeout=5),
        )
        with pytest.raises(CommitDeltaError, match="full working tree is GOOD"):
            engine.reduce()


@pytest.mark.e2e
def test_demo_dramatic_reduction(tmp_path):
    repo = build_demo(tmp_path / "demo")
    snap = capture_snapshot(repo)
    assert len(snap.hunks) >= 25
    assert line_count(snap.hunks) >= 400
    result = reduce_repo(repo)
    assert len(result.minimal) == 1
    assert result.minimal[0].path == "calc.py"
    assert result.stats.output_lines < 20
    assert result.stats.hunk_ratio < 0.1


@pytest.mark.e2e
def test_cli_demo(tmp_path):
    repo = build_fixture_a(tmp_path / "cli")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(
        [sys.executable, "-m", "commit_delta", "--verbose", "--", "./reproduce.sh"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "Minimal failure-inducing change set" in proc.stdout
    assert "core.py" in proc.stdout
    assert "1-minimal" in proc.stdout


@pytest.mark.e2e
def test_head_not_good_aborts(tmp_path):
    repo = build_fixture_a(tmp_path / "badhead")
    # Make HEAD itself fail by rewriting reproduce.sh in the index... easier:
    # change reproduce.sh on HEAD by amending? Just rewrite the committed
    # test after the fact: edit reproduce.sh (tracked) so the test is inverted
    # at HEAD as well. Simpler: run a command that always fails.
    snap = capture_snapshot(repo)
    with IsolatedTree(repo) as tree:
        engine = Engine(
            snap,
            tree,
            EngineConfig(command=["false"], timeout=5),
        )
        with pytest.raises(Exception, match="HEAD is not GOOD"):
            engine.reduce()
