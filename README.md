# commit-delta

**git bisect for a dirty working tree.**

You have a known-good `HEAD`, a messy uncommitted change, and a test
that fails on the full working tree. `commit-delta` searches for a
**minimal failure-inducing change set** — the smallest 1-minimal
subset of those hunks that still fails the test.

It will not tell you that one line is "the cause". Multiple hunks may
interact. Another 1-minimal subset may also fail. The output is a
reduced patch you can actually read.

```
HEAD:          PASS
Working tree:  14 files, 93 hunks, 567 lines, FAIL

$ commit-delta -- ./reproduce.sh

Minimal failure-inducing change set:

calc.py
  hunk 2  def total(items):
    -        acc = acc + item
    +        acc = acc - item
```

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Git 2.5+ (`git worktree`) and Python 3.10+.

## Usage

```bash
commit-delta -- ./reproduce.sh
commit-delta -- npm test
commit-delta --confirm 3 --timeout 60s --output reduced.patch -- pytest -q
```

The command after `--` runs inside an **isolated worktree**, never in
your dirty tree.

| Flag | Meaning |
|---|---|
| `--confirm N` | require N consistent PASS/FAIL results (flakes → UNRESOLVED) |
| `--timeout DURATION` | per-trial timeout (`60s`, `2m`; `0` disables) |
| `--include PATH` | only these paths (repeatable; prefix or glob) |
| `--exclude PATH` | skip these paths |
| `--verbose` | log every candidate |
| `--strict-exits` | ignore traceback heuristics; only 0 / 125 / other |
| `--output FILE` | write the reduced patch |
| `--json FILE` | write a machine-readable result (for agents) |
| `--log-file FILE` | write the trial log |

### Exit codes of *your* command

Same contract as `git bisect run`:

| Exit | Meaning |
|---|---|
| `0` | PASS |
| `125` | UNRESOLVED — cannot build, parse, or import this subset |
| other | FAIL — the failure you want isolated |

If compile errors and the real failure both exit `1`, wrap the command
and map unbuildable subsets to `125`. For Python, `SyntaxError`,
`ImportError`, and (when no assertion ran) `TypeError` /
`AttributeError` are treated as UNRESOLVED automatically
(`--strict-exits` disables that). See [docs/limitations.md](docs/limitations.md).

## What it does

1. Verify `HEAD` is GOOD.
2. Verify the full dirty tree is BAD.
3. Snapshot tracked diffs (`git diff HEAD -U0`) and untracked text files.
4. Reduce at **file** granularity, then **hunk** granularity (ddmin).
5. Evaluate each candidate in a temporary worktree.
6. Cache subsets. Time out hung tests. Optionally confirm flakes.
7. Print a report and, optionally, a patch that still fails.

Your working tree is not checked out, reset, or rewritten.

## For coding agents

Most agents only need [AGENTS.md](AGENTS.md). One run after tests go
red, then keep working on `reduced.patch`. No MCP, no wrapper.

## What it is not

| Tool | Solves |
|---|---|
| `git bisect` | which *commit* in history broke |
| `git add -p` | interactive staging |
| Shrink Ray / C-Reduce | shrink a failing *input file* |
| **commit-delta** | shrink an uncommitted *change set* |

Competition notes: [docs/competition.md](docs/competition.md).

## Fixtures and tests

```bash
source .venv/bin/activate
pip install -e ".[dev]"
make test
make bench
```

| Fixture | Expectation |
|---|---|
| A | 20+ noise hunks + one bad hunk → one hunk |
| B | A alone PASS, B alone PASS, A+B FAIL → both kept |
| C | some subsets do not import → UNRESOLVED, search still converges |
| D | two independent minima → one 1-minimal set; uniqueness not claimed |
| E | `--confirm 3` still finds the deterministic bad hunk |
| F | messy refactor, no exit 125: fat hunk + new module; heuristic catches ImportError |
| G | four bits must all flip → keeps all four, drops noise |
| demo | 400+ lines / 25+ hunks → one hunk |

## Docs

- [docs/algorithm.md](docs/algorithm.md) — ddmin, UNRESOLVED, apply model
- [docs/limitations.md](docs/limitations.md) — what v0.1 will not do
- [docs/benchmark.md](docs/benchmark.md) — candidate counts and the demo
- [docs/competition.md](docs/competition.md) — why this is not git bisect

## License

Apache-2.0. See [LICENSE](LICENSE).
