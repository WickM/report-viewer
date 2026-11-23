#!/bin/bash
# Report-Viewer — Start script
# Usage: ./start.sh

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

mkdir -p logs

echo "🚀 Starting Report-Viewer backend on http://localhost:8765 ..."
PY="$(command -v python3 || command -v python)"
"$PY" app.py &
BACKEND_PID=$!

sleep 1.5

if curl -s http://localhost:8765/api/health | grep -q '"status": "ok"'; then
    echo "✅ Backend running (PID $BACKEND_PID)"
    echo ""
    echo "📄 Open viewer:  http://localhost:8765"
    echo "📋 List reports: http://localhost:8765/api/reports"
    echo "❤️  Health:       http://localhost:8765/api/health"
    echo ""
else
    echo "❌ Backend failed to start"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi
