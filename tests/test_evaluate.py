from __future__ import annotations

import sys

from commit_delta.evaluate import CommandResult, confirm_outcome, run_command
from commit_delta.heuristic import heuristic_unresolved
from commit_delta.types import Outcome
from commit_delta.util import parse_duration, should_keep


def _res(outcome: Outcome) -> CommandResult:
    return CommandResult(outcome=outcome, exit_code=1, elapsed_s=0.01, detail="t")


def test_confirm_all_fail():
    calls = {"n": 0}

    def once():
        calls["n"] += 1
        return _res(Outcome.FAIL)

    out = confirm_outcome(once, 3)
    assert out.outcome is Outcome.FAIL
    assert calls["n"] == 3


def test_confirm_mixed_is_unresolved():
    seq = [Outcome.FAIL, Outcome.PASS]
    it = iter(seq)

    def once():
        return _res(next(it))

    out = confirm_outcome(once, 2)
    assert out.outcome is Outcome.UNRESOLVED
    assert "inconsistent" in out.detail


def test_confirm_all_pass():
    out = confirm_outcome(lambda: _res(Outcome.PASS), 2)
    assert out.outcome is Outcome.PASS


def test_parse_duration():
    assert parse_duration("60") == 60
    assert parse_duration("60s") == 60
    assert parse_duration("2m") == 120
    assert parse_duration("500ms") == 0.5
    assert parse_duration("1h") == 3600


def test_heuristic_import_and_syntax():
    importerr = (
        "Traceback (most recent call last):\n"
        '  File "./reproduce.sh", line 8, in <module>\n'
        "    from checkout import total\n"
        "ModuleNotFoundError: No module named 'promo'\n"
    )
    assert heuristic_unresolved("", importerr) == "heuristic ModuleNotFoundError"

    syntax = (
        '  File "app.py", line 3\n'
        "    def compute(x)\n"
        "                 ^\n"
        "SyntaxError: expected ':'\n"
    )
    assert heuristic_unresolved(syntax, "") == "heuristic SyntaxError"

    pytest_style = "E   ImportError: cannot import name 'factor'\n"
    assert heuristic_unresolved("", pytest_style) == "heuristic ImportError"


def test_heuristic_ignores_real_failures():
    assert heuristic_unresolved("", "AssertionError: 33 != 35") is None
    assert heuristic_unresolved("", "NameError: name 'apply_promo' is not defined") is None
    assert heuristic_unresolved("ok", "") is None


def test_heuristic_typeerror_alone_is_unresolved():
    tb = (
        "Traceback (most recent call last):\n"
        '  File "tests/test_freshness.py", line 51, in test_static\n'
        "    SubClaim(text='x', temporal_class='fast')\n"
        "TypeError: SubClaim.__init__() got an unexpected keyword argument "
        "'temporal_class'\n"
    )
    assert heuristic_unresolved("", tb) == "heuristic TypeError"


def test_heuristic_assertion_wins_over_typeerror():
    mixed = (
        "E   TypeError: unexpected keyword argument 'temporal_class'\n"
        "FAILED tests/test_freshness.py::test_static - TypeError\n"
        "E   AssertionError: assert 'fresh' == 'stale'\n"
        "FAILED tests/test_smoke.py::test_supported_claim - AssertionError\n"
    )
    assert heuristic_unresolved("", mixed) is None


def test_run_command_exit_125(tmp_path):
    script = tmp_path / "skip.py"
    script.write_text("import sys\nsys.exit(125)\n", encoding="utf-8")
    out = run_command([sys.executable, str(script)], cwd=tmp_path, timeout=5)
    assert out.outcome is Outcome.UNRESOLVED
    assert out.exit_code == 125


def test_run_command_not_found(tmp_path):
    out = run_command(["definitely-not-a-cmd-xyz"], cwd=tmp_path, timeout=5)
    assert out.outcome is Outcome.UNRESOLVED
    assert "not found" in out.detail


def test_confirm_all_unresolved():
    out = confirm_outcome(lambda: _res(Outcome.UNRESOLVED), 2)
    assert out.outcome is Outcome.UNRESOLVED
    assert "UNRESOLVED 2/2" in out.detail


def test_run_command_applies_heuristic(tmp_path):
    script = tmp_path / "missing.py"
    script.write_text("import nosuch_commit_delta_module\n", encoding="utf-8")
    hit = run_command([sys.executable, str(script)], cwd=tmp_path, timeout=5)
    assert hit.outcome is Outcome.UNRESOLVED
    assert "heuristic" in hit.detail
    raw = run_command(
        [sys.executable, str(script)],
        cwd=tmp_path,
        timeout=5,
        heuristics=False,
    )
    assert raw.outcome is Outcome.FAIL


def test_include_exclude():
    assert should_keep("src/a.py", ["src"], [])
    assert not should_keep("tests/a.py", ["src"], [])
    assert not should_keep("src/a.py", [], ["src"])
    assert should_keep("src/a.py", [], ["tests"])
