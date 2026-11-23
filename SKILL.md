---
name: report-viewer
description: Publish and iterate on browser-viewable reports (Markdown with Mermaid/KaTeX, HTML dashboards, Excalidraw boards) via the local report-viewer REST API. Use whenever a structured visual report, dashboard or diagram should be created or revised and a browser comment-loop is wanted. Not for plain chat answers, not for desktop-only features (Quarto/qmd, Reveal.js).
user-invocable: true
disable-model-invocation: false
version: 1.0.0
author: WickM
license: Apache-2.0
homepage: https://github.com/WickM/report-viewer
tags:
  - reporting
  - dashboard
  - excalidraw
  - markdown
  - mermaid
  - katex
  - charts
  - comment-loop
  - flask
  - openclaw-skill
---

# Report-Viewer (Skill)

> **Container-Variant**: Direct REST API calls, no MCP server required.
> The viewer runs at `http://localhost:8765` from the OpenClaw container.
> The skill checks the backend on every invocation and starts it automatically if needed.

## Prerequisites

- The skill checks the backend health on every invocation.
- If the backend is **not running**, the skill starts it automatically via `start.sh`.
- If the backend is running, it is reused as-is.
- No external URLs are ever invented — always use the link returned by `POST /api/publish`.

## 0. Pre-flight: ensure backend is up

```bash
# Check health
HEALTH=$(curl -s -m3 http://localhost:8765/api/health 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q '"status": "ok"'; then
  echo "Backend already running"
else
  echo "Backend not running — starting it..."
  cd "<skill dir>"   # das Verzeichnis, in dem dieses SKILL.md + app.py liegen
  nohup ./start.sh >/tmp/rv.log 2>&1 &
  sleep 2
  # Verify
  HEALTH=$(curl -s -m3 http://localhost:8765/api/health 2>/dev/null || echo "")
  if echo "$HEALTH" | grep -q '"status": "ok"'; then
    echo "Backend started successfully"
  else
    echo "ERROR: Backend failed to start. Check /tmp/rv.log"
    exit 1
  fi
fi
```

## 1. Format selection

| Format | Use for |
|---|---|
| `md` | Reports, analyses, architecture docs, tables, Mermaid blocks, KaTeX (`$...$` / `$$...$$`) |
| `html` | Interactive dashboards (Chart.js, Plotly, ECharts), complex web layouts |
| `html` (Quiz/Flashcard) | Interactive quizzes & flashcards — take `references/quiz-template.html`, replace placeholders, publish as `html` |
| `excalidraw` | A real `.excalidraw` board (JSON as `content` or `source_path`) |

**Not supported (container):** Quarto/`.qmd`, Reveal.js, `<stem>_files/`. Desktop-only.

## 2. Publish a report

**Inline content:**
```bash
curl -s -X POST http://localhost:8765/api/publish \
  -H "Content-Type: application/json" \
  -d '{"title":"<short title>","format":"md|html|excalidraw","content":"<raw content>"}'
```

**From a file on disk:**
```bash
curl -s -X POST http://localhost:8765/api/publish \
  -H "Content-Type: application/json" \
  -d '{"title":"<short title>","format":"md|html|excalidraw","source_path":"/path/to/file"}'
```

**Response** contains `filename`, `url`, `created` (true on first publish, false on overwrite).
Give the URL to the user exactly as returned. **Never** construct URLs yourself.

## 3. Feedback loop (browser comments → source)

1. **List comments for a report:**
   ```bash
   curl -s "http://localhost:8765/api/comments?filename=<filename>"
   ```
   Returns an array of comments: `id`, `author`, `text`, `quote`, `created`, optionally `resolved`.

2. **Update the source:**
   - With `source_path`: patch the original file (e.g. the brain vault `.md`) so the working copy stays in sync.
   - Without `source_path`: rewrite the `content` string.

3. **In-place overwrite** (same URL stays):
   ```bash
   curl -s -X POST http://localhost:8765/api/publish \
     -H "Content-Type: application/json" \
     -d '{"title":"<title>","format":"md|html|excalidraw","source_path":"<same path>","filename":"<existing filename>"}'
   ```
   or with `content` instead of `source_path`.

4. **Mark comments resolved** (only AFTER publish succeeded):
   ```bash
   curl -s -X POST http://localhost:8765/api/comments/<comment_id>/resolve
   ```

5. Tell the user: what was patched, that they should press F5.

## 4. Hard rules (never break)

- Iterations **always** overwrite the same `filename` — no new timestamped file (unless the user explicitly asks for a new version).
- Resolve comments **only after** `publish_report` succeeded.
- Never invent URLs — only the link returned by the publish call.
- When `source_path` was used, keep that file patched (working copy ↔ viewer sync).
- If the backend cannot be started → refuse to run, tell the user to check `/tmp/rv.log`.
- No Quarto, no `.qmd`, no Reveal.js — those are desktop-only.

### 4.5 Quiz and flashcards (interactive HTML, working)

Both formats are interactive HTML pages served by the viewer. Each one is a single self-contained file in `reports/`.

**Working examples (verified, HTTP 200):**
- Quiz, all four question types: `http://192.168.0.6:8765/view/quiz-beispiel-alle-formate-v1.html`
- Flashcards (flip card, right/wrong): `http://192.168.0.6:8765/view/flashcards-llm-governance-eu-ai-act.html`

**Quiz question types** (array `QUESTIONS` in `references/quiz-template.html`):

| `type` | Fields | Evaluation |
|---|---|---|
| `mc` | `q`, `options`, `correct` (index), `why` | click an option |
| `tf` | `q`, `correct` (true/false), `why` | click true or false |
| `cloze` | `q` (with `__` as gap), `answer`, `why` | typed input, compared case-insensitively |
| `text` | `q`, `answer` (alternatives separated by `;`), `why` | typed input, matches if any alternative fits |

**Flashcards** (array `CARDS` in the flashcard page): each card is `{ q, a }`. The card shows `q` on the front, the learner flips it, then rates `a` right or wrong.

**Creating a new page:** copy the working file as a base, replace the question or card array and the title, then publish it with `POST /api/publish`, `format: "html"`, `content` = full HTML.

**Comment widget caveat:** the comment engine treats elements with the class `.card` as commentable and intercepts their clicks. The flashcard uses `.fc-card` for this reason. Do not name interactive elements `.card`.

**Result storage:** the quiz posts its result to `/api/quiz/result` on completion, shown at `/quiz-results`. The flashcard page does not post results yet.


# 5. Deactivation / fallback

If the backend is unreachable and cannot be started:
- Do **not** execute the skill.
- Tell the user: "Report-Viewer backend not reachable at localhost:8765 — skill deactivation. Check `/tmp/rv.log` or run `./start.sh` manually from this skill's directory."
- Never produce fake URLs.

## 6. Smoke tests (definition of done)

- [ ] Pre-flight: backend already running → "already running" message.
- [ ] Pre-flight: backend not running → starts via `start.sh` → "started successfully".
- [ ] `curl -X POST .../api/publish` with a small `md` payload → response contains a `url` → paste in chat, confirm.
- [ ] Add a comment in the browser → `GET /api/comments?filename=...` shows it → patch source → `POST /api/publish` (same `filename`) → `POST /api/comments/<id>/resolve` → F5 → comment gone.
- [ ] Graceful degradation: `start.sh` fails → skill refuses and tells user.

## 7. References

- Viewer project (skill dir): das Verzeichnis dieses SKILL.md (deployed als `skills/report-viewer/`)
- Similar skill: `skills/session-closeout/SKILL.md`
- Quiz template: `references/quiz-template.html`
- Quiz results dashboard: `/quiz-results` (live, auto-aggregiert)