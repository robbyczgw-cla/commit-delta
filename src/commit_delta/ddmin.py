from __future__ import annotations

from typing import Callable, Sequence, TypeVar

from commit_delta.types import Outcome

T = TypeVar("T")

TestFn = Callable[[Sequence[T]], Outcome]


def ddmin(
    atoms: Sequence[T],
    test: TestFn[T],
    *,
    log: Callable[[str], None] | None = None,
) -> list[T]:
    """Zeller ddmin. `test` must return FAIL for the full `atoms` set.

    UNRESOLVED is neither FAIL nor PASS: those subsets are skipped, so
    they cannot become the current candidate and cannot poison the
    search into a dead end.
    """
    current = list(atoms)
    if not current:
        return current
    n = 2
    _log = log or (lambda _m: None)

    while True:
        if len(current) == 1:
            return current
        subsets = _split(current, n)
        _log(f"ddmin |Δ|={len(current)} n={n} subsets={len(subsets)}")

        reduced = False
        for part in subsets:
            if not part:
                continue
            outcome = test(part)
            if outcome is Outcome.FAIL:
                _log(f"  subset FAIL size={len(part)} -> recurse")
                current = list(part)
                n = 2
                reduced = True
                break
        if reduced:
            continue

        for part in subsets:
            if not part or len(part) == len(current):
                continue
            complement = _complement(current, part)
            if not complement:
                continue
            outcome = test(complement)
            if outcome is Outcome.FAIL:
                _log(f"  complement FAIL size={len(complement)} -> recurse")
                current = complement
                n = max(n - 1, 2)
                reduced = True
                break
        if reduced:
            continue

        if n < len(current):
            n = min(len(current), n * 2)
            _log(f"  increase granularity n={n}")
            continue
        return current


def _split(atoms: Sequence[T], n: int) -> list[list[T]]:
    size = len(atoms)
    n = max(1, min(n, size))
    parts: list[list[T]] = []
    start = 0
    for i in range(n):
        # Distribute remainder across the first (size % n) chunks.
        extra = 1 if i < (size % n) else 0
        step = (size // n) + extra
        parts.append(list(atoms[start : start + step]))
        start += step
    return [p for p in parts if p]


def _complement(atoms: Sequence[T], part: Sequence[T]) -> list[T]:
    drop = set(map(id, part))
    # Identity on the same objects; fall back to equality for primitives.
    if len(drop) != len(part):
        part_list = list(part)
        remaining = list(atoms)
        for item in part_list:
            try:
                remaining.remove(item)
            except ValueError:
                pass
        return remaining
    return [a for a in atoms if id(a) not in drop]
