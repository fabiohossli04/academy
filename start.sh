#!/usr/bin/env bash
# Startet die Academy auf einem lokalen Server und oeffnet den Browser.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8777}"
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT laeuft schon - oeffne nur den Browser."
else
  python3 -m http.server "$PORT" --bind 127.0.0.1 >/tmp/academy-server.log 2>&1 &
  sleep 0.6
fi
open "http://127.0.0.1:$PORT/"
echo "Academy laeuft auf http://127.0.0.1:$PORT/"
echo "Beenden:  lsof -ti tcp:$PORT | xargs kill"
