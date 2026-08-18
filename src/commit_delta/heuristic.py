"""Conservative traceback heuristics for UNRESOLVED.

These fire only when the process already exited non-zero and not 125.
They exist so a naive `pytest` / `python reproduce.py` that uses exit 1
for both "cannot import" and "assertion failed" does not poison ddmin.

An AssertionError in the same output wins: the subset *did* run a real
check, even if other tests crashed with TypeError. Incomplete subsets
that only raise TypeError/AttributeError stay UNRESOLVED.

NameError stays FAIL — that is often the bug the user is isolating.
"""

from __future__ import annotations

import re

# Raised when a subset cannot be executed meaningfully. Explicit allowlist;
# do not treat every Exception as untestable.
UNRESOLVED_EXCEPTIONS = (
    "SyntaxError",
    "IndentationError",
    "TabError",
    "ImportError",
    "ModuleNotFoundError",
    "TypeError",
    "AttributeError",
)

# Last traceback exception, including pytest's "E   ImportError: ..." lines.
_EXC_RE = re.compile(
    r"^(?:E\s+)?(" + "|".join(UNRESOLVED_EXCEPTIONS) + r")\b",
    re.MULTILINE,
)

# If a real assertion ran, this subset is testable. Do not hide that
# FAIL behind a TypeError from some other new test file.
_INTERESTING_RE = re.compile(
    r"AssertionError|"
    r"^E\s+assert\b|"
    r"^FAILED .+- AssertionError",
    re.MULTILINE,
)


def heuristic_unresolved(stdout: str, stderr: str) -> str | None:
    """Return a short reason if output looks like an untestable subset."""
    text = f"{stderr or ''}\n{stdout or ''}"
    if _INTERESTING_RE.search(text):
        return None
    matches = list(_EXC_RE.finditer(text))
    if not matches:
        return None
    name = matches[-1].group(1)
    return f"heuristic {name}"
