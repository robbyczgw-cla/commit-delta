# Algorithm

`commit-delta` looks for a **1-minimal failure-inducing change set**.

That is a subset `S` of the dirty-tree hunks such that:

- `S` FAILs the reproduction command
- every proper subset formed by dropping a single remaining hunk PASSes
  (or, rarely, is UNRESOLVED)

It does **not** claim `S` is the unique cause, the smallest possible
subset in the lattice, or a single line of guilt. Another 1-minimal
subset may also FAIL. Interacting hunks stay together.

## Atoms

Changes are captured once, up front, and never re-diffed:

1. `git diff HEAD -U0` for staged + unstaged tracked edits
2. each untracked, non-ignored text file as one ADD hunk

`-U0` drops context so each contiguous edit is its own hunk. Adjacent
line edits still collapse into one hunk; we do not split below that
in v0.1.

## Applying a subset

Hunks record **original (HEAD) coordinates**. A subset is applied by
editing the HEAD file from the bottom up, independently of omitted
hunks. We do not feed a partial unified diff to `patch(1)` and hope
fuzz factor saves us.

That is the difference between "this subset is untestable" and "git
apply was confused". Apply failures still exist (encoding, unexpected
line endings) and are UNRESOLVED.

Application happens inside a disposable `git worktree` pinned at HEAD.
The user's working tree is only read.

## Three outcomes

The reproduction command is classified like `git bisect run`:

| Exit | Meaning |
|---|---|
| 0 | PASS (this subset is good) |
| 125 | UNRESOLVED (cannot test: syntax, missing import, build, timeout) |
| anything else | FAIL, unless a traceback heuristic matches |
| timeout / spawn error | UNRESOLVED |

### Traceback heuristics (on by default)

A naive `pytest` / `python` command often uses exit 1 for both
"cannot import this subset" and "the assertion failed". If those
are both FAIL, ddmin will reduce *to the import error* and hand
back a patch that does not even run the test.

When the exit is already non-zero, commit-delta also looks at
stdout/stderr for an allowlisted exception:

- `SyntaxError`, `IndentationError`, `TabError`
- `ImportError`, `ModuleNotFoundError`
- `TypeError`, `AttributeError` (incomplete feature slice)

If the same output also contains an `AssertionError`, that wins:
the subset ran a real check, so it is FAIL.

`NameError` stays FAIL — that is often the bug. `--strict-exits`
turns the heuristic off. It is not a compiler and will not catch
TypeScript / Java / Rust build failures; wrap those to 125.

UNRESOLVED is neither interesting nor innocent. ddmin will not reduce
*to* an UNRESOLVED subset and will not treat it as PASS. That is how
broken intermediate patches avoid poisoning the search.

## Search

Two-phase Zeller ddmin (`docs` / `src/commit_delta/ddmin.py`):

1. **File level.** Each file's hunks are one atom. Cheap rejection of
   irrelevant files.
2. **Hunk level.** Remaining hunks are atoms. This is the result.

ddmin, in short:

- split the current set into `n` pieces (start `n=2`)
- if a piece FAILs, continue on that piece (`n=2`)
- else if a complement FAILs, continue on the complement
- else increase granularity (`n -> 2n`) until pieces are singletons
- stop: the current set is 1-minimal w.r.t. this partition order

UNRESOLVED pieces are skipped, same as PASS, for the purpose of
*reducing to them*. They do not prove a hunk is innocent.

## Cache, confirm, timeout

- Every tested set of hunk ids is cached.
- `--confirm N` requires N identical PASS or FAIL results. A mix,
  including a flake that PASSes once and FAILs once, is UNRESOLVED.
- `--timeout` kills the process group and returns UNRESOLVED.

## Witness

After ddmin returns, the tool removes each leftover hunk in turn and
reports the outcome. If every removal PASSes, the set is empirically
1-minimal. That check is printed in the report so the user can see
why the leftover hunks were kept.

## Complexity

ddmin is quadratic in the worst case in the number of atoms, but the
file-level pass usually throws away most of the tree first. Each
trial costs one worktree reset + one command invocation. Cache hits
are free.
