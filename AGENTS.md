# AGENTS.md

Use this file. Do not invent a wrapper, MCP server, or second search.

## What this tool is

`commit-delta` shrinks a **dirty Git working tree** against a test command
to a **1-minimal failure-inducing change set**.

It does not explain the bug, fix the bug, or name a single guilty line.

## When to run it

All of these are true:

1. `HEAD` is known good (the test passes on a clean checkout).
2. The working tree has many uncommitted changes.
3. The same test fails on the full dirty tree.
4. You (or the human) cannot tell which part of the diff matters.

Typical moment: you just edited many files, tests went red.

## When not to run it

- No reproducible command exists.
- `HEAD` already fails the test.
- The dirty tree already *passes* the test (nothing to isolate).
- You only need to stage a commit (`git add -p`), not find a failure.
- You need a historical culprit (`git bisect`).

## How to run

```bash
commit-delta --verbose --output reduced.patch --json reduced.json -- <the-same-test-you-already-run>
```

Examples:

```bash
commit-delta --output reduced.patch --json reduced.json -- pytest -q
commit-delta --output reduced.patch --json reduced.json -- ./reproduce.sh
commit-delta --exclude tests --output reduced.patch -- pytest -q tests/test_foo.py
```

The command after `--` must be the **same predicate** you used to decide
the tree is bad. It runs in an isolated worktree. It will not touch the
user's working tree.

Exit of *that* command:

| Exit | Meaning |
|---|---|
| 0 | PASS |
| 125 | UNRESOLVED — cannot build / parse / import this subset |
| other | FAIL |

If compile errors and assertion failures both exit `1`, wrap the command
and map unbuildable subsets to `125`. For Python, SyntaxError / ImportError
and (when no AssertionError is present) TypeError / AttributeError are
already treated as UNRESOLVED.

## What to do with the output

1. Prefer `reduced.json` over scraping the prose report. `minimal` is
   **a** 1-minimal FAIL set, not "the" cause. `unique_not_guaranteed` is
   always true.
2. Work only on that reduced set (or `reduced.patch`).
3. Do not "clean up" or revert the rest unless the human asks.
4. Do not re-run `commit-delta` in a loop to get a smaller answer.
5. If the leftover set is almost the whole input, say so. The tool
   provided little value; stop.

## What not to do

- Do not call `commit-delta` once per file or per hunk. One run.
- Do not add AI, MCP, or a web UI around it.
- Do not claim a single line is the root cause.
- Do not mutate the user's working tree to experiment. The tool
  already isolates candidates.
- Do not treat UNRESOLVED as FAIL or as PASS.
