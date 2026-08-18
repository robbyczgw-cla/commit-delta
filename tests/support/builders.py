from __future__ import annotations

from pathlib import Path

from tests.support.gitrepo import commit_all, init_repo, write, write_reproduce


def _fn_block(mod: str, idx: int, *, extra_comment: str = "stable") -> str:
    return (
        f"def {mod}_fn_{idx}(x):\n"
        f'    """{mod} helper {idx} ({extra_comment})."""\n'
        f"    acc = x\n"
        f"    acc = acc + 0  # keep-{idx}-a\n"
        f"    acc = acc + 0  # keep-{idx}-b\n"
        f"    acc = acc + 0  # keep-{idx}-c\n"
        f"    return acc\n"
    )


def _module(mod: str, n: int = 8) -> str:
    parts = [f'"""Generated module {mod}."""', "", f"NAME = {mod!r}", ""]
    for i in range(n):
        parts.append(_fn_block(mod, i))
        parts.append("")
    return "\n".join(parts)


def _dirty_module(mod: str, n: int = 8, *, noise_at: tuple[int, ...] = (0, 2, 5)) -> str:
    parts = [f'"""Generated module {mod}."""', "", f"NAME = {mod!r}", ""]
    for i in range(n):
        comment = "tweaked" if i in noise_at else "stable"
        parts.append(_fn_block(mod, i, extra_comment=comment))
        parts.append("")
    return "\n".join(parts)


def build_fixture_a(root: Path) -> Path:
    """20+ irrelevant hunks + one failing hunk."""
    repo = init_repo(root)
    write(repo / "core.py", _core_good())
    for name in "alpha beta gamma delta epsilon zeta eta theta".split():
        write(repo / f"{name}.py", _module(name))
    write_reproduce(repo, _repro_add())
    commit_all(repo, "good HEAD")

    write(repo / "core.py", _core_bad_subtract())
    for name in "alpha beta gamma delta epsilon zeta eta theta".split():
        write(repo / f"{name}.py", _dirty_module(name))
    return repo


def build_fixture_b(root: Path) -> Path:
    """A alone PASS, B alone PASS, A+B FAIL."""
    repo = init_repo(root)
    write(
        repo / "flags.py",
        '"""Feature flags."""\n\nENABLED = False\n',
    )
    write(
        repo / "app.py",
        '"""App."""\n\nfrom flags import ENABLED\n\n'
        "def run():\n"
        "    unused = 0  # keep\n"
        "    return 0\n",
    )
    write(repo / "noise.py", _module("noise", n=6))
    write_reproduce(
        repo,
        "from app import run\n"
        "raise SystemExit(0 if run() == 0 else 1)\n",
    )
    commit_all(repo, "good HEAD")

    write(
        repo / "flags.py",
        '"""Feature flags."""\n\nENABLED = True\n',
    )
    write(
        repo / "app.py",
        '"""App."""\n\nfrom flags import ENABLED\n\n'
        "def run():\n"
        "    unused = 0  # keep\n"
        "    if ENABLED:\n"
        "        return 99\n"
        "    return 0\n",
    )
    write(repo / "noise.py", _dirty_module("noise", n=6))
    return repo


def build_fixture_c(root: Path) -> Path:
    """Some subsets do not import/compile -> UNRESOLVED (exit 125)."""
    repo = init_repo(root)
    write(
        repo / "app.py",
        "def compute(x):\n"
        "    pad = 0  # keep\n"
        "    return x * 2\n",
    )
    write(repo / "noise.py", _module("noise", n=5))
    write_reproduce(
        repo,
        "import sys\n"
        "try:\n"
        "    from app import compute\n"
        "    result = compute(2)\n"
        "except (SyntaxError, ImportError, NameError, IndentationError, TypeError):\n"
        "    sys.exit(125)\n"
        "except Exception:\n"
        "    sys.exit(125)\n"
        "sys.exit(0 if result == 4 else 1)\n",
    )
    commit_all(repo, "good HEAD")

    # Three cooperating hunks, plus noise:
    # 1. new file extras.py (defines factor)
    # 2. import in app.py
    # 3. use factor in compute (the actual bug: *3 instead of *2)
    write(repo / "extras.py", "factor = 3\n")
    write(
        repo / "app.py",
        "from extras import factor\n"
        "\n"
        "def compute(x):\n"
        "    pad = 0  # keep\n"
        "    return x * factor\n",
    )
    write(repo / "noise.py", _dirty_module("noise", n=5))
    return repo


def build_fixture_d(root: Path) -> Path:
    """Two independent 1-minimal solutions."""
    repo = init_repo(root)
    write(repo / "left.py", "def value():\n    marker = 0  # keep\n    return 0\n")
    write(repo / "right.py", "def value():\n    marker = 0  # keep\n    return 0\n")
    write(repo / "noise.py", _module("noise", n=6))
    write_reproduce(
        repo,
        "from left import value as left_value\n"
        "from right import value as right_value\n"
        "ok = left_value() == 0 and right_value() == 0\n"
        "raise SystemExit(0 if ok else 1)\n",
    )
    commit_all(repo, "good HEAD")

    write(repo / "left.py", "def value():\n    marker = 0  # keep\n    return 1\n")
    write(repo / "right.py", "def value():\n    marker = 0  # keep\n    return 1\n")
    write(repo / "noise.py", _dirty_module("noise", n=6))
    return repo


def build_fixture_e(root: Path) -> Path:
    """Deterministic failure used with --confirm N.

    A companion flake mode is available by setting COMMIT_DELTA_FLAKE=1
    in the environment; that path is covered by unit tests of --confirm.
    """
    repo = init_repo(root)
    write(
        repo / "core.py",
        "def answer():\n    note = 'ok'  # keep\n    return 42\n",
    )
    write(repo / "noise.py", _module("noise", n=6))
    write_reproduce(
        repo,
        "import os\n"
        "import subprocess\n"
        "from pathlib import Path\n"
        "from core import answer\n"
        "\n"
        "ok = answer() == 42\n"
        "if os.environ.get('COMMIT_DELTA_FLAKE') == '1' and not ok:\n"
        "    git_dir = subprocess.check_output(\n"
        "        ['git', 'rev-parse', '--git-common-dir'], text=True\n"
        "    ).strip()\n"
        "    counter = Path(git_dir) / 'commit-delta-flake'\n"
        "    n = int(counter.read_text()) if counter.exists() else 0\n"
        "    n += 1\n"
        "    counter.write_text(str(n))\n"
        "    # Fail 2/3 of the time when the bug is present.\n"
        "    if n % 3 == 0:\n"
        "        raise SystemExit(0)\n"
        "    raise SystemExit(1)\n"
        "raise SystemExit(0 if ok else 1)\n",
    )
    commit_all(repo, "good HEAD")

    write(
        repo / "core.py",
        "def answer():\n    note = 'ok'  # keep\n    return 0\n",
    )
    write(repo / "noise.py", _dirty_module("noise", n=6))
    return repo


def build_fixture_messy(root: Path) -> Path:
    """Realistic WIP: fat fused hunk + new module, no exit-125 wrapper.

    The reproduction script is naive (exit 1 on any exception). Incomplete
    subsets raise ModuleNotFoundError; heuristics must mark those
    UNRESOLVED or ddmin will treat 'import failed' as the bug.

    The actual assertion failure lives in the middle of a large contiguous
    rewrite of checkout.total, so hunk-level cannot extract a one-line
    cause. The honest result is that fat hunk plus promo.py.
    """
    repo = init_repo(root)
    write(repo / "pricing.py", _pricing(dirty=False))
    write(repo / "checkout.py", _checkout_head())
    for name in "catalog inventory shipping notify audit".split():
        write(repo / f"{name}.py", _module(name, n=6))
    write_reproduce(
        repo,
        "from checkout import total\n"
        "items = [(2, 10), (3, 5)]\n"
        "raise SystemExit(0 if total(items) == 35 else 1)\n",
    )
    commit_all(repo, "good HEAD")

    write(repo / "pricing.py", _pricing(dirty=True))
    write(repo / "checkout.py", _checkout_dirty())
    write(repo / "promo.py", _promo_module())
    for name in "catalog inventory shipping notify audit".split():
        write(repo / f"{name}.py", _dirty_module(name, n=6))
    return repo


def build_fixture_dense(root: Path) -> Path:
    """Four independent bits must all flip or the test still passes.

    Expected: keep all four required hunks, drop noise. Documents the
    case where reduction is real but not dramatic.
    """
    repo = init_repo(root)
    for name in "w x y z".split():
        write(repo / f"{name}.py", f"FLAG = 0  # {name} off\n")
    write(repo / "noise.py", _module("noise", n=6))
    write_reproduce(
        repo,
        "import w, x, y, z\n"
        "ok = not (w.FLAG and x.FLAG and y.FLAG and z.FLAG)\n"
        "raise SystemExit(0 if ok else 1)\n",
    )
    commit_all(repo, "good HEAD")
    for name in "w x y z".split():
        write(repo / f"{name}.py", f"FLAG = 1  # {name} on\n")
    write(repo / "noise.py", _dirty_module("noise", n=6))
    return repo


def build_fixture_delete(root: Path) -> Path:
    """Deleting a tracked helper file is the failure; noise stays."""
    repo = init_repo(root)
    write(repo / "helper.py", "VALUE = 1\n")
    write(repo / "app.py", "from helper import VALUE\n\ndef run():\n    return VALUE\n")
    write(repo / "noise.py", _module("noise", n=4))
    write_reproduce(
        repo,
        "import sys\n"
        "try:\n"
        "    from app import run\n"
        "    result = run()\n"
        "except (ImportError, ModuleNotFoundError):\n"
        "    sys.exit(1)\n"
        "sys.exit(0 if result == 1 else 1)\n",
    )
    commit_all(repo, "good HEAD")
    (repo / "helper.py").unlink()
    write(repo / "noise.py", _dirty_module("noise", n=4))
    return repo


def build_demo(root: Path) -> Path:
    """400+ changed lines, 25+ hunks, one tiny failure."""
    repo = init_repo(root)
    modules = [
        "ledger",
        "ledger_tax",
        "ledger_fx",
        "ledger_fees",
        "ledger_audit",
        "ledger_export",
        "ledger_import",
        "ledger_report",
        "ledger_cache",
        "ledger_util",
        "ledger_format",
        "ledger_validate",
        "ledger_history",
    ]
    write(repo / "calc.py", _demo_calc(good=True))
    for name in modules:
        write(repo / f"{name}.py", _demo_module(name, dirty=False))
    write_reproduce(
        repo,
        "from calc import total\n"
        "raise SystemExit(0 if total([10, 20, 30]) == 60 else 1)\n",
    )
    commit_all(repo, "good HEAD")

    write(repo / "calc.py", _demo_calc(good=False))
    for name in modules:
        write(repo / f"{name}.py", _demo_module(name, dirty=True))
    return repo


def _core_good() -> str:
    return (
        "NOTE = 'sum'  # label-a\n"
        "PAD_A = 0  # label-b\n"
        "PAD_B = 0  # label-c\n"
        "PAD_C = 0  # label-d\n"
        "\n"
        "def add(a, b):\n"
        "    note = NOTE  # keep\n"
        "    scratch = PAD_A + PAD_B + PAD_C\n"
        "    return a + b + scratch\n"
    )


def _core_bad_subtract() -> str:
    # Several well-separated noise hunks in the same file as the bug so
    # file-level reduction is not enough: hunk-level must drop the labels.
    return (
        "NOTE = 'sum'  # label-a-dirty\n"
        "PAD_A = 0  # label-b-dirty\n"
        "PAD_B = 0  # label-c-dirty\n"
        "PAD_C = 0  # label-d-dirty\n"
        "\n"
        "def add(a, b):\n"
        "    note = NOTE  # keep\n"
        "    scratch = PAD_A + PAD_B + PAD_C\n"
        "    return a - b + scratch\n"
    )


def _repro_add() -> str:
    return (
        "from core import add\n"
        "raise SystemExit(0 if add(2, 2) == 4 else 1)\n"
    )


def _pricing(*, dirty: bool) -> str:
    tag = "rewritten" if dirty else "original"
    return (
        f'"""Unit pricing ({tag})."""\n'
        "\n"
        f"CURRENCY = 'USD'  # {tag}\n"
        "\n"
        "def line_total(qty, unit_price):\n"
        f'    """qty * unit ({tag})."""\n'
        "    return qty * unit_price\n"
    )


def _checkout_head() -> str:
    return (
        "from pricing import line_total\n"
        "\n"
        "def total(items):\n"
        "    acc = 0\n"
        "    for qty, price in items:\n"
        "        acc += line_total(qty, price)\n"
        "    return acc\n"
    )


def _checkout_dirty() -> str:
    # Every line of total() changes so -U0 emits one fat hunk. The promo
    # import sits inside that hunk: drop promo.py and the hunk raises
    # ModuleNotFoundError when total() runs. Unchanged lines in the
    # middle would split the hunk and leave a NameError-only subset.
    return (
        "from pricing import line_total\n"
        "\n"
        "def total(basket):\n"
        "    from promo import apply_promo\n"
        "    running = 0\n"
        "    seen = []\n"
        "    debug_left = 0\n"
        "    debug_right = 0\n"
        "    for qty, price in basket:\n"
        "        base = line_total(qty, price)\n"
        "        labelled = ('line', qty, price, base)\n"
        "        seen.append(labelled)\n"
        "        debug_left += qty\n"
        "        debug_right += price\n"
        "        promoted = apply_promo(base)\n"
        "        adjusted = promoted - 1  # off-by-one, buried in the rewrite\n"
        "        running += adjusted\n"
        "        scratch = debug_left + debug_right + len(seen)\n"
        "        running = running + scratch * 0\n"
        "    return running\n"
    )


def _promo_module() -> str:
    return (
        '"""Promotions extracted during the WIP refactor."""\n'
        "\n"
        "def apply_promo(amount):\n"
        "    # Identity on purpose: the failure is the -1 in checkout,\n"
        "    # but the new module is required for the rewrite to import.\n"
        "    bump = 0\n"
        "    tagged = amount + bump\n"
        "    return tagged\n"
    )


def _demo_calc(*, good: bool) -> str:
    op = "acc + item" if good else "acc - item"
    label = "stable" if good else "tweaked"
    # Extra separated constants so the failing file also has noise hunks.
    return (
        '"""Public calculator."""\n'
        "\n"
        f"VERSION = '{label}'\n"
        f"SCALE = 1  # {label}\n"
        f"BIAS = 0  # {label}\n"
        "\n"
        "def total(items):\n"
        "    acc = 0\n"
        "    for item in items:\n"
        f"        acc = {op}\n"
        "    return acc * SCALE + BIAS\n"
        "\n"
        f"def banner():\n"
        f"    return VERSION\n"
    )


def _demo_module(name: str, *, dirty: bool) -> str:
    """Large-ish module with several well-separated edits when dirty."""
    lines = [f'"""{name} support (generated)."""', "", f"TAG = {name!r}", ""]
    for i in range(12):
        comment = "rewritten" if dirty and i in (1, 4, 8) else "original"
        # Extra body lines so the dirty tree is hundreds of changed lines.
        extra = []
        for j in range(6):
            if dirty and i in (1, 4, 8) and j == 3:
                extra.append(f"    scratch = scratch + {j}  # {comment}-{j}")
            else:
                extra.append(f"    scratch = scratch + {j} - {j}  # {comment}-{j}")
        lines.append(f"def {name}_op_{i}(n):")
        lines.append(f'    """{name} op {i} ({comment})."""')
        lines.append("    scratch = n")
        lines.extend(extra)
        if dirty and i == 10:
            lines.append("    scratch = scratch + 0  # extra trailer")
        lines.append("    return scratch")
        lines.append("")
    return "\n".join(lines) + "\n"
