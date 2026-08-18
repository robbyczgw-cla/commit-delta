# commit-delta

**git bisect for a dirty working tree.**

HEAD is green. Your uncommitted changes are a mess. The test is red.
`commit-delta` throws hunks away until it has a **small set that still
fails**.

It does not explain the bug. It does not fix the bug. It does not
name one guilty line. Multiple hunks may interact; another 1-minimal
set may also fail. You get a reduced patch you can actually read.

```
HEAD:          PASS
Working tree:  14 files, 93 hunks, 567 lines, FAIL

$ commit-delta -- ./reproduce.sh

Minimal failure-inducing change set:

calc.py
  hunk 2
    -        acc = acc + item
    +        acc = acc - item
```

93 hunks → 1 hunk. Same failure.

On a real repo (`wsp-verify`, four feature commits left uncommitted):
28 files / 2230 lines → 2 files / 69 lines in 8 seconds. That run
returned *a* 1-minimal fail, not “the” bug — two other independent
fails existed in the same tree. That is expected.

## Install

Needs Git 2.5+ (`git worktree`) and Python 3.10+.

```bash
git clone git@github.com:robbyczgw-cla/commit-delta.git
cd commit-delta
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Private repo: use SSH or a GitHub token. Not on PyPI yet.

```bash
pip install "git+ssh://git@github.com/robbyczgw-cla/commit-delta.git"
```

## Use

```bash
# same test that is already red
commit-delta -- ./reproduce.sh
commit-delta -- pytest -q
commit-delta --output reduced.patch --json reduced.json -- npm test
```

The command after `--` runs in an **isolated worktree**. Your dirty
tree is only read.

| You want | Flag |
|---|---|
| a patch to inspect | `--output reduced.patch` |
| JSON for an agent | `--json reduced.json` |
| each trial logged | `--verbose` |
| flake-resistant FAIL | `--confirm 3` |
| hung tests | `--timeout 60s` |
| only some paths | `--include src` / `--exclude tests` |
| no traceback heuristics | `--strict-exits` |

### Your test command

Same contract as `git bisect run`:

| Exit | Meaning |
|---|---|
| `0` | PASS |
| `125` | UNRESOLVED — this subset cannot build, parse, or import |
| other | FAIL — the failure you want isolated |

If compile errors and the real assertion both exit `1`, wrap the
command and map “cannot run” to `125`. For Python, `SyntaxError` /
`ImportError` and (when no `AssertionError` is in the output)
`TypeError` / `AttributeError` are already treated as UNRESOLVED.

The test must work from a **fresh checkout + the candidate hunks**.
It will not see your `node_modules` or `.venv`. Either the command
installs what it needs, or you point at a test that can run bare.

## What it does

1. Check HEAD is GOOD and the full dirty tree is BAD.
2. Snapshot `git diff HEAD -U0` plus untracked text files.
3. Reduce files first, then hunks (ddmin).
4. Apply each candidate in a temporary worktree. Cache results.
5. Print a report. Optionally write `reduced.patch` and `reduced.json`.

Your working tree is never checked out, reset, or rewritten.

## For coding agents

Read **[AGENTS.md](AGENTS.md)**. One run after tests go red:

```bash
commit-delta --output reduced.patch --json reduced.json -- <the-same-test>
```

Then work only on `reduced.json` / `reduced.patch`. Do not loop. Do
not invent MCP. `unique_not_guaranteed` is always true.

## Not this

| Tool | Answers |
|---|---|
| `git bisect` | which *commit* in history broke |
| `git add -p` | how to stage hunks by hand |
| Shrink Ray / C-Reduce | shrink a failing *input file* |
| **commit-delta** | shrink an uncommitted *change set* |

## Limits (v0.1)

- Atoms are hunks, not statements. A 40-line rewrite is one piece.
- Result is **a** 1-minimal FAIL set. Uniqueness is not guaranteed.
- Text only. No binaries, submodules, or ignored build trees.
- Isolated worktree has no `node_modules` / local venv unless your
  command creates them.
- Renames and odd encodings are best-effort.
- `npm test` / `tsc` / `cargo` need an exit-125 wrapper if they use
  `1` for both “won’t compile” and “assertion failed”.

Full list: [docs/limitations.md](docs/limitations.md).

## Develop

```bash
pip install -e ".[dev]"
make test    # 85 tests
make bench   # fixtures A–G + demo
make demo    # materialize the 567-line dirty tree and reduce it
```

| Fixture | Expectation |
|---|---|
| A | one bad hunk among 20+ noise hunks |
| B | A and B each pass; A+B fail — both kept |
| C | some subsets do not import — UNRESOLVED, still converges |
| D | two independent minima — returns one |
| E | `--confirm 3` still finds the hunk |
| F | messy refactor, no exit 125 — fat hunk + new file |
| G | four bits must all flip — keeps all four, drops noise |

## Docs

- [AGENTS.md](AGENTS.md) — when to run, what to do with the output
- [docs/algorithm.md](docs/algorithm.md) — ddmin, heuristics, apply
- [docs/limitations.md](docs/limitations.md) — what v0.1 will not do
- [docs/benchmark.md](docs/benchmark.md) — trial counts and the demo
- [docs/competition.md](docs/competition.md) — why this is not git bisect

## License

Apache-2.0. See [LICENSE](LICENSE).
