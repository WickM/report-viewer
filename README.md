# Report-Viewer

Browser-viewable reports (Markdown with Mermaid/KaTeX, HTML dashboards, Excalidraw boards) with a built-in comment loop. Served at `http://localhost:8765` from the OpenClaw container.

## Quick Start

```bash
python3 app.py
# → http://localhost:8765
```

The skill (`SKILL.md`) automatically starts the backend on every invocation if it is not already running.

## What the viewer can do

### 1. Publish reports
`POST /api/publish` publishes or overwrites a report as Markdown (`md`), HTML (`html`) or Excalidraw (`excalidraw`). Every published file is served under `/view/<filename>`.

### 2. Comment loop
Readers can mark text and add comments in the browser (`/view/<filename>`). The skill lists comments via `GET /api/comments?filename=...`, you patch the source, re-publish with the same `filename`, and resolve comments with `POST /api/comments/<id>/resolve`.

### 3. Interactive quizzes (working)
HTML quiz pages served under `/view/<filename>`. Supported question types:

| Type | Fields | Evaluation |
|------|--------|------------|
| `mc` | `q`, `options`, `correct` (index), `why` | click an option |
| `tf` | `q`, `correct` (true/false), `why` | click true or false |
| `cloze` | `q` (with `__` gap), `answer`, `why` | typed input |
| `text` | `q`, `answer` (`;` separated), `why` | typed input |

Quiz results post to `/api/quiz/result` on completion and appear on `/quiz-results`.

### 4. Flashcards (working)
Flashcard pages served under `/view/<filename>`. Each card shows a question on the front; the learner flips it, then rates it right or wrong. Card data is `{ q, a }`. Flashcards do **not** post results yet.

### 5. Templates in `references/`
- `quiz-template.html` — quiz page with placeholder `QUESTIONS` array
- `flashcard-template.html` — flashcard page with placeholder `CARDS` array
- `weekly-status.md`, `research-summary.md`, `architecture-decision.md` — Markdown report templates
- `CUSTOM.md` — how to add your own template

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/publish` | Publish or overwrite a report |
| GET | `/api/health` | Health check |
| GET | `/api/reports` | List all reports |
| DELETE | `/api/reports/<filename>` | Delete report + comments |
| GET | `/api/comments` | List comments (`?filename=` for one report) |
| POST | `/api/comments` | Add a comment |
| DELETE | `/api/comments/<id>` | Delete a comment |
| POST | `/api/comments/<id>/resolve` | Mark as resolved |
| POST | `/api/quiz/result` | Save a quiz attempt result |
| GET | `/api/quiz/results` | List all quiz results |
| DELETE | `/api/quiz/results` | Delete quiz results |
| GET | `/quiz-results` | Quiz results dashboard |
| GET | `/view/<filename>` | Serve a published report |
| GET | `/quiz/<filename>` | Serve quiz template (legacy query mode) |

## Working links (local network)

- Health: `http://192.168.0.6:8765/api/health`
- Quiz example (all types): `http://192.168.0.6:8765/view/quiz-beispiel-alle-formate-v1.html`
- Flashcards: `http://192.168.0.6:8765/view/flashcards-llm-governance-eu-ai-act.html`
- Quiz dashboard: `http://192.168.0.6:8765/quiz-results`

## OpenClaw Skill

`SKILL.md` in the repo root is the OpenClaw skill — auto-starts the backend, publishes, and handles the comment loop.

## License

Apache-2.0