# Limitations (v0.1)

Honest list. If a case is in here, the tool will not magically handle it.

## Will not touch your working tree

Candidates run in a temporary `git worktree`. The original dirty tree
is snapshotted via `git diff` / untracked file reads and then left
alone. If the process is killed hard enough to skip cleanup, leftover
directories under `/tmp/commit-delta-*` and stale worktree records
are possible; `git worktree prune` removes the records.

## What is captured

In scope:

- staged and unstaged edits to tracked **text** files
- untracked, non-ignored **text** files (one atom per file)

Out of scope / skipped with a warning:

- binary diffs
- Git submodules
- ignored files (`node_modules`, build output, `.venv`, …)
- file mode-only changes (chmod) without a content hunk

## What the isolated tree does not have

The probe worktree is a clean HEAD plus the candidate hunks. It does
**not** copy ignored or leftover untracked build artifacts unless
those artifacts are themselves part of the captured change set.

If `npm test` needs `node_modules`, the command must install them, or
you must use a test command that can run from a fresh checkout. Same
for compiled artifacts, virtualenvs, Docker volumes, etc.

## Reproduction command contract

The command must be meaningful from the probe worktree cwd:

| Exit | Meaning |
|---|---|
| 0 | PASS |
| 125 | UNRESOLVED (cannot build / parse / import) |
| other | FAIL |

If you wrap `npm test` and a missing file, a TypeScript compile error,
and the actual assertion failure all exit `1`, the tool cannot tell
UNRESOLVED from FAIL. That will stall reduction or keep extra hunks.
Write a thin wrapper that maps compile/import failures to 125.

For **Python**, v0.1 also applies a conservative traceback heuristic
(see [algorithm.md](algorithm.md)): `SyntaxError` / `ImportError` /
`ModuleNotFoundError` / `IndentationError` / `TypeError` /
`AttributeError` on a non-zero exit become UNRESOLVED — unless the
same output also has an `AssertionError`, which stays FAIL.
`NameError` does **not** become UNRESOLVED. Disable with
`--strict-exits`. This does not extend to `tsc`, `cargo`, or `javac`.

Timeouts are UNRESOLVED, not FAIL.

## Granularity

Atoms are hunks at `-U0`, not statements and not characters. A
contiguous 40-line rewrite is one atom. Adjacent edits merge. We
deliberately do not do AST-aware splitting in v0.1.

## Apply model

Subset application edits HEAD content using original-line coordinates.
This is reliable for ordinary multi-file text edits. It can still
fail on:

- mixed encodings (non-UTF-8 is skipped or UNRESOLVED)
- unusual newline conventions (`\ No newline at end of file` is
  best-effort; we always write a trailing newline for non-empty files)
- file renames (treated poorly; prefer add+delete)
- conflicts with smudge/clean filters

If apply is systematically wrong on your repo, stop. That is a kill
criterion.

## Completeness of the answer

The result is **a** 1-minimal FAIL set, not **the** cause.

- Two independent bugs can each FAIL the same test; one of them is
  returned (fixture D).
- A smaller non-1-minimal-adjacent subset is not searched for beyond
  ddmin's partition order.
- We never claim a single line is "the" bug.

## Flakes

`--confirm N` refuses to treat mixed PASS/FAIL as interesting. A
genuinely flaky failure may then look UNRESOLVED and refuse to
reduce. That is intentional. Fix the predicate or raise N and accept
that some flakes cannot be isolated.

## Scale

Each trial copies the HEAD tree into the probe worktree. Fine for
normal application repos. Painful for multi-gigabyte checkouts. No
parallel trials in v0.1.

## Platform

Developed and tested on Linux. Requires `git worktree`. Not tested
on Windows. macOS should work if `git worktree` does.

## Non-goals (still)

No AI explanations, no GitHub app, no IDE plugin, no cloud, no
automatic fix, no MCP, no web UI.
