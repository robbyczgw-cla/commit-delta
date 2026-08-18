from __future__ import annotations

from commit_delta.ddmin import ddmin
from commit_delta.types import Outcome


def test_single_bad_atom():
    atoms = list(range(20))

    def test(subset):
        return Outcome.FAIL if 7 in subset else Outcome.PASS

    result = ddmin(atoms, test)
    assert result == [7]


def test_interacting_pair():
    atoms = list("abcdefgh")

    def test(subset):
        s = set(subset)
        return Outcome.FAIL if ("c" in s and "f" in s) else Outcome.PASS

    result = set(ddmin(atoms, test))
    assert result == {"c", "f"}


def test_unresolved_does_not_poison():
    atoms = list("wxyz")

    def test(subset):
        s = set(subset)
        if s == {"x"}:
            return Outcome.UNRESOLVED
        if "x" in s and "z" in s:
            return Outcome.FAIL
        return Outcome.PASS

    result = set(ddmin(atoms, test))
    assert "x" in result and "z" in result
    assert result <= {"w", "x", "y", "z"}


def test_multiple_minima_returns_one_1_minimal():
    atoms = list("abcd")

    def test(subset):
        s = set(subset)
        return Outcome.FAIL if ("a" in s or "c" in s) else Outcome.PASS

    result = ddmin(atoms, test)
    assert len(result) == 1
    assert result[0] in {"a", "c"}


def test_empty():
    assert ddmin([], lambda s: Outcome.PASS) == []


def test_all_atoms_required():
    atoms = list("abcd")

    def test(subset):
        return Outcome.FAIL if set(subset) == set(atoms) else Outcome.PASS

    assert set(ddmin(atoms, test)) == set(atoms)


def test_log_is_optional_and_used():
    notes: list[str] = []
    result = ddmin([1, 2, 7], lambda s: Outcome.FAIL if 7 in s else Outcome.PASS, log=notes.append)
    assert result == [7]
    assert notes


def test_unresolved_complements_are_skipped():
    atoms = list("xyz")

    def test(subset):
        s = set(subset)
        if s == {"x", "y"}:
            return Outcome.UNRESOLVED
        if "z" in s:
            return Outcome.FAIL
        return Outcome.PASS

    assert ddmin(atoms, test) == ["z"]
