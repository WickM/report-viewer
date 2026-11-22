#!/usr/bin/env python3
"""
Report-Viewer MCP Server
========================
Standalone MCP server that exposes the report-viewer as OpenClaw tools.
Communicates with the Flask backend via REST API.

Usage:
    python3 mcp_server.py

Or integrate into OpenClaw MCP config:
    {
      "mcp": {
        "servers": {
          "report-viewer": {
            "command": "python3",
            "args": ["/media/HA_EXTERN/freigabe/projekte/report-viewer/mcp_server.py"]
          }
        }
      }
    }
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VIEWER_URL = os.environ.get("REPORT_VIEWER_URL", "http://localhost:8765")
LOG_FILE = Path(__file__).parent / "logs" / "mcp_server.log"
LOG_FILE.parent.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("mcp-server")

# ---------------------------------------------------------------------------
# REST helpers
# ---------------------------------------------------------------------------

def api_call(method: str, path: str, data: dict = None) -> dict:
    """Make a REST call to the report-viewer backend."""
    url = f"{VIEWER_URL}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        log.error(f"HTTP {e.code} from {url}: {body}")
        return {"error": f"HTTP {e.code}", "detail": body}
    except urllib.error.URLError as e:
        log.error(f"Cannot reach viewer at {url}: {e}")
        return {"error": "viewer_unreachable", "detail": str(e)}
    except Exception as e:
        log.error(f"API call failed: {e}")
        return {"error": str(e)}

# ---------------------------------------------------------------------------
# MCP Tool definitions (JSON-RPC style, compatible with OpenClaw MCP)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "publish_report",
        "description": (
            "Publish a report (Markdown or HTML) to the report-viewer. "
            "Returns a URL the user can open in the browser. "
            "Use 'filename' to overwrite an existing report in-place (same URL). "
            "Formats: 'md' (Markdown with Mermaid + KaTeX support), 'html' (raw HTML)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Report title (shown in browser tab and header).",
                },
                "format": {
                    "type": "string",
                    "enum": ["md", "html"],
                    "description": "Content format: 'md' for Markdown, 'html' for raw HTML.",
                },
                "content": {
                    "type": "string",
                    "description": "Inline content (Markdown or HTML). Use this OR source_path.",
                },
                "source_path": {
                    "type": "string",
                    "description": "Path to a file on disk (e.g. brain vault .md file). Use this OR content.",
                },
                "filename": {
                    "type": "string",
                    "description": "Optional. Existing filename to overwrite in-place (keeps same URL).",
                },
            },
            "required": ["title", "format"],
        },
    },
    {
        "name": "list_reports",
        "description": "List all published reports with filename, size, and modification time.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "health_check",
        "description": "Check if the report-viewer backend is running.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def handle_publish_report(args: dict) -> dict:
    """Handle publish_report tool call."""
    title = args.get("title", "Unbenannt")
    fmt = args.get("format", "md")
    content = args.get("content")
    source_path = args.get("source_path")
    filename = args.get("filename")

    if not content and not source_path:
        return {"error": "Either 'content' or 'source_path' is required."}

    data = {"title": title, "format": fmt}
    if content:
        data["content"] = content
    if source_path:
        data["source_path"] = source_path
    if filename:
        data["filename"] = filename

    result = api_call("POST", "/api/publish", data)

    if "error" in result:
        return result

    url = result.get("url", "")
    filename_out = result.get("filename", "")
    created = result.get("created", False)

    # Build user-friendly response
    lines = []
    if created:
        lines.append(f"📄 **Report veröffentlicht:** {title}")
    else:
        lines.append(f"📄 **Report aktualisiert:** {title}")
    lines.append(f"🔗 **Link:** {url}")
    if filename_out:
        lines.append(f"📁 **Datei:** `{filename_out}`")
    lines.append("")
    lines.append("Im Browser öffnen und Kommentare setzen. "
                 "Zum Einarbeiten der Kommentare: `get_report_comments` + `resolve_report_comments`.")

    return {"result": "\n".join(lines), "url": url, "filename": filename_out}


def handle_list_reports(args: dict) -> dict:
    """Handle list_reports tool call."""
    result = api_call("GET", "/api/reports")
    if "error" in result:
        return result

    if not result:
        return {"result": "Noch keine Reports vorhanden."}

    lines = ["📋 **Vorhandene Reports:**\n"]
    for r in result:
        lines.append(f"- `{r['filename']}` — {r['modified']} ({r['size'] // 1024} KB)")
    lines.append(f"\n**Total:** {len(result)} Reports")
    return {"result": "\n".join(lines)}


def handle_health_check(args: dict) -> dict:
    """Handle health_check tool call."""
    result = api_call("GET", "/api/health")
    if "error" in result:
        return {"status": "down", "error": result.get("detail", str(result))}
    return {"status": "up", "reports": result.get("reports", 0), "version": result.get("version", "?")}


# ---------------------------------------------------------------------------
# MCP protocol handler (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

TOOL_HANDLERS = {
    "publish_report": handle_publish_report,
    "list_reports": handle_list_reports,
    "health_check": handle_health_check,
}

def handle_mcp_request(msg: dict) -> dict:
    """Handle a single MCP JSON-RPC request."""
    method = msg.get("method")
    params = msg.get("params", {})
    req_id = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "report-viewer", "version": "0.1.0"},
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        try:
            result = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": result.get("result", json.dumps(result))}]},
            }
        except Exception as e:
            log.error(f"Tool {tool_name} failed: {e}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }


def main():
    """Run MCP server over stdio."""
    log.info("Report-Viewer MCP Server starting...")
    log.info(f"Backend URL: {VIEWER_URL}")

    # Check backend on startup
    health = api_call("GET", "/api/health")
    if "error" in health:
        log.warning(f"Backend not reachable at {VIEWER_URL}: {health}")
        log.warning("Start the backend first: python3 app.py")
    else:
        log.info(f"Backend OK: {health}")

    # JSON-RPC over stdio (line-delimited)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            log.error(f"Invalid JSON: {line[:100]}")
            continue

        response = handle_mcp_request(msg)
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()