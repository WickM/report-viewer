# Report-Viewer MCP

Web-Viewer für Markdown-Berichte (Mermaid + KaTeX), HTML-Dashboards und Excalidraw-Boards.
Läuft auf `localhost:8765`, integriert via MCP-Server in OpenClaw.

## Quick Start

```bash
cd /media/HA_EXTERN/freigabe/projekte/report-viewer
python3 app.py
```

→ öffne `http://localhost:8765`

## Struktur

```
report-viewer/
├── app.py                 # Flask-Backend (Web-Viewer + REST API)
├── mcp_server.py          # MCP-Server (JSON-RPC over stdio für OpenClaw)
├── parser/
│   └── (Platzhalter für zukünftige Parser-Erweiterungen)
├── static/
│   ├── css/style.css      # Dark-Theme Stylesheet
│   ├── js/report.js       # Mermaid + KaTeX Auto-Render
│   └── lib/
│       ├── mermaid/mermaid.min.js
│       └── katex/ (katex.min.js, katex.min.css, auto-render.min.js)
├── templates/             # (Platzhalter für Jinja-Templates)
├── uploads/               # Upload-Storage
├── reports/               # Generierte HTML-Reports
└── logs/                  # MCP-Server-Logs
```

## API

### `POST /api/publish`

Report veröffentlichen oder aktualisieren.

```json
{
  "title": "Mein Bericht",
  "format": "md",
  "content": "# Hello\n\nMarkdown content...",
  "source_path": "/path/to/file.md",
  "filename": "existing.html"
}
```

**Response:**
```json
{
  "filename": "mein-bericht-abc123.html",
  "url": "http://localhost:8765/view/mein-bericht-abc123.html",
  "created": true
}
```

### `GET /api/reports`

Alle Reports auflisten.

### `GET /api/health`

Health-Check.

## MCP-Integration (OpenClaw)

Der MCP-Server läuft als separater Prozess und kommuniziert mit dem Flask-Backend via REST.

### In OpenClaw registrieren

```json
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
```

### Verfügbare Tools

| Tool | Beschreibung |
|------|-------------|
| `publish_report` | Report veröffentlichen (Markdown/HTML), gibt Browser-URL zurück |
| `list_reports` | Alle Reports auflisten |
| `health_check` | Backend-Status prüfen |

##异地 Deployment

- `REPORT_VIEWER_HOST` — Bind-Adresse (default `0.0.0.0`)
- `REPORT_VIEWER_PORT` — Port (default `8765`)
- `REPORT_VIEWER_BASE_URL` — Öffentliche URL (default `http://localhost:<port>`)
- `REPORT_VIEWER_URL` — Backend-URL für MCP-Server (default `http://localhost:8765`)

## Bekannte Limitierungen

- Keine Kommentare im Browser (nur Anzeige) — `get_report_comments` / `resolve_report_comments` sind noch nicht implementiert
- Kein Datei-Upload (nur API-basierter Publish)
- Keine User-Authentifizierung
- Flask-Development-Server (nicht für Produktion)

## Lizenz

Apache-2.0 (wie alle Alfred-Projekte)