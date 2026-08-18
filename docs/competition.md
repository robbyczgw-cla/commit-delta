# Competition check (August 2026)

Question: is there an **active** project that already provides this exact workflow?

```
dirty Git working tree + test command
    -> automated minimal failure-inducing patch subset
```

**Verdict: no. Build.**

Generic delta debugging exists. That is expected and is not a kill.
Nothing found that packages the Git-native working-tree workflow
`commit-delta` targets.

## What was inspected

### git bisect

Finds a **commit** in history. It requires the failure to already be
committed, and it treats each commit as an atomic blob.

It does not:

- inspect an uncommitted dirty tree
- split a large local change into hunks
- return a reduced patch

`git bisect` is the inspiration, not a substitute.
`commit-delta` is "bisect the uncommitted delta", not "bisect history".

### git add -p

Interactive hunk staging. The human is the search algorithm.

Useful for composing commits. Useless for automatically finding a
minimal failure-inducing subset against a test command.

### diffbisect and similarly named projects

Searched GitHub and the public web for `diffbisect`, `hunk-bisect`,
`patch-bisect`, `git-ddmin`, `git-minimize-diff`, `git-reduce-patch`,
`isolate-hunk`, and "working tree delta debugging".

No active project turned up that:

1. reads a dirty working tree
2. takes a test command
3. reduces to a minimal failing hunk subset

A few adjacent names exist (`git-llm-pick` repairs cherry-picks with an
LLM; `git bisect-find` wraps commit bisection). None are this tool.

### Shrink Ray, C-Reduce, cvise, picire, halfempty, delta

These are **test-case reducers**. They shrink a failing *input file*
(or a single source file treated as input) while a predicate stays
interesting.

They do not:

- snapshot `git diff HEAD`
- isolate candidates in temporary worktrees
- treat hunks as the reduction atoms
- speak Git's PASS / FAIL / skip(125) contract in a working-tree
  workflow

You *could* abuse Shrink Ray by stuffing a patch into a file and
writing a predicate that applies it. That is not a product. The
predicate, worktree isolation, three-outcome classification, and
report are the whole product.

### Academic / library delta debugging on changes

Zeller's original ddmin paper and the Debugging Book
`ChangeDebugger` isolate failure-inducing *patches between two
sources*. That is the right algorithm family.

What they are not:

- a CLI a developer runs as `commit-delta -- npm test`
- Git-worktree isolated
- maintained as a daily-driver OSS tool for dirty trees

`omegastar`, `ddmin-python`, and similar snippets implement the
algorithm, not the workflow.

### 2025–2026 GitHub scan

Recent public activity is dominated by:

- more `git bisect` wrappers and tutorials
- generic reducers (Shrink Ray still the modern input reducer)
- worktree managers (`worktrunk`, etc.)
- LLM cherry-pick helpers

No 2025–2026 project was found that ships the dirty-tree + test
command + minimal failing patch loop as a polished CLI.

## Differentiation (what we actually own)

| Tool | Input | Atom | Output |
|---|---|---|---|
| git bisect | commit history | commit | one commit |
| git add -p | dirty tree | hunk | staged index (manual) |
| Shrink Ray / C-Reduce | a test file | bytes / AST edits | smaller file |
| ChangeDebugger | two source trees | patch fragments | library result |
| **commit-delta** | dirty tree vs HEAD | file then hunk | 1-minimal failing patch |

The gap is the **workflow**, not the algorithm.

## Kill criterion on competition

Kill only if an active project already provides *this exact*
workflow, polished.

That criterion is **not** met as of 2026-08-17.

## Residual risk

Someone can compose `git diff` + a generic reducer in an afternoon.
The moat is reliability of subset application, UNRESOLVED handling,
and a report that a working programmer trusts. If those fail in the
spike, kill for technical reasons, not because ddmin exists.
