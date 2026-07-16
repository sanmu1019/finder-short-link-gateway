#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
screen="${FINDER_SCREEN:-1440x900x24}"
vnc_password="${FINDER_VNC_PASSWORD:-}"

if [[ -z "${vnc_password}" ]]; then
  echo "FINDER_VNC_PASSWORD is required" >&2
  exit 1
fi

mkdir -p "${FINDER_PROFILE_DIR:-/data/chromium-profile}"

Xvfb "${DISPLAY}" -screen 0 "${screen}" -nolisten tcp &
xvfb_pid=$!
sleep 1

openbox-session >/tmp/openbox.log 2>&1 &

x11vnc -storepasswd "${vnc_password}" /tmp/x11vnc.pass >/dev/null
x11vnc \
  -display "${DISPLAY}" \
  -rfbauth /tmp/x11vnc.pass \
  -forever \
  -shared \
  -localhost \
  -rfbport 5900 \
  -quiet &

websockify \
  --web=/usr/share/novnc/ \
  6080 \
  localhost:5900 \
  >/tmp/websockify.log 2>&1 &

cleanup() {
  kill "${xvfb_pid}" 2>/dev/null || true
}
trap cleanup EXIT

exec uvicorn app.main:app \
  --host "${FINDER_BIND_HOST:-0.0.0.0}" \
  --port "${FINDER_PORT:-8790}" \
  --no-access-log \
  --proxy-headers \
  --forwarded-allow-ips="127.0.0.1"
