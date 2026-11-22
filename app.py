#!/usr/bin/env python3
"""Report-Viewer MCP — Web viewer + parser backend.
Flask app with REST API for OpenClaw MCP integration.
Runs on localhost:8765 by default.
"""

import os
import re
import json
import time
import uuid
import logging
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort, redirect, url_for, Response
from flask_cors import CORS
from markdown_it import MarkdownIt

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
UPLOADS_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

REPORTS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

HOST = os.environ.get("REPORT_VIEWER_HOST", "0.0.0.0")
PORT = int(os.environ.get("REPORT_VIEWER_PORT", "8765"))
BASE_URL = os.environ.get("REPORT_VIEWER_BASE_URL", f"http://localhost:{PORT}")

# ---------------------------------------------------------------------------
# Comment storage (JSON files — CIFS doesn't support SQLite locking)
# ---------------------------------------------------------------------------

COMMENTS_DIR = BASE_DIR / ".comments"
COMMENTS_DIR.mkdir(exist_ok=True)

def _safe_name(filename: str) -> str:
    """Map filename -> safe JSON path inside .comments/."""
    return filename.replace("/", "_").replace("..", "_") + ".json"

def _load_comments(filename: str) -> list:
    fp = COMMENTS_DIR / _safe_name(filename)
    if not fp.exists():
        return []
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_comments(filename: str, comments: list) -> None:
    fp = COMMENTS_DIR / _safe_name(filename)
    fp.write_text(json.dumps(comments, ensure_ascii=False), encoding="utf-8")

def _add_comment(filename: str, author: str, text: str, quote: str = "") -> dict:
    comments = _load_comments(filename)
    entry = {
        "id": int(time.time() * 1000),
        "filename": filename,
        "author": author,
        "text": text,
        "quote": quote,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    comments.append(entry)
    _save_comments(filename, comments)
    return entry

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("report-viewer")

# ---------------------------------------------------------------------------
# Markdown parser (markdown-it-py + Mermaid + KaTeX)
# ---------------------------------------------------------------------------

md = MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
md.enable("table")
md.enable("strikethrough")


def render_markdown(text: str) -> str:
    """Render markdown to HTML with Mermaid and KaTeX placeholders."""
    html = md.render(text)

    def mermaid_replace(match):
        code = match.group(1).strip()
        return f'<div class="mermaid">\n{code}\n</div>'

    html = re.sub(
        r'<pre><code class="language-mermaid">\s*(.*?)\s*</code></pre>',
        mermaid_replace,
        html,
        flags=re.DOTALL,
    )

    html = re.sub(
        r'\$\$(.*?)\$\$',
        lambda m: f'<span class="katex-block" data-tex="{m.group(1).strip()}">\\[{m.group(1).strip()}\\]</span>',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'(?<!\$)\$([^\$\n]+?)\$(?!\$)',
        lambda m: f'<span class="katex-inline" data-tex="{m.group(1).strip()}">\\({m.group(1).strip()}\\)</span>',
        html,
    )

    return html


app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATES_DIR))
CORS(app)

# ---------------------------------------------------------------------------
# Comment widget HTML (injected into /view/ pages)
# ---------------------------------------------------------------------------

COMMENT_WIDGET_HTML = '''
<link rel="stylesheet" href="/static/css/style.css">
<script src="/static/js/comments.js" defer></script>

<!-- Popover: erscheint beim Markieren von Text -->
<div id="comment-popover" class="comment-popover" hidden>
  <div class="popover-author-row">
    <input id="popover-author" type="text" placeholder="Name (optional)" maxlength="60">
  </div>
  <textarea id="popover-text" placeholder="Kommentar zum markierten Text …" rows="3"></textarea>
  <div class="popover-actions">
    <button id="popover-cancel" class="btn-cancel">Abbrechen</button>
    <button id="popover-save" class="btn-save" title="Strg+Enter">Speichern</button>
  </div>
</div>

<!-- Thread: schwebende Kommentare zu einem Zitat -->
<div id="comment-thread" class="comment-thread" hidden>
  <div class="thread-header">
    <span class="thread-label">Kommentare zu diesem Zitat</span>
    <button id="thread-close" class="thread-close" aria-label="Schließen">✕</button>
  </div>
  <blockquote id="thread-quote" class="thread-quote"></blockquote>
  <div id="thread-comments" class="thread-comments"></div>
</div>
'''

# ---------------------------------------------------------------------------
# Routes — Comments API
# ---------------------------------------------------------------------------

@app.route("/api/comments", methods=["GET"])
def api_comments_list():
    """List comments for a report (or all)."""
    filename = request.args.get("filename")
    if filename:
        return jsonify(_load_comments(filename))
    all_comments = []
    for fp in COMMENTS_DIR.glob("*.json"):
        try:
            all_comments.extend(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            pass
    all_comments.sort(key=lambda c: c.get("created", ""), reverse=True)
    return jsonify(all_comments[:200])


@app.route("/api/comments", methods=["POST"])
def api_comments_add():
    """Add a comment to a report."""
    data = request.get_json(force=True) or {}
    filename = (data.get("filename") or "").strip()
    text = (data.get("text") or "").strip()
    author = (data.get("author") or "Anonym").strip() or "Anonym"
    if not filename or not text:
        return jsonify({"error": "filename and text required"}), 400
    quote = (data.get("quote") or "").strip()
    entry = _add_comment(filename, author, text, quote)
    return jsonify(entry), 201


@app.route("/api/comments/<int:cid>", methods=["DELETE"])
def api_comments_delete(cid):
    """Delete a comment by id across all reports."""
    deleted = False
    for fp in COMMENTS_DIR.glob("*.json"):
        try:
            comments = json.loads(fp.read_text(encoding="utf-8"))
            orig = len(comments)
            comments = [c for c in comments if c.get("id") != cid]
            if len(comments) < orig:
                fp.write_text(json.dumps(comments, ensure_ascii=False), encoding="utf-8")
                deleted = True
        except Exception:
            pass
    return jsonify({"deleted": deleted})


@app.route("/api/comments/<int:cid>/resolve", methods=["POST"])
def api_comments_resolve(cid):
    """Mark a comment as resolved across all reports."""
    resolved = False
    for fp in COMMENTS_DIR.glob("*.json"):
        try:
            comments = json.loads(fp.read_text(encoding="utf-8"))
            changed = False
            for c in comments:
                if c.get("id") == cid and not c.get("resolved"):
                    c["resolved"] = True
                    c["resolvedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    changed = True
            if changed:
                fp.write_text(json.dumps(comments, ensure_ascii=False), encoding="utf-8")
                resolved = True
        except Exception:
            pass
    return jsonify({"resolved": resolved})


@app.route("/api/reports/<filename>", methods=["GET"])
def api_report_meta(filename):
    """Return report metadata + comment count."""
    safe = os.path.basename(filename)
    fp = REPORTS_DIR / safe
    if not fp.exists():
        return jsonify({"error": "not found"}), 404
    st = fp.stat()
    comments = _load_comments(safe)
    return jsonify({
        "filename": safe,
        "size": st.st_size,
        "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
        "comments": len(comments),
    })


@app.route("/api/reports/<filename>", methods=["DELETE"])
def api_report_delete(filename):
    """Delete a report (html file + its comments)."""
    safe = os.path.basename(filename)
    fp = REPORTS_DIR / safe
    if not fp.exists():
        return jsonify({"error": "not found"}), 404
    fp.unlink()
    comment_fp = COMMENTS_DIR / _safe_name(safe)
    if comment_fp.exists():
        comment_fp.unlink()
    log.info(f"Deleted report: {safe}")
    return jsonify({"deleted": safe})


# ---------------------------------------------------------------------------
# Routes — HTML pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Dashboard — list all reports."""
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = f.stat()
        reports.append({
            "filename": f.name,
            "title": f.stem,
            "size": stat.st_size,
            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
        })
    return _render_index(reports)


def _render_index(reports):
    """Render index page inline."""
    cards = "".join(
        f'<div class="card" data-filename="{r["filename"]}" tabindex="0">'
        f'<span class="card-title">{r["title"]}</span>'
        f'<span class="card-meta">{r["modified"]} · {r["size"] // 1024} KB</span>'
        f'<span class="card-hint">Rechtsklick / Long-Press für Aktionen</span>'
        f'</div>'
        for r in reports
    ) or '<p class="empty">Noch keine Reports vorhanden.</p>'
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Report-Viewer</title>
<link rel="stylesheet" href="/static/css/style.css">
<script src="/static/js/dashboard.js" defer></script>
</head>
<body>
<header>
  <h1>📄 Report-Viewer</h1>
  <nav>
    <a href="/">Übersicht</a>
    <a href="/upload">Upload</a>
  </nav>
</header>
<main>
  <section id="comments-panel" class="comments-panel" hidden>
    <div class="comments-header">
      <h2 id="comments-title">Kommentare</h2>
      <button id="comments-close" class="comments-close" aria-label="Schließen">✕</button>
    </div>
    <div id="comments-list" class="comments-list"></div>
    <div class="comments-form">
      <input id="comments-author" type="text" placeholder="Dein Name (optional)" maxlength="60">
      <textarea id="comments-text" placeholder="Kommentar schreiben …" rows="2" required></textarea>
      <button id="comments-send">Senden</button>
    </div>
  </section>
  <section class="reports-grid">
    {cards}
  </section>
</main>
<footer>
  <small>Report-Viewer MCP · localhost:{PORT}</small>
</footer>
</body>
</html>"""
    return html


@app.route("/view/<filename>")
def view_report(filename):
    """Serve a rendered report HTML file with comment widget injected."""
    safe_name = os.path.basename(filename)
    filepath = REPORTS_DIR / safe_name
    if not filepath.exists():
        abort(404)
    html = filepath.read_text(encoding="utf-8")
    # Inject comment widget + filename JS before </body>
    inject = (
        COMMENT_WIDGET_HTML
        + '<script>window.__REPORT_FILENAME__=' + json.dumps(safe_name) + ';</script>\n'
    )
    if "</body>" in html:
        html = html.replace("</body>", inject + "</body>", 1)
    else:
        html += inject
    return Response(html, mimetype="text/html")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    """Upload page — POST markdown or HTML."""
    if request.method == "GET":
        html = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Upload — Report-Viewer</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
<header><h1>📤 Upload</h1><a href="/">← Zurück</a></header>
<main>
<form method="POST" action="/api/publish">
  <label>Titel:<br><input type="text" name="title" placeholder="Mein Bericht" required></label><br><br>
  <label>Format:<br>
    <select name="format">
      <option value="md">Markdown (md)</option>
      <option value="html">HTML (html)</option>
    </select>
  </label><br><br>
  <label>Inhalt:<br><textarea name="content" rows="15" style="width:100%" placeholder="# Überschrift&#10;&#10;Text mit **Markdown** ..."></textarea></label><br><br>
  <button type="submit">Veröffentlichen</button>
</form>
</main>
</body>
</html>"""
        return html
    return redirect(url_for("upload"))


# ---------------------------------------------------------------------------
# Routes — REST API (for MCP server)
# ---------------------------------------------------------------------------

@app.route("/api/publish", methods=["POST"])
def api_publish():
    """Publish a report."""
    data = request.get_json(force=True)
    title = data.get("title", "Unbenannt")
    fmt = data.get("format", "md")
    content = data.get("content")
    source_path = data.get("source_path")
    existing_filename = data.get("filename")

    if existing_filename:
        filename = os.path.basename(existing_filename)
        created = False
    else:
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40] or "report"
        filename = f"{slug}-{uuid.uuid4().hex[:8]}.html"
        created = True

    filepath = REPORTS_DIR / filename

    if source_path:
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            return jsonify({"error": f"Cannot read source_path: {e}"}), 400
    elif content is not None:
        raw = content
    else:
        return jsonify({"error": "Either 'content' or 'source_path' required"}), 400

    if fmt == "md":
        body_html = render_markdown(raw)
        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="/static/css/style.css">
<link rel="stylesheet" href="/static/lib/katex/katex.min.css">
<script src="/static/lib/katex/katex.min.js"></script>
<script src="/static/lib/mermaid/mermaid.min.js"></script>
</head>
<body class="report-body">
<header>
  <a href="/">← Übersicht</a>
  <h1>{title}</h1>
</header>
<main class="report-content">
{body_html}
</main>
<footer>
  <small>Report-Viewer MCP · {time.strftime("%Y-%m-%d %H:%M")}</small>
</footer>
<script>
  if (typeof renderMathInElement === 'function') {{
    renderMathInElement(document.body, {{
      delimiters: [
        {{left: '$$', right: '$$', display: true}},
        {{left: '\\(', right: '\\)', display: false}}
      ]
    }});
  }}
  if (typeof mermaid !== 'undefined') {{
    mermaid.initialize({{ startOnLoad: true, theme: 'neutral', securityLevel: 'loose' }});
  }}
</script>
</body>
</html>"""
    elif fmt == "html":
        html = raw
    elif fmt == "excalidraw":
        html = _wrap_excalidraw(title, raw)
    else:
        return jsonify({"error": f"Unknown format: {fmt}. Supported: md, html, excalidraw"}), 400

    filepath.write_text(html, encoding="utf-8")
    url = f"{BASE_URL}/view/{filename}"
    log.info(f"Published: {filename} ({len(html)} bytes, created={created})")
    return jsonify({"filename": filename, "url": url, "created": created})


@app.route("/api/reports", methods=["GET"])
def api_reports():
    """List all published reports."""
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = f.stat()
        reports.append({
            "filename": f.name,
            "size": stat.st_size,
            "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        })
    return jsonify(reports)


@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "reports": len(list(REPORTS_DIR.glob("*.html"))),
        "version": "0.1.0",
    })


# ---------------------------------------------------------------------------
# Static files — serve JS libs locally
# ---------------------------------------------------------------------------

@app.route("/static/lib/<path:filename>")
def serve_lib(filename):
    """Serve static library files (katex, mermaid)."""
    return send_file(STATIC_DIR / "lib" / filename)


# ---------------------------------------------------------------------------
# Excalidraw wrapper
# ---------------------------------------------------------------------------

def _wrap_excalidraw(title: str, raw_json: str) -> str:
    """Wrap raw Excalidraw JSON into a full HTML page."""
    import json as _json
    try:
        _json.loads(raw_json)
    except Exception as e:
        raise ValueError(f"Invalid Excalidraw JSON: {e}")

    bundle_ok = (STATIC_DIR / "lib" / "excalidraw-viewer.js").is_file()
    bundle_tag = (
        '<script src="/static/lib/excalidraw-viewer.js"></script>'
        if bundle_ok else ""
    )
    if not bundle_ok:
        log.error(
            "excalidraw-viewer.js missing from static/lib — run: "
            "cd /config/clawd/build/excalidraw && npm run build"
        )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="/static/css/style.css">
<style>
  html, body {{ margin:0; padding:0; }}
  body.report-body {{ height:100vh; display:flex; flex-direction:column; background:#0d1117; color:#e6edf3; }}
  #excalidraw-app {{ flex:1; min-height:0; position:relative; }}
  body.report-body header {{ flex:0 0 auto; display:flex; align-items:center; gap:1.5rem; padding:1rem 2rem; background:#161b22; border-bottom:1px solid #30363d; }}
  body.report-body header h1 {{ font-size:1.2rem; margin:0; }}
  body.report-body header a {{ color:#8b949e; text-decoration:none; }}
  body.report-body header a:hover {{ color:#58a6ff; }}
  #loading {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:1.1rem; color:#8b949e; }}
</style>
{bundle_tag}
</head>
<body class="report-body">
<header>
  <a href="/">← Übersicht</a>
  <h1>{title}</h1>
</header>
<div id="excalidraw-app">
  <div id="loading">⏳ Lade Excalidraw ...</div>
</div>
<script>
  (function () {{
    var loading = document.getElementById("loading");
    function fail(msg) {{
      console.error("Excalidraw init failed:", msg);
      if (loading) {{
        loading.textContent = "❌ Excalidraw konnte nicht geladen werden: " + msg;
        loading.style.color = "#f85149";
      }}
    }}

    if (!window.ExcalidrawViewer) {{
      fail("Bundle excalidraw-viewer.js nicht geladen (siehe static/lib/).");
      return;
    }}

    var Excalidraw = window.ExcalidrawViewer.Excalidraw;
    var React = window.ExcalidrawViewer.React;
    var createRoot = window.ExcalidrawViewer.createRoot;

    if (!Excalidraw || !React || typeof createRoot !== "function") {{
      fail("Bundle unvollständig (Excalidraw/React/createRoot fehlen).");
      return;
    }}

    try {{
      var initialData = JSON.parse({json.dumps(raw_json)});
      var container = document.getElementById("excalidraw-app");
      container.innerHTML = "";
      createRoot(container).render(
        React.createElement(Excalidraw, {{
          initialData: initialData,
          viewModeEnabled: false,
          zenModeEnabled: true,
          gridModeEnabled: false,
          UIOptions: {{ canvasActions: {{ export: {{ saveFileToDisk: true }} }} }}
        }})
      );
      if (loading && loading.parentNode) {{
        loading.parentNode.removeChild(loading);
      }}
    }} catch (err) {{
      fail(String((err && err.message) || err));
    }}
  }})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(f"Report-Viewer MCP starting on {HOST}:{PORT}")
    log.info(f"Reports dir: {REPORTS_DIR}")
    log.info(f"Base URL: {BASE_URL}")
    app.run(host=HOST, port=PORT, debug=False)
