#!/usr/bin/env python3
"""Materialize the killer-demo fixture as a real git checkout."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support.builders import build_demo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dest", nargs="?", default="demo-repo")
    args = parser.parse_args()
    dest = Path(args.dest).resolve()
    if dest.exists():
        shutil.rmtree(dest)
    build_demo(dest)
    print(f"demo repository at {dest}")
    print("  git status  — dirty tree vs good HEAD")
    print("  commit-delta -- ./reproduce.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
