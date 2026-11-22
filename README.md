# Report-Viewer

Browser-viewable reports (Markdown with Mermaid/KaTeX, HTML dashboards, Excalidraw boards) with a built-in comment loop.

## Quick Start

```bash
python3 app.py
# → http://localhost:8765
```

## Features

- **Publish**: `POST /api/publish` — `md`, `html` or `excalidraw`
- **Comment loop**: `GET /api/comments?filename=...` → patch source → re-publish → `POST /api/comments/<id>/resolve`
- **Auto-start**: the skill (`SKILL.md`) checks health and starts the backend if needed
- **Dark theme UI** with Mermaid, KaTeX, Chart.js support

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/publish` | Publish or overwrite a report |
| GET  | `/api/comments` | List comments (`?filename=` for one report) |
| POST | `/api/comments` | Add a comment |
| DELETE | `/api/comments/<id>` | Delete a comment |
| POST | `/api/comments/<id>/resolve` | Mark as resolved |
| GET  | `/api/reports` | List all reports |
| DELETE | `/api/reports/<filename>` | Delete report + its comments |
| GET  | `/api/health` | Health check |

## OpenClaw Skill

`SKILL.md` in the repo root is the OpenClaw skill — auto-starts the backend, publishes, and handles the comment loop.

## License

Apache-2.0
