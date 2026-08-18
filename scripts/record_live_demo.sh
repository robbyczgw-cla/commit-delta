#!/usr/bin/env bash
# Record a real xfce4-terminal session of the demo fixture via Xvfb.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DISPLAY_N="${DISPLAY_N:-:97}"
OUT_DIR="${OUT_DIR:-$ROOT/docs}"
WORKDIR="${WORKDIR:-/tmp/cd-demo-video}"

if [[ ! -x "$WORKDIR/reproduce.sh" ]]; then
  "$ROOT/.venv/bin/python" "$ROOT/scripts/make_demo.py" "$WORKDIR"
fi

export PATH="$ROOT/.venv/bin:/usr/bin:/bin"
export DISPLAY="$DISPLAY_N"

Xvfb "$DISPLAY_N" -screen 0 1280x720x24 -ac +extension GLX +render -noreset >/tmp/cd-xvfb.log 2>&1 &
XPID=$!
sleep 0.5
xsetroot -solid '#0b0f14' || true
xfwm4 --compositor=off >/tmp/cd-xfwm4.log 2>&1 &
WMPID=$!
sleep 0.4

DEMO=/tmp/cd-live-demo.sh
cat > "$DEMO" <<'EOS'
#!/bin/bash
set -u
cd "$WORKDIR"
printf '\033[2J\033[H'
echo
echo "  commit-delta — git bisect for a dirty working tree"
echo
sleep 1.4
printf '  $ git diff --stat\n'
sleep 0.5
git --no-pager diff --stat HEAD
echo
sleep 2.2
printf '  $ commit-delta --verbose -- ./reproduce.sh\n'
sleep 0.7
commit-delta --verbose -- ./reproduce.sh
echo
sleep 12
EOS
# inject workdir because the heredoc is quoted
sed -i "s|cd \"\$WORKDIR\"|cd \"$WORKDIR\"|" "$DEMO"
chmod +x "$DEMO"

RAW=/tmp/cd-live-raw.mp4
ffmpeg -y -f x11grab -video_size 1280x720 -framerate 30 -i "$DISPLAY_N" \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -preset veryfast \
  "$RAW" >/tmp/cd-live-ffmpeg.log 2>&1 &
FFPID=$!
sleep 0.4

xfce4-terminal --display="$DISPLAY_N" --fullscreen --hold \
  --hide-menubar --hide-scrollbar --hide-toolbar --hide-borders \
  --font='DejaVu Sans Mono 12' \
  --color-bg='#0b0f14' --color-text='#e6edf3' \
  --title='commit-delta' \
  --command="$DEMO" >/tmp/cd-term.log 2>&1 &
sleep 17
kill "$FFPID" 2>/dev/null || true
wait "$FFPID" 2>/dev/null || true

ffmpeg -y -ss 0.7 -t 15.5 -i "$RAW" \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart \
  "$OUT_DIR/demo.mp4"
ffmpeg -y -i "$OUT_DIR/demo.mp4" \
  -vf "fps=12,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse" \
  -loop 0 "$OUT_DIR/demo.gif"

kill "$WMPID" 2>/dev/null || true
kill "$XPID" 2>/dev/null || true
echo "wrote $OUT_DIR/demo.mp4 and $OUT_DIR/demo.gif"
