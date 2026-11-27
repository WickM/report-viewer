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
# Data root: user-level, project-independent. Reports/comments live here, not
# inside the skill/code dir - portable across projects and agent copies.
DATA_DIR = Path.home() / ".report_viewer"
REPORTS_DIR = DATA_DIR / "reports"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("REPORT_VIEWER_HOST", "0.0.0.0")
PORT = int(os.environ.get("REPORT_VIEWER_PORT", "8765"))
BASE_URL = os.environ.get("REPORT_VIEWER_BASE_URL", f"http://localhost:{PORT}")

# ---------------------------------------------------------------------------
# Comment storage (JSON files — CIFS doesn't support SQLite locking)
# ---------------------------------------------------------------------------

COMMENTS_DIR = DATA_DIR / "comments"
COMMENTS_DIR.mkdir(parents=True, exist_ok=True)

# Quiz-Ergebnisse: persistent, außerhalb des Entwicklungsordners.
# Default ~/.local/share/report-viewer/results, überschreibbar via REPORT_VIEWER_RESULTS_DIR.
RESULTS_DIR = Path(os.environ.get(
    "REPORT_VIEWER_RESULTS_DIR",
    str(Path.home() / ".local" / "share" / "report-viewer" / "results"),
))
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Report-Metadaten (lesbarer Titel + Format) pro Filename — Sidecar, da der
# publizierte Report ein gefrorenes HTML ist und den Titel sonst nur im <title> trägt.
META_PATH = REPORTS_DIR / "_meta.json"

def _load_meta() -> dict:
    if not META_PATH.exists():
        return {}
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_meta(meta: dict) -> None:
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

def _detect_format(html: str) -> str:
    """Format aus dem gepublizierten HTML raten (nur für Backfill)."""
    if "excalidraw-app" in html:
        return "excalidraw"
    if "var QUESTIONS" in html or "quiz-card" in html:
        return "quiz"
    if 'class="fc-card"' in html or "fc-scene" in html:
        return "flashcard"
    # MD-Reports tragen die KaTeX/Mermaid-Libs + report-content-Wrapping.
    if "katex" in html.lower() and "report-content" in html:
        return "md"
    return "html"

def _backfill_meta() -> dict:
    """Meta für Reports ohne Eintrag nachtragen: Titel aus <title>, Format erkannt."""
    meta = _load_meta()
    changed = False
    for f in REPORTS_DIR.glob("*.html"):
        if f.name in meta:
            # Format neu bestimmen, falls sich die Erkennung geändert hat (Titel behalten)
            try:
                new_fmt = _detect_format(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta[f.name].get("format") != new_fmt:
                meta[f.name]["format"] = new_fmt
                changed = True
            continue
        try:
            html = f.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        title = m.group(1).strip() if m else f.stem
        meta[f.name] = {"title": title, "format": _detect_format(html),
                        "created": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime))}
        changed = True
    if changed:
        _save_meta(meta)
    return meta

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

def _add_comment(filename: str, author: str, text: str, quote: str = "", card_ref=None, excal_id=None) -> dict:
    comments = _load_comments(filename)
    entry = {
        "id": int(time.time() * 1000),
        "filename": filename,
        "author": author,
        "text": text,
        "quote": quote,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if card_ref is not None:
        entry["card_ref"] = card_ref
    if excal_id:
        entry["excal_id"] = excal_id
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
# Quiz results (persistent — stored outside the dev folder)
# ---------------------------------------------------------------------------

def _result_path(filename: str) -> Path:
    safe = re.sub(r'[^a-zA-Z0-9._-]+', '_', os.path.basename(filename))[:120] or "unknown"
    if not safe.endswith(".json"):
        safe = safe + ".json"
    return RESULTS_DIR / safe

def _load_results(filename: str) -> list:
    fp = _result_path(filename)
    if not fp.exists():
        return []
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return []

def _quiz_key(filename: str, quiz_id: str = "") -> str:
    """Speicher-Key: quiz_id (versioniert) oder fallback filename.
    WICHTIG: quiz_id wird NICHT nochmal mit 'quiz-' präfixiert — der Client
    übergibt die volle ID (z.B. 'quiz-llm-governance-eu-ai-act-v2')."""
    qid = (quiz_id or "").strip()
    if qid:
        safe = re.sub(r'[^a-zA-Z0-9._-]+', '_', qid)[:120] or "unknown"
        return f"{safe}.json"
    return os.path.basename(filename)

def _save_result(filename: str, entry: dict, quiz_id: str = "") -> dict:
    key = _quiz_key(filename, quiz_id)
    entries = _load_results(key)
    entry.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    entry.setdefault("id", uuid.uuid4().hex[:8])
    if quiz_id:
        entry.setdefault("quiz_id", quiz_id)
    entries.append(entry)
    _result_path(key).write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


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
    card_ref = data.get("card_ref")
    excal_id = (data.get("excal_id") or "").strip() or None
    entry = _add_comment(filename, author, text, quote, card_ref, excal_id)
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


@app.route("/quiz/<filename>")
def view_quiz(filename):
    """Serve quiz-template.html with injected quiz config (mode, quiz_id)."""
    safe = os.path.basename(filename)
    if not safe.endswith(".html"):
        safe += ".html"
    tmpl = BASE_DIR / "references" / safe
    if not tmpl.exists():
        abort(404)
    html = tmpl.read_text(encoding="utf-8")
    inject = (
        '<script>window.__REPORT_FILENAME__=' + json.dumps(safe) + ';</script>\n'
    )
    qmode = request.args.get("quiz_mode")
    qid = request.args.get("quiz_id")
    if qmode:
        inject += '<script>window.__QUIZ_MODE__=' + json.dumps(qmode) + ';</script>\n'
    if qid:
        inject += '<script>window.__QUIZ_ID__=' + json.dumps(qid) + ';</script>\n'
    if "</body>" in html:
        html = html.replace("</body>", inject + "</body>", 1)
    else:
        html += inject
    return Response(html, mimetype="text/html")


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
    excal_fp = REPORTS_DIR / (safe + ".excalidraw.json")
    if excal_fp.exists():
        excal_fp.unlink()
    meta = _load_meta()
    if safe in meta:
        del meta[safe]
        _save_meta(meta)
    log.info(f"Deleted report: {safe}")
    return jsonify({"deleted": safe})


def _excalidraw_save_path(filename: str) -> Path:
    """Sidecar for Excalidraw autosave, keyed by report filename."""
    safe = os.path.basename(filename)
    return REPORTS_DIR / (safe + ".excalidraw.json")


@app.route("/api/reports/<filename>/excalidraw", methods=["GET"])
def api_excalidraw_load(filename):
    """Load the autosaved Excalidraw scene for a report (if any)."""
    fp = _excalidraw_save_path(filename)
    if not fp.exists():
        return jsonify({"saved": False})
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        return jsonify({"saved": True, "data": data})
    except Exception:
        return jsonify({"saved": False})


@app.route("/api/reports/<filename>/excalidraw", methods=["POST"])
def api_excalidraw_save(filename):
    """Autosave the current Excalidraw scene (debounced from the client).
    Accepts whatever the bundle's onChange passes (object or array)."""
    data = request.get_json(force=True)
    if data is None:
        return jsonify({"error": "invalid payload"}), 400
    fp = _excalidraw_save_path(filename)
    fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return jsonify({"saved": True, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})


# ---------------------------------------------------------------------------
# Routes — HTML pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Dashboard — list all reports."""
    meta = _backfill_meta()
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = f.stat()
        m = meta.get(f.name, {})
        reports.append({
            "filename": f.name,
            "title": m.get("title", f.stem),
            "format": m.get("format", _detect_format(f.read_text(encoding="utf-8"))),
            "size": stat.st_size,
            "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        })
    return _render_index(reports)


def _fmt_badge(fmt: str) -> str:
    labels = {"md": "MD", "html": "HTML", "excalidraw": "EXCALIDRAW", "quiz": "QUIZ", "flashcard": "FLASHCARD"}
    label = labels.get(fmt, fmt.upper())
    return f'<span class="card-fmt-badge fmt-{fmt}">{label}</span>'

def _render_index(reports):
    """Render index page inline."""
    cards = "".join(
        f'<div class="card" data-filename="{r["filename"]}" data-format="{r["format"]}" data-mtime="{r["modified"]}" data-title="{r["title"]}" tabindex="0">'
        f'<button class="card-actions" data-filename="{r["filename"]}" aria-label="Aktionen">⋮</button>'
        f'<div class="card-head">{_fmt_badge(r["format"])}</div>'
        f'<span class="card-title-read" title="{r["filename"]}">{r["title"]}</span>'
        f'<span class="card-title-slug">{r["filename"]}</span>'
        f'<span class="card-meta"><span class="card-when" data-mtime="{r["modified"]}">{r["modified"][:16].replace("T", " ")}</span> · {r["size"] // 1024} KB</span>'
        f'<span class="card-hint">Langer Klick (500ms) oder Rechtsklick für Aktionen</span>'
        f'</div>'
        for r in reports
    ) or '<p class="empty">Noch keine Reports vorhanden.</p>'
    html = f"""<!DOCTYPE html>
<html lang="de" data-theme="light">
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
    <a href="/" class="active">Übersicht</a>
    <a href="/quiz-results">📊 Quiz-Ergebnisse</a>
  </nav>
</header>
<main>
  <section class="toolbar">
    <input id="tb-search" type="search" placeholder="Suche (Titel / Filename) …" aria-label="Suche">
    <select id="tb-filter" aria-label="Typ-Filter">
      <option value="alle">Alle</option>
      <option value="md">Report (MD)</option>
      <option value="html">HTML</option>
      <option value="excalidraw">Excalidraw</option>
      <option value="quiz">Quiz</option>
      <option value="flashcard">Flashcard</option>
    </select>
    <select id="tb-sort" aria-label="Sortierung">
      <option value="neueste">Neueste zuerst</option>
      <option value="name">Name (A–Z)</option>
    </select>
    <span class="toolbar-note">Tipps: ⋮-Button, Long-Press (500ms) oder Rechtsklick für Aktionen.</span>
  </section>
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
    qmode = request.args.get("quiz_mode")
    qid = request.args.get("quiz_id")
    if qmode:
        inject += '<script>window.__QUIZ_MODE__=' + json.dumps(qmode) + ';</script>\n'
    if qid:
        inject += '<script>window.__QUIZ_ID__=' + json.dumps(qid) + ';</script>\n'
    if "</body>" in html:
        html = html.replace("</body>", inject + "</body>", 1)
    else:
        html += inject
    return Response(html, mimetype="text/html")




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
<html lang="de" data-theme="light">
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
    elif fmt == "flashcard":
        # Flashcard-Deck als fertiges HTML (Template) — wie "html" durchreichen,
        # aber Format "flashcard" für das Badge speichern.
        html = raw
    elif fmt == "excalidraw":
        html = _wrap_excalidraw(title, raw)
    else:
        return jsonify({"error": f"Unknown format: {fmt}. Supported: md, html, excalidraw"}), 400

    filepath.write_text(html, encoding="utf-8")
    meta = _load_meta()
    meta[filename] = {"title": title, "format": fmt,
                      "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save_meta(meta)
    url = f"{BASE_URL}/view/{filename}"
    log.info(f"Published: {filename} ({len(html)} bytes, created={created})")
    return jsonify({"filename": filename, "url": url, "created": created})


@app.route("/api/reports", methods=["GET"])
def api_reports():
    """List all published reports."""
    meta = _load_meta()
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = f.stat()
        m = meta.get(f.name, {})
        reports.append({
            "filename": f.name,
            "title": m.get("title", f.stem),
            "format": m.get("format", "html"),
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
<html lang="de" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="/static/css/style.css">
<style>
  html, body {{ margin:0; padding:0; }}
  body.report-body {{ height:100vh; display:flex; flex-direction:column; background:var(--bg); color:var(--text); }}
  #excalidraw-app {{ flex:1; min-height:0; position:relative; }}
  body.report-body header {{ flex:0 0 auto; display:flex; align-items:center; gap:1.5rem; padding:1rem 2rem; background:var(--bg-card); border-bottom:1px solid var(--border); }}
  body.report-body header h1 {{ font-size:1.2rem; margin:0; }}
  body.report-body header a {{ color:var(--text-muted); text-decoration:none; }}
  body.report-body header a:hover {{ color:var(--accent-hover); }}
  #loading {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:1.1rem; color:var(--text-muted); }}
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
        loading.style.color = "#cc6666";
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

    var saveTimer = null;
    var saveStatus = null;
    var excalApi = null;

    var lastElements = null;

    /* Objekt-Liste für den Kommentar-Dropdown (id + lesbares Label).
       Nutzt das Element-Array aus onChange (zuverlässig in diesem Bundle). */
    function publishObjects(els) {{
      if (els) lastElements = els;
      var list = [];
      var arr = lastElements || [];
      if (arr && !Array.isArray(arr) && arr.elements) arr = arr.elements;
      arr.forEach(function (el, i) {{
        if (!el || el.isDeleted) return;
        var label;
        if (el.type === "text" && el.text) {{
          label = "Text: " + el.text.replace(/\\n/g, " ").slice(0, 40);
        }} else {{
          var t = el.type || "Objekt";
          label = t.charAt(0).toUpperCase() + t.slice(1) + " #" + (i + 1);
        }}
        list.push({{ id: el.id, label: label }});
      }});
      window.__EXCAL_OBJECTS__ = list;
      document.dispatchEvent(new CustomEvent("excal:objects", {{ detail: list }}));
    }}

    function showStatus(msg) {{
      if (!saveStatus) {{
        saveStatus = document.createElement("div");
        saveStatus.id = "excal-status";
        saveStatus.style.cssText = "position:fixed;top:8px;right:16px;z-index:10000;font-size:0.8rem;padding:4px 10px;border-radius:6px;background:rgba(40,40,50,0.9);color:#aaa;";
        document.body.appendChild(saveStatus);
      }}
      saveStatus.textContent = msg;
    }}

    function scheduleSave(state) {{
      if (saveTimer) clearTimeout(saveTimer);
      showStatus("…");
      saveTimer = setTimeout(function () {{
        fetch("/api/reports/" + encodeURIComponent(window.__REPORT_FILENAME__ || "") + "/excalidraw", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify(state)
        }}).then(function (r) {{
          showStatus(r.ok ? "✓" : "⚠");
          setTimeout(function () {{ if (saveStatus) saveStatus.textContent = ""; }}, 1200);
        }}).catch(function () {{ showStatus("⚠"); }});
      }}, 800);
    }}

    /* Lade gespeicherten Stand; sonst Original aus dem Report.
       setTimeout(0): __REPORT_FILENAME__ wird nach diesem Skript injiziert,
       daher erst in der nächsten Event-Loop-Runde holen. */
    setTimeout(function () {{
    fetch("/api/reports/" + encodeURIComponent(window.__REPORT_FILENAME__ || "") + "/excalidraw")
      .then(function (r) {{ return r.json(); }})
      .then(function (res) {{
        var orig = JSON.parse({json.dumps(raw_json)});
        var initialData = orig;
        if (res && res.saved && res.data) {{
          /* onChange liefert in diesem Bundle das Element-Array – zu initialData
             ({{elements, appState, files}}) normalisieren, sonst wie gespeichert. */
          if (Array.isArray(res.data)) {{
            initialData = {{ elements: res.data, appState: orig.appState || {{}} , files: orig.files || {{}} }};
          }} else {{
            initialData = res.data;
          }}
        }}
        var container = document.getElementById("excalidraw-app");
        container.innerHTML = "";
        createRoot(container).render(
          React.createElement(Excalidraw, {{
            initialData: initialData,
            viewModeEnabled: false,
            zenModeEnabled: true,
            gridModeEnabled: false,
            excalidrawAPI: function (api) {{ excalApi = api; }},
            onChange: function (state) {{ scheduleSave(state); publishObjects(state); }},
            UIOptions: {{ canvasActions: {{ export: {{ saveFileToDisk: true }} }} }}
          }})
        );
        publishObjects(initialData.elements || (Array.isArray(initialData) ? initialData : []));
        if (loading && loading.parentNode) {{
          loading.parentNode.removeChild(loading);
        }}
      }})
      .catch(function (err) {{ fail(String((err && err.message) || err)); }});
    }}, 0);
  }})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes — Quiz results
# ---------------------------------------------------------------------------

@app.route("/api/quiz/result", methods=["POST"])
def api_quiz_result():
    """Speichere ein Quiz-Ergebnis persistent (außerhalb des Entwicklungsordners)."""
    data = request.get_json(force=True) or {}
    filename = (data.get("filename") or "").strip()
    if not filename:
        return jsonify({"error": "filename required"}), 400
    quiz_id = (data.get("quiz_id") or "").strip()
    qtype = (data.get("type") or "quiz").strip()
    entry = {
        "type": qtype,
        "score": data.get("score"),
        "total": data.get("total"),
        "answers": data.get("answers") or [],
        "cards": data.get("cards") or [],
        "avg_rating": data.get("avg_rating"),
    }
    saved = _save_result(filename, entry, quiz_id)
    return jsonify(saved), 201


@app.route("/api/quiz/results", methods=["GET"])
def api_quiz_results():
    """Alle gespeicherten Quiz-Ergebnisse (optional nach filename filtern)."""
    filename = request.args.get("filename")
    if filename:
        return jsonify(_load_results(filename))
    out = []
    for fp in RESULTS_DIR.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            for e in data:
                e.setdefault("_file", fp.name)
                out.append(e)
        except Exception:
            pass
    out.sort(key=lambda c: c.get("ts", ""), reverse=True)
    return jsonify(out[:200])


@app.route("/api/quiz/results", methods=["DELETE"])
def api_quiz_results_delete():
    """Löscht alle gespeicherten Quiz-Ergebnisse (optional nach quiz_id/filename filtern)."""
    quiz_id = request.args.get("quiz_id")
    filename = request.args.get("filename")
    if quiz_id:
        fp = _result_path(f"{quiz_id}.json")
        if fp.exists():
            fp.unlink()
            return jsonify({"deleted": quiz_id})
        return jsonify({"error": "not found"}), 404
    if filename:
        fp = _result_path(os.path.basename(filename))
        if fp.exists():
            fp.unlink()
            return jsonify({"deleted": filename})
        return jsonify({"error": "not found"}), 404
    return jsonify({"error": "quiz_id or filename required"}), 400


# ---------------------------------------------------------------------------
# Routes — Quiz results dashboard (auto-aggregiert, keine separate Datei)
# ---------------------------------------------------------------------------

@app.route("/quiz-results")
def quiz_results_page():
    """Aggregiert alle Quiz-Ergebnisse live, gruppiert nach Quiz (Base) + Version (quiz_id).
    Jede Version hat ein Kontextmenü (Long-Press / Rechtsklick) mit Löschen-Funktion."""
    import html as html_mod

    # Gruppieren nach Typ und base (Quiz und Flashcard getrennt)
    groups = {}
    flash_groups = {}
    for fp in sorted(RESULTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in data:
            qtype = e.get("type") or "quiz"
            qid = (e.get("quiz_id") or "").strip() or fp.name[:-5]
            base = re.sub(r'-v\d+$', '', qid)
            score = e.get("score") or 0
            total = e.get("total") or 1
            pct = round(100 * score / total) if total else 0
            entry = {
                "version": qid,
                "type": qtype,
                "score": score,
                "total": total,
                "pct": pct,
                "ts": e.get("ts", ""),
                "id": e.get("id", ""),
                "answers": e.get("answers") or [],
                "cards": e.get("cards") or [],
                "avg_rating": e.get("avg_rating"),
            }
            if qtype == "flashcard":
                flash_groups.setdefault(base, []).append(entry)
            else:
                groups.setdefault(base, []).append(entry)

    for base in groups:
        groups[base].sort(key=lambda x: x["ts"], reverse=True)
    for base in flash_groups:
        flash_groups[base].sort(key=lambda x: x["ts"], reverse=True)

    # Build cards: Quiz zuerst
    cards = []
    for base, entries in sorted(groups.items(), key=lambda kv: kv[1][0]["ts"] if kv[1] else "", reverse=True):
        total_score = sum(e["score"] for e in entries)
        total_total = sum(e["total"] for e in entries)
        overall_pct = round(100 * total_score / total_total) if total_total else 0
        versions_html = "".join(
            f'<li class="quiz-version" data-quiz-id="{html_mod.escape(e["version"])}">'
            f'<span class="ver-label">{html_mod.escape(e["version"])}</span>'
            f'<span class="ver-score">{e["score"]}/{e["total"]} · {e["pct"]}%</span>'
            f'<span class="ver-ts">{html_mod.escape(e["ts"])}</span>'
            f'<span class="ver-hint">Rechtsklick / Long-Press für Löschen</span>'
            f'</li>'
            for e in entries
        )
        cards.append(
            f'<div class="card quiz-group">'
            f'<details>'
            f'<summary class="quiz-summary" data-quiz-base="{html_mod.escape(base)}">'
            f'<span class="card-title">📝 {html_mod.escape(base)}</span>'
            f'<span class="card-meta">{len(entries)} Version(en) · Gesamt {total_score}/{total_total} · {overall_pct}%</span>'
            f'<span class="quiz-score-bar"><span style="width:{overall_pct}%"></span></span>'
            f'</summary>'
            f'<ul class="quiz-versions">{versions_html}</ul>'
            f'</details>'
            f'</div>'
        )

    # Flashcard-Karten separat
    fc_cards = []
    for base, entries in sorted(flash_groups.items(), key=lambda kv: kv[1][0]["ts"] if kv[1] else "", reverse=True):
        latest = entries[0]
        avg = latest.get("avg_rating")
        avg_str = f" · Ø {avg}/5" if avg else ""
        versions_html = "".join(
            '<li class="quiz-version" data-quiz-id="%s">'
            '<span class="ver-label">%s</span>'
            '<span class="ver-score">%d Karten</span>'
            '<span class="ver-ts">%s</span>'
            '<span class="ver-hint">Rechtsklick / Long-Press für Löschen</span>'
            '</li>' % (
                html_mod.escape(e["version"]),
                html_mod.escape(e["version"]),
                len(e["cards"]),
                html_mod.escape(e["ts"]),
            )
            for e in entries
        )
        fc_cards.append(
            f'<div class="card quiz-group fc-group">'
            f'<details>'
            f'<summary class="quiz-summary" data-quiz-base="{html_mod.escape(base)}">'
            f'<span class="card-title">🃏 {html_mod.escape(base)}</span>'
            f'<span class="card-meta">{len(entries)} Karte(n){avg_str} · {html_mod.escape(entries[0]["ts"])}</span>'
            f'<span class="quiz-score-bar"><span style="width:100%"></span></span>'
            f'</summary>'
            f'<ul class="quiz-versions">{versions_html}</ul>'
            f'</details>'
            f'</div>'
        )

    quiz_part = "".join(cards) or '<p class="empty">Noch keine Quiz-Ergebnisse vorhanden.</p>'
    fc_part = "".join(fc_cards) or '<p class="empty">Noch keine Flashcard-Ergebnisse vorhanden.</p>'
    cards_html = f'<section id="quiz-section"><h2>📝 Quiz-Ergebnisse</h2>{quiz_part}</section><section id="flashcard-section"><h2>🃏 Flashcard-Ergebnisse</h2>{fc_part}</section>'

    detail = json.dumps(groups, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="de" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quiz-Ergebnisse</title>
<link rel="stylesheet" href="/static/css/style.css">
<style>
  /* ── Quiz-Ergebnisse — OpenClaw Design ─────────────────────────── */
  main {{ max-width: 960px; }}

  .quiz-progress {{
    color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1.5rem;
    padding: 0.75rem 1rem; background: var(--bg-card);
    border: 1px solid var(--border); border-radius: var(--radius);
  }}

  .quiz-group {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 1rem;
    overflow: hidden;
    transition: border-color 0.15s;
  }}
  .quiz-group:hover {{ border-color: var(--accent); }}

  .quiz-group details {{ width: 100%; }}

  .quiz-summary {{
    cursor: pointer; padding: 1rem 1.2rem; list-style: none;
    -webkit-user-select: none; user-select: none;
    -webkit-touch-callout: none; touch-action: manipulation;
    display: flex; flex-direction: column; gap: 0.4rem;
    transition: background 0.15s;
  }}
  .quiz-summary:hover {{ background: var(--bg-hover); }}
  .quiz-summary::-webkit-details-marker {{ display: none; }}

  .quiz-summary::before {{
    content: '▶'; font-size: 0.65rem; color: var(--text-muted);
    position: absolute; margin-top: 0.15rem;
    transition: transform 0.15s;
  }}
  .quiz-group details[open] .quiz-summary::before {{ content: '▼'; }}

  .card-title {{
    font-weight: 600; font-size: 1rem; color: var(--text);
    display: flex; align-items: center; gap: 0.5rem;
  }}
  .card-meta {{ color: var(--text-muted); font-size: 0.85rem; }}

  .quiz-score-bar {{
    display: block; height: 6px; background: var(--bg-hover);
    border-radius: 3px; overflow: hidden; margin-top: 0.3rem;
  }}
  .quiz-score-bar > span {{
    display: block; height: 100%; background: var(--accent);
    border-radius: 3px; transition: width 0.3s;
  }}

  .quiz-versions {{
    list-style: none; padding: 0; margin: 0;
    border-top: 1px solid var(--border);
    background: var(--bg);
  }}
  .quiz-versions li {{
    display: flex; gap: 0.8rem; padding: 0.6rem 1.2rem;
    border-bottom: 1px solid var(--border);
    cursor: pointer; align-items: center;
    transition: background 0.12s;
  }}
  .quiz-versions li:last-child {{ border-bottom: none; }}
  .quiz-versions li:hover {{ background: var(--bg-hover); }}

  .ver-label {{ font-weight: 500; color: var(--text); font-size: 0.85rem; min-width: 7rem; }}
  .ver-score {{ color: var(--accent); font-size: 0.85rem; min-width: 5.5rem; }}
  .ver-ts {{ flex: 1; color: var(--text-muted); font-size: 0.8rem; }}
  .ver-hint {{
    color: var(--text-muted); font-size: 0.72rem; opacity: 0;
    transition: opacity 0.15s;
  }}
  .quiz-versions li:hover .ver-hint {{ opacity: 0.7; }}

  .ctx-menu {{
    position: fixed; z-index: 9999; min-width: 180px;
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); box-shadow: 0 8px 32px rgba(0,0,0,0.55);
    padding: 5px; display: flex; flex-direction: column; gap: 1px;
  }}
  .ctx-menu[hidden] {{ display: none; }}
  .ctx-menu button {{
    background: none; border: none; color: var(--text);
    text-align: left; padding: 9px 14px; font-size: 0.9rem;
    border-radius: 6px; cursor: pointer; white-space: nowrap;
    display: flex; align-items: center; gap: 0.5rem;
    transition: background 0.12s;
  }}
  .ctx-menu button:hover {{ background: var(--bg-hover); }}
  .ctx-menu button.danger {{ color: var(--error); }}
  .ctx-menu button.danger:hover {{ background: rgba(204,102,102,0.15); }}

  .json-overlay {{
    position: fixed; inset: 0; background: rgba(0,0,0,0.55);
    display: flex; align-items: center; justify-content: center; z-index: 1000;
    padding: 2rem;
  }}
  .json-overlay[hidden] {{ display: none; }}
  .json-overlay-content {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1.5rem; width: 90%; max-width: 800px;
    max-height: 80vh; overflow: auto; font-family: var(--font-mono); font-size: 0.8rem;
    white-space: pre-wrap; line-height: 1.5; color: var(--text);
  }}
  .json-overlay-close {{
    margin-top: 1rem; padding: 0.5rem 1.2rem; background: var(--accent);
    color: #fff; border: none; border-radius: var(--radius);
    cursor: pointer; font-size: 0.9rem; font-family: var(--font-sans);
    transition: background 0.15s;
  }}
  .json-overlay-close:hover {{ background: var(--accent-hover); }}

  @media (max-width: 640px) {{
    .quiz-summary {{ padding: 0.9rem 1rem; }}
    .quiz-versions li {{ padding: 0.5rem 1rem; flex-wrap: wrap; }}
    .ver-hint {{ display: none; }}
    .json-overlay {{ padding: 1rem; }}
  }}
</style>
</head>
<body>
<header>
  <a href="/">← Übersicht</a>
  <h1>📊 Quiz-Ergebnisse</h1>
</header>
<main>
  <p class="quiz-progress">Alle gespeicherten Quiz-Versuche · gruppiert nach Quiz + Version · automatisch aktualisiert bei jedem Submit.</p>
  {cards_html}
</main>
<footer><small>Report-Viewer · Quiz-Results</small></footer>

<div class="json-overlay" id="json-overlay" hidden>
  <div class="json-overlay-content" id="json-overlay-content"></div>
  <button class="json-overlay-close" id="json-overlay-close">Schließen</button>
</div>

<script>
(function () {{
  "use strict";

  var ctx = null;
  var pressTimer = null;
  var longPressed = false;
  var startX = 0, startY = 0;

  /* Kontext-Menü aufbauen (identisch zum Dashboard) */
  function buildContext() {{
    var menu = document.createElement("div");
    menu.id = "ctx-menu";
    menu.className = "ctx-menu";
    menu.hidden = true;
    menu.innerHTML =
      '<button data-act="show-json">📋 JSON Details</button>' +
      '<button data-act="download-json">⬇️ JSON herunterladen</button>' +
      '<button data-act="delete-version" class="danger">🗑️ Löschen</button>';
    document.body.appendChild(menu);
    return menu;
  }}

  function showContext(x, y, base) {{
    if (!ctx) ctx = buildContext();
    ctx.dataset.quizBase = base;
    ctx.hidden = false;
    var w = ctx.offsetWidth, h = ctx.offsetHeight;
    ctx.style.left = Math.min(x, window.innerWidth - w - 8) + "px";
    ctx.style.top = Math.min(y, window.innerHeight - h - 8) + "px";
  }}

  function hideContext() {{ if (ctx) ctx.hidden = true; }}

  /* Karten-Kontext: Quiz-Base aus dem Menü-State */
  function currentBase() {{
    return (ctx && ctx.dataset.quizBase) ? ctx.dataset.quizBase : "";
  }}

  /* Versions-IDs der aktiven Kachel */
  function versionIds(base) {{
    var summary = document.querySelector('.quiz-summary[data-quiz-base="' + CSS.escape(base) + '"]');
    if (!summary) return [];
    var details = summary.closest("details") || summary.parentElement;
    return Array.prototype.map.call(
      details.querySelectorAll(".quiz-version"),
      function (li) {{ return li.dataset.quizId; }}
    );
  }}

  /* JSON für aktive Kachel laden (client-seitig gefiltert) */
  function fetchJson(base) {{
    return fetch("/api/quiz/results")
      .then(function (r) {{ return r.json(); }})
      .then(function (all) {{
        var vids = versionIds(base);
        return all.filter(function (r) {{
          var f = (r._file || "").replace(/\.json$/, "");
          return vids.some(function (v) {{ return f === v || f.indexOf(v) === 0; }});
        }});
      }});
  }}

  function onContextAction(act) {{
    var base = currentBase();
    hideContext();

    if (act === "delete-version") {{
      if (!confirm('Quiz "' + base + '" mit ALLEN Versionen löschen?')) return;
      Promise.all(versionIds(base).map(function (qid) {{
        return fetch("/api/quiz/results?quiz_id=" + encodeURIComponent(qid), {{ method: "DELETE" }});
      }})).then(function () {{ location.reload(); }});
      return;
    }}

    fetchJson(base).then(function (rows) {{
      var payload = rows.length === 1 ? rows[0] : {{ quizzes: rows }};
      var jsonStr = JSON.stringify(payload, null, 2);

      if (act === "show-json") {{
        var overlay = document.getElementById("json-overlay");
        var content = document.getElementById("json-overlay-content");
        if (!overlay || !content) return;
        content.textContent = jsonStr;
        overlay.hidden = false;
      }} else if (act === "download-json") {{
        var blob = new Blob([jsonStr], {{ type: "application/json" }});
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = base + "-results.json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }}
    }});
  }}

  document.addEventListener("DOMContentLoaded", function () {{
    /* Kontext-Menü aufbauen */
    ctx = buildContext();
    ctx.addEventListener("click", function (e) {{
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      onContextAction(btn.dataset.act);
    }});

    /* Hauptkacheln verdrahten (identisch zum Dashboard) */
    document.querySelectorAll(".quiz-summary").forEach(function (summary) {{
      var base = summary.dataset.quizBase;

      /* Klick: Long-Press unterdrücken */
      summary.addEventListener("click", function (e) {{
        if (e.target.closest("#ctx-menu")) return;
        if (longPressed) {{ longPressed = false; return; }}
      }});

      /* Rechtsklick → Kontextmenü */
      summary.addEventListener("contextmenu", function (e) {{
        e.preventDefault();
        showContext(e.clientX, e.clientY, base);
      }});

      /* Long-Press (Maus, 500ms) → Kontextmenü */
      summary.addEventListener("mousedown", function (e) {{
        if (e.button !== 0) return;
        if (e.target.closest("#ctx-menu")) return;
        longPressed = false;
        pressTimer = setTimeout(function () {{
          longPressed = true;
          showContext(e.clientX, e.clientY, base);
        }}, 500);
      }});
      summary.addEventListener("mouseup", function () {{ clearTimeout(pressTimer); }});
      summary.addEventListener("mouseleave", function () {{ clearTimeout(pressTimer); }});

      /* Long-Press (Touch, 500ms) → Kontextmenü */
      summary.addEventListener("touchstart", function (e) {{
        if (e.touches.length !== 1) return;
        var t = e.touches[0];
        startX = t.clientX; startY = t.clientY;
        longPressed = false;
        pressTimer = setTimeout(function () {{
          longPressed = true;
          showContext(startX, startY, base);
        }}, 500);
      }}, {{ passive: true }});

      summary.addEventListener("touchend", function () {{ clearTimeout(pressTimer); }});
      summary.addEventListener("touchmove", function (e) {{
        if (e.touches.length !== 1) return;
        var t = e.touches[0];
        if (Math.abs(t.clientX - startX) > 10 || Math.abs(t.clientY - startY) > 10) {{
          clearTimeout(pressTimer);
        }}
      }}, {{ passive: true }});
    }});

    /* Escape schließt Menü + Overlay */
    document.addEventListener("keydown", function (e) {{
      if (e.key !== "Escape") return;
      hideContext();
      var ov = document.getElementById("json-overlay");
      if (ov) ov.hidden = true;
    }});

    /* Overlay schließen */
    var overlay = document.getElementById("json-overlay");
    var closeBtn = document.getElementById("json-overlay-close");
    if (overlay && closeBtn) {{
      closeBtn.addEventListener("click", function () {{ overlay.hidden = true; }});
      overlay.addEventListener("click", function (e) {{
        if (e.target === overlay) overlay.hidden = true;
      }});
    }}
  }});
}})();
</script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(f"Report-Viewer MCP starting on {HOST}:{PORT}")
    log.info(f"Reports dir: {REPORTS_DIR}")
    log.info(f"Base URL: {BASE_URL}")
    app.run(host=HOST, port=PORT, debug=False)
