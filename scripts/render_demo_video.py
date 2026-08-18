#!/usr/bin/env python3
"""Render a terminal-style demo video from the real fixture run."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FPS = 30
COLS = 88
ROWS = 28
MARGIN_X = 36
MARGIN_Y = 78
LINE_H = 22

BG = (11, 15, 20)
FG = (230, 237, 243)
DIM = (125, 133, 144)
GREEN = (63, 185, 80)
RED = (255, 123, 114)
AMBER = (210, 153, 34)
BLUE = (88, 166, 255)
CYAN = (121, 192, 255)
PROMPT = (126, 231, 135)
BAR = (22, 27, 34)
MINUS = (255, 161, 152)
PLUS = (126, 231, 135)
WHITE = (255, 255, 255)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

STAT = """\
 calc.py            |  8 ++++----
 ledger.py          | 43 ++++++++++++++++++++++---------------------
 ledger_audit.py    | 43 ++++++++++++++++++++++---------------------
 ledger_cache.py    | 43 ++++++++++++++++++++++---------------------
 ledger_export.py   | 43 ++++++++++++++++++++++---------------------
 ledger_fees.py     | 43 ++++++++++++++++++++++---------------------
 ... 8 more files ...
 14 files changed, 290 insertions(+), 277 deletions(-)"""

LOG = [
    ("dim", "verify HEAD is GOOD"),
    ("pass", "  [1] HEAD {} PASS  (0.03s)"),
    ("dim", "verify full working tree is BAD"),
    ("fail", "  [2] working-tree {calc.py#1, calc.py#2, +91 more} FAIL  (0.03s)"),
    ("dim", "captured 14 files, 93 hunks, 567 changed lines"),
    ("blue", "phase 1: file-level ddmin (14 files)"),
    ("fail", "  [3] file-subset  7 files  FAIL"),
    ("fail", "  [4] file-subset  4 files  FAIL"),
    ("fail", "  [5] file-subset  2 files  FAIL"),
    ("fail", "  [6] file-subset  {calc.py}  FAIL"),
    ("dim", "phase 1 kept 1 file / 2 hunks"),
    ("blue", "phase 2: hunk-level ddmin (2 hunks)"),
    ("pass", "  [7] hunk-subset  {calc.py#1}  PASS"),
    ("fail", "  [8] hunk-subset  {calc.py#2}  FAIL"),
]

REPORT = """\
Minimal failure-inducing change set:

calc.py
  hunk 2  def total(items):
    -        acc = acc + item
    +        acc = acc - item

Full working tree: FAIL  14 files, 93 hunks, 567 lines
Reduced patch:     FAIL  1 file,  1 hunk,   2 lines
Reduction:         93 -> 1 hunks (99% fewer)

1-minimal: yes   Trials: 8   0.26s"""


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def color_for(kind: str) -> tuple[int, int, int]:
    return {
        "pass": GREEN,
        "fail": RED,
        "dim": DIM,
        "blue": BLUE,
        "cmd": CYAN,
        "prompt": PROMPT,
        "plain": FG,
        "minus": MINUS,
        "plus": PLUS,
        "title": WHITE,
    }.get(kind, FG)


class Terminal:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []
        self.mono = font(FONT, 17)
        self.mono_b = font(FONT_B, 17)
        self.sans = font(SANS, 15)
        self.sans_b = font(SANS, 22)

    def push(self, kind: str, text: str) -> None:
        self.lines.append((kind, text))
        overflow = len(self.lines) - ROWS
        if overflow > 0:
            self.lines = self.lines[overflow:]

    def extend(self, kind: str, block: str) -> None:
        for raw in block.splitlines():
            self.push(kind, raw)

    def clear(self) -> None:
        self.lines = []

    def render(self, typed: str = "") -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, W, 48), fill=BAR)
        draw.ellipse((22, 16, 36, 30), fill=(255, 95, 86))
        draw.ellipse((44, 16, 58, 30), fill=(255, 189, 46))
        draw.ellipse((66, 16, 80, 30), fill=(39, 201, 63))
        draw.text((110, 13), "commit-delta  —  ~/demo", font=self.sans, fill=DIM)
        y = MARGIN_Y
        for kind, text in self.lines:
            face = self.mono_b if kind in {"fail", "pass", "title"} else self.mono
            draw.text((MARGIN_X, y), text[:COLS], font=face, fill=color_for(kind))
            y += LINE_H
        if typed:
            draw.text((MARGIN_X, y), typed[:COLS], font=self.mono, fill=CYAN)
        draw.rectangle((0, H - 36, W, H), fill=BAR)
        draw.text(
            (MARGIN_X, H - 28),
            "git bisect for a dirty working tree",
            font=self.sans,
            fill=DIM,
        )
        return img


def hold(frames: list[Image.Image], img: Image.Image, seconds: float) -> None:
    frames.extend([img] * max(1, int(seconds * FPS)))


def type_command(term: Terminal, frames: list[Image.Image], cmd: str) -> None:
    prefix = "$ "
    term.push("prompt", "")
    # replace the blank we just pushed while typing
    term.lines.pop()
    shown = prefix
    for i, ch in enumerate(cmd):
        shown = prefix + cmd[: i + 1]
        frames.append(term.render(shown + "█"))
        if ch == " ":
            frames.extend([term.render(shown + "█")] * 2)
    hold(frames, term.render(shown + "█"), 0.25)
    term.push("cmd", prefix + cmd)
    hold(frames, term.render(), 0.2)


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/root/hunkhunt/docs")
    out_dir.mkdir(parents=True, exist_ok=True)
    term = Terminal()
    frames: list[Image.Image] = []

    term.push("title", "commit-delta")
    term.push("dim", "git bisect for a dirty working tree")
    term.push("plain", "")
    term.push("plain", "HEAD is green. The working tree is a mess. The test is red.")
    hold(frames, term.render(), 2.4)

    type_command(term, frames, "git diff --stat")
    for i, line in enumerate(STAT.splitlines()):
        kind = "dim" if line.startswith(" ...") else "plain"
        if "files changed" in line:
            kind = "blue"
        term.push(kind, line)
        hold(frames, term.render(), 0.12 if i < 6 else 0.35)
    hold(frames, term.render(), 1.1)

    type_command(term, frames, "commit-delta --verbose -- ./reproduce.sh")
    for kind, line in LOG:
        term.push(kind, line)
        hold(frames, term.render(), 0.38)
    hold(frames, term.render(), 0.6)

    term.clear()
    for line in REPORT.splitlines():
        if line.startswith("-"):
            kind = "minus"
        elif line.startswith("+") or line.startswith("    +"):
            kind = "plus"
        elif "Minimal" in line:
            kind = "title"
        elif "FAIL" in line and "PASS" not in line:
            kind = "fail"
        elif "1-minimal" in line or "Reduction" in line:
            kind = "pass"
        elif line.startswith("calc.py") or line.startswith("  hunk"):
            kind = "blue"
        else:
            kind = "plain"
        # fix plus detection for indented plus
        stripped = line.lstrip()
        if stripped.startswith("+"):
            kind = "plus"
        elif stripped.startswith("-") and "acc" in line:
            kind = "minus"
        term.push(kind, line)
        hold(frames, term.render(), 0.16)
    hold(frames, term.render(), 3.2)

    term.clear()
    term.push("title", "93 hunks  →  1 hunk")
    term.push("plain", "")
    term.push("fail", "full dirty tree     FAIL   567 changed lines")
    term.push("pass", "reduced patch       FAIL   2 changed lines")
    term.push("plain", "")
    term.push("dim", "A minimal failure-inducing change set.")
    term.push("dim", "Not “the” cause. Another 1-minimal subset may also fail.")
    hold(frames, term.render(), 3.0)

    tmp = Path(tempfile.mkdtemp(prefix="cd-demo-frames-"))
    try:
        for i, frame in enumerate(frames):
            frame.save(tmp / f"f{i:05d}.png")
        mp4 = out_dir / "demo.mp4"
        gif = out_dir / "demo.gif"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(tmp / "f%05d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "20",
                "-movflags",
                "+faststart",
                str(mp4),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp4),
                "-vf",
                "fps=12,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse",
                "-loop",
                "0",
                str(gif),
            ],
            check=True,
            capture_output=True,
        )
        print(f"wrote {mp4} ({mp4.stat().st_size // 1024}K)")
        print(f"wrote {gif} ({gif.stat().st_size // 1024}K)")
        print(f"frames={len(frames)} duration={len(frames) / FPS:.1f}s")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
