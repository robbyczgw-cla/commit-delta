from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from commit_delta.apply import render_patch
from commit_delta.engine import Engine, EngineConfig
from commit_delta.parse import capture_snapshot
from commit_delta.worktree import IsolatedTree
from tests.support.builders import build_fixture_a
from tests.support.gitrepo import run

SRC = Path(__file__).resolve().parents[1] / "src"


def test_cli_writes_applyable_patch(tmp_path):
    repo = build_fixture_a(tmp_path / "a")
    out = tmp_path / "reduced.patch"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "commit_delta",
            "--output",
            str(out),
            "--log-file",
            str(tmp_path / "run.log"),
            "--",
            "./reproduce.sh",
        ],
        cwd=str(repo),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert out.exists()
    text = out.read_text()
    assert "core.py" in text
    assert (tmp_path / "run.log").exists()

    # Apply the reduced patch onto a clean checkout and confirm it still fails.
    clean = tmp_path / "clean"
    run(["git", "clone", str(repo), str(clean)], cwd=tmp_path)
    run(["git", "apply", str(out)], cwd=clean)
    failed = subprocess.run(
        ["./reproduce.sh"],
        cwd=str(clean),
        check=False,
    )
    assert failed.returncode != 0


def test_include_drops_other_files(tmp_path):
    repo = build_fixture_a(tmp_path / "inc")
    snap = capture_snapshot(repo, include=["core.py"])
    assert {f.path for f in snap.files} == {"core.py"}


def test_cli_writes_json(tmp_path):
    import json

    repo = build_fixture_a(tmp_path / "j")
    js = tmp_path / "out.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(
        [sys.executable, "-m", "commit_delta", "--json", str(js), "--", "./reproduce.sh"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(js.read_text())
    assert data["minimal"]
    assert data["minimal"][0]["path"] == "core.py"
    assert data["stats"]["output_hunks"] == 1
    assert data["unique_not_guaranteed"] is True
    assert "patch" in data


def test_cli_missing_command_errors():
    proc = subprocess.run(
        [sys.executable, "-m", "commit_delta"],
        cwd="/tmp",
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "missing command" in (proc.stderr + proc.stdout).lower()


def test_cli_version():
    proc = subprocess.run(
        [sys.executable, "-m", "commit_delta", "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "0.1.0" in proc.stdout


def test_cli_not_a_repo(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(
        [sys.executable, "-m", "commit_delta", "--", "true"],
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 2
    assert "not a git repository" in proc.stderr


def test_cli_clean_tree(tmp_path):
    from tests.support.gitrepo import commit_all, init_repo, write

    repo = init_repo(tmp_path / "clean")
    write(repo / "a.py", "x = 1\n")
    commit_all(repo, "ok")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(
        [sys.executable, "-m", "commit_delta", "--", "true"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 2
    assert "no reducible" in proc.stderr


def test_timeout_is_unresolved(tmp_path):
    repo = build_fixture_a(tmp_path / "to")
    snap = capture_snapshot(repo)
    with IsolatedTree(repo) as tree:
        engine = Engine(
            snap,
            tree,
            EngineConfig(command=["sleep", "5"], timeout=0.2),
        )
        result = engine._run_in_tree([], label="timeout")
    assert result.outcome.value == "UNRESOLVED"
    assert "timeout" in result.detail
