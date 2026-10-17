#!/usr/bin/env bash
# Start the whole DharRakshak app (backend + frontend) with one command.
#
#   ./scripts/run_demo.sh            → open http://localhost:5173
#   API_PORT=8001 WEB_PORT=5174 ./scripts/run_demo.sh   (other ports)
#
# Ctrl+C stops both servers. First-time setup steps (venv, packages,
# model weights) are in README.md; this script checks for them and tells
# you what's missing.
set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

# ----- checks ---------------------------------------------------------------
if [ ! -x .venv/bin/uvicorn ]; then
  echo "✗ Python environment not set up. See README.md → 'First-time setup'."; exit 1
fi
if [ ! -f models/plant-disease-mobilenetv2/mobilenetv2_plant.pth ]; then
  echo "• Image model weights missing — downloading (~9 MB)…"
  .venv/bin/python scripts/download_model.py
fi
if [ ! -d frontend/node_modules ]; then
  echo "• Installing frontend packages (first run only)…"
  (cd frontend && npm install --no-fund --no-audit)
fi
if ! grep -qs '^GROQ_API_KEY=.\+' .env; then
  echo "⚠ No GROQ_API_KEY in .env — the chatbot will use saved answers and voice input is off."
  echo "  (cp .env.example .env, then paste your key)"
fi
for port in "$API_PORT" "$WEB_PORT"; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "✗ Port $port is already in use (maybe the app is already running?)."
    echo "  Stop it, or pick other ports: API_PORT=8001 WEB_PORT=5174 $0"; exit 1
  fi
done

# ----- start ----------------------------------------------------------------
.venv/bin/uvicorn backend.main:app --port "$API_PORT" &
API_PID=$!
(cd frontend && VITE_API_MODE=api DHARRAKSHAK_API_PROXY="http://localhost:$API_PORT" exec node_modules/.bin/vite --port "$WEB_PORT" --strictPort) &
WEB_PID=$!

stop() {
  trap - EXIT INT TERM   # run the cleanup only once
  echo; echo "Stopping DharRakshak…"
  pkill -P "$WEB_PID" 2>/dev/null || true
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap stop EXIT INT TERM

# Wait until the backend answers, then print the address.
for _ in $(seq 1 60); do
  if curl -fs "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done
echo
echo "✅ DharRakshak is running"
echo "   App:      http://localhost:$WEB_PORT"
echo "   API docs: http://localhost:$API_PORT/docs"
echo "   Press Ctrl+C to stop."
wait
