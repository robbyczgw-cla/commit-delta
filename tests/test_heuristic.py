from __future__ import annotations

from commit_delta.heuristic import heuristic_unresolved


def test_attribute_error_alone():
    tb = "E   AttributeError: 'NoneType' object has no attribute 'x'\n"
    assert heuristic_unresolved("", tb) == "heuristic AttributeError"


def test_indent_and_tab_errors():
    assert heuristic_unresolved("IndentationError: unexpected indent\n", "") == (
        "heuristic IndentationError"
    )
    assert heuristic_unresolved("", "TabError: inconsistent use of tabs\n") == (
        "heuristic TabError"
    )


def test_pytest_e_assert_is_interesting():
    out = "E   assert 1 == 2\n"
    assert heuristic_unresolved(out, "") is None


def test_failed_assertionerror_line():
    out = "FAILED tests/test_foo.py::test_bar - AssertionError: boom\n"
    assert heuristic_unresolved("", out) is None


def test_empty_output():
    assert heuristic_unresolved("", "") is None
