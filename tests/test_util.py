from __future__ import annotations

import pytest

from commit_delta.util import (
    CommitDeltaError,
    find_repo,
    format_hunk_set,
    parse_duration,
    path_matches,
    should_keep,
)
from tests.support.gitrepo import commit_all, init_repo, write


def test_parse_duration_invalid():
    with pytest.raises(CommitDeltaError, match="invalid duration"):
        parse_duration("nope")
    with pytest.raises(CommitDeltaError, match="invalid duration unit"):
        parse_duration("3weeks")


def test_parse_duration_aliases():
    assert parse_duration("1.5s") == 1.5
    assert parse_duration("3min") == 180
    assert parse_duration("2hours") == 7200
    assert parse_duration("  10sec ") == 10


def test_path_matches_prefix_glob_and_name():
    assert path_matches("src/a.py", ["src"])
    assert path_matches("src/a.py", ["src/a.py"])
    assert path_matches("src/a.py", ["*.py"])
    assert path_matches("src/a.py", ["a.py"])
    assert not path_matches("src/a.py", ["tests"])
    assert not path_matches("src/a.py", [])
    assert not path_matches("src/a.py", [""])


def test_should_keep_include_and_exclude():
    assert should_keep("a.py", [], [])
    assert should_keep("src/a.py", ["src/*.py"], [])
    assert not should_keep("src/a.py", ["src"], ["src/a.py"])
    assert not should_keep("docs/x.md", ["src"], [])


def test_format_hunk_set_limits():
    assert format_hunk_set([]) == "{}"
    assert format_hunk_set(["a#1", "b#1"]) == "{a#1, b#1}"
    out = format_hunk_set([f"f#{i}" for i in range(12)], limit=3)
    assert "+9 more" in out


def test_find_repo_and_not_a_repo(tmp_path):
    with pytest.raises(CommitDeltaError, match="not a git repository"):
        find_repo(tmp_path)
    repo = init_repo(tmp_path / "r")
    write(repo / "a.txt", "x\n")
    commit_all(repo, "init")
    nested = repo / "sub"
    nested.mkdir()
    assert find_repo(nested) == repo.resolve()
