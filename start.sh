#!/bin/bash
# Report-Viewer - Start script (cross-platform: Git Bash / Linux / macOS)
# Usage: ./start.sh
#
# Ensures a dedicated runtime venv at ~/.report_viewer/venv (self-contained,
# project-independent), then launches the Flask backend on :8765 in the
# background and verifies health (retry loop: first run compiles bytecode).
# Data (reports/comments) lives in ~/.report_viewer/ (see app.py: DATA_DIR).
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
mkdir -p logs

# --- data root (must match app.py: Path.home() / ".report_viewer") ---
DATA_DIR="${HOME}/.report_viewer"
mkdir -p "$DATA_DIR"
VENV_DIR="$DATA_DIR/venv"

# --- dedicated venv (self-contained runtime, project-independent) ---
if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
  PY="$VENV_DIR/Scripts/python.exe"
elif [ -f "$VENV_DIR/bin/python" ]; then
  PY="$VENV_DIR/bin/python"
else
  echo "First run: creating dedicated venv at $VENV_DIR ..."
  if command -v uv >/dev/null 2>&1; then
    uv venv "$VENV_DIR"
    if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
      uv pip install --python "$VENV_DIR/Scripts/python.exe" flask flask-cors markdown-it-py
    else
      uv pip install --python "$VENV_DIR/bin/python" flask flask-cors markdown-it-py
    fi
  else
    python -m venv "$VENV_DIR"
    if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
      "$VENV_DIR/Scripts/python.exe" -m pip install --quiet flask flask-cors markdown-it-py
    else
      "$VENV_DIR/bin/python" -m pip install --quiet flask flask-cors markdown-it-py
    fi
  fi
  if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
    PY="$VENV_DIR/Scripts/python.exe"
  else
    PY="$VENV_DIR/bin/python"
  fi
fi

echo "Using python: $PY"

# --- launch backend in background ---
nohup "$PY" app.py >> "$DIR/logs/rv.log" 2>&1 &
BACKEND_PID=$!
disown 2>/dev/null || true

# --- wait for health (first run compiles bytecode -> allow up to 15s) ---
UP=0
for i in $(seq 1 15); do
  if curl -s -m 2 http://localhost:8765/api/health 2>/dev/null | grep -q '"status":"ok"'; then
    UP=1
    break
  fi
  sleep 1
done

if [ "$UP" = "1" ]; then
  echo "Backend running (PID $BACKEND_PID)"
  echo ""
  echo "Open viewer:  http://localhost:8765"
  echo "List reports: http://localhost:8765/api/reports"
  echo "Health:       http://localhost:8765/api/health"
  echo ""
else
  echo "Backend failed to start - check $DIR/logs/rv.log"
  kill "$BACKEND_PID" 2>/dev/null || true
  exit 1
fi
