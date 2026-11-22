#!/bin/bash
# Report-Viewer MCP — Start script
# Usage: ./start.sh [--with-mcp]

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Create logs dir if missing
mkdir -p logs

# Start backend
echo "🚀 Starting Report-Viewer backend on http://localhost:8765 ..."
python3 app.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 1.5

# Check health
if curl -s http://localhost:8765/api/health | grep -q '"status": "ok"'; then
    echo "✅ Backend running (PID $BACKEND_PID)"
    echo ""
    echo "📄 Open viewer:  http://localhost:8765"
    echo "📋 List reports: http://localhost:8765/api/reports"
    echo "❤️  Health:       http://localhost:8765/api/health"
    echo ""

    if [ "$1" = "--with-mcp" ]; then
        echo "🔌 Starting MCP server (stdio) ..."
        python3 mcp_server.py
    fi
else
    echo "❌ Backend failed to start"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi