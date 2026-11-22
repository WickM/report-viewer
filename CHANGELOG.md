# Changelog

## [1.0.0] — 2026-11-22

### Added
- Flask backend with REST API (`POST /api/publish`, `GET /api/comments`, `POST /api/comments/<id>/resolve`, `DELETE /api/reports/<filename>`)
- OpenClaw skill (`skill/SKILL.md`) with auto-start, pre-flight check, and REST workflow
- Mermaid, KaTeX, Excalidraw, and Chart.js support
- Comment loop: inline text marking + element selection (charts, images, KPI cards) on HTML dashboards
- Thread popover positioning near clicked element
- Report deletion with cascade comment cleanup
- `.gitignore` excludes runtime data (`reports/`, `.comments/`, `logs/`, `backups/`, `__pycache__/`)
- Apache-2.0 license

### Smoke Tests (all green)
- ✅ Pre-flight: backend already running → "already running"
- ✅ Publish md with Mermaid + KaTeX → URL returned
- ✅ Comment created → listed via API → overwrite in-place (same URL) → resolved
- ✅ Delete report → comments cascade-deleted