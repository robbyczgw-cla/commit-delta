# Changelog

## 0.1.0 — 2026-08-18

First public release.

### Added
- Isolate a 1-minimal failure-inducing subset of a dirty Git working tree.
- File-level then hunk-level ddmin in an isolated worktree.
- CLI report plus optional `reduced.patch` and `reduced.json`.
- Treat Python `SyntaxError` / `ImportError` (and some `TypeError` / `AttributeError`) as UNRESOLVED (`125`).
- Fixture suite covering independent minima, confirm-flakes, and unbuildable subsets.

### Notes
- The result is a 1-minimal FAIL set, not a unique root cause.
- Atoms are hunks, not statements.

### Contributors
- Robby Czesany
