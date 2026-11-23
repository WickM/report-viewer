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
  cd /config/clawd/skills/report-viewer
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

### 4.5 Quiz / Flashcard (interactive HTML)

Interactive quizzes are plain `html` reports — no extra server format needed.

1. **Template:** `references/quiz-template.html` (in this skill's `references/`).
2. **Fill placeholders:** `[TITEL]`, `[FRAGE]`, `[A]`–`[D]`, `[ERKLÄRUNG]`, `correct: <index>`, `why`.
3. **Versionierung (wichtig):** Quiz-Updates bekommen eine neue `quiz_id` mit Suffix `-v1`, `-v2`, `-v3`...
   - Erstes Quiz: `quiz_id = "quiz-<slug>-v1"` (z.B. `quiz-llm-governance-eu-ai-act-v1`)
   - Update mit neuen Fragen: `quiz_id = "quiz-<slug>-v2"` (neue HTML-Datei, alte Ergebnisse bleiben erhalten)
   - So bleiben alte und neue Quiz-Versuche **sauber getrennt auswertbar** (`/quiz-results` gruppiert nach Quiz + Version).
4. **Publish:**
   ```bash
   curl -s -X POST http://localhost:8765/api/publish \
     -H "Content-Type: application/json" \
     -d '{"title":"<Titel>","format":"html","content":"<fully rendered HTML>"}'
   ```
5. **Ergebnisse speichern:** Die Quiz-Engine im Template postet automatisch beim Abschluss an `/api/quiz/result` mit `quiz_id`. Gespeichert in `RESULTS_DIR` (CIFS, persistent).
6. **Ergebnisse anzeigen:** `/quiz-results` (Dashboard) zeigt alle Quiz-Versuche, gruppiert nach Quiz + Version.
7. **Vor dem Publizieren:** `node --check` auf das extrahierte `<script>`-JS machen (Syntaxfehler → Quiz zeigt nichts).

**Flashcards** = vereinfachte Quiz-Variante (Frage → Klick → Antwort), gleiche `quiz_id`-Versionierung.

#### 4.6 Unterstützte Formate (Quiz + Flashcard)

Die Vorlage `references/quiz-template.html` kennt vier Quiz-Fragetypen plus den Flashcard-Modus. Jeder Eintrag im Array `QUESTIONS` hat einen Typ `type`:

| `type` | Bedeutung | Pflichtfelder | Auswertung |
|---|---|---|---|
| `mc` | Multiple Choice, eine richtige Option | `q`, `options` (Array), `correct` (Index), `why` | Klick auf Option |
| `tf` | Wahr/Falsch | `q`, `correct` (`true`/`false`), `why` | Klick Wahr oder Falsch |
| `cloze` | Lückentext, eine Antwort | `q` (mit `__` als Lücke), `answer`, `why` | Eingabe, Vergleich ohne Groß-/Kleinschreibung |
| `text` | Freitext, mehrere akzeptierte Antworten mit `;` | `q`, `answer` (z. B. `a;b;c`), `why` | Eingabe, Treffer wenn eine Alternative passt |

Der Flashcard-Modus ist **separat** und wird nicht über `QUESTIONS` gesteuert, sondern über eine eigene Datei:

- `type`: flashcard (eigene HTML-Datei, z. B. `reports/flashcards-<slug>.html`)
- Karten: Frage vorne, Antwort hinten, Klick zum Umdrehen, Selbstbewertung richtig/falsch
- **Kein** Query-Parameter-Modus mehr (`?quiz_mode=...` ist unzuverlässig, siehe Lessons unten)
- **Kommentar-Konflikt vermeiden:** Die Kommentar-Engine (`static/js/comments.js`) behandelt jedes Element mit der Klasse `.card` als kommentierbar und fängt dessen Klicks ab. Flashcard-Karten daher **nicht** `.card` nennen, sondern z. B. `.fc-card`.

**Ergebnis-Typen** (für `/api/quiz/result`):
- Quiz: `type: "quiz"`, Eintrag enthält `answers` mit `correct`/`chosen`/`expected` pro Frage
- Flashcard: `type: "flashcard"`, Eintrag enthält Anzahl richtig/falsch

**Referenzen für neue Quizze:** Beispiel-Quiz und Beispiel-Flashcard-Datei stehen unter `reports/` (siehe Abschnitt 7).


# 5. Deactivation / fallback

If the backend is unreachable and cannot be started:
- Do **not** execute the skill.
- Tell the user: "Report-Viewer backend not reachable at localhost:8765 — skill deactivation. Check `/tmp/rv.log` or run `cd /config/clawd/skills/report-viewer && ./start.sh` manually."
- Never produce fake URLs.

## 6. Smoke tests (definition of done)

- [ ] Pre-flight: backend already running → "already running" message.
- [ ] Pre-flight: backend not running → starts via `start.sh` → "started successfully".
- [ ] `curl -X POST .../api/publish` with a small `md` payload → response contains a `url` → paste in chat, confirm.
- [ ] Add a comment in the browser → `GET /api/comments?filename=...` shows it → patch source → `POST /api/publish` (same `filename`) → `POST /api/comments/<id>/resolve` → F5 → comment gone.
- [ ] Graceful degradation: `start.sh` fails → skill refuses and tells user.

## 7. References

- Viewer project (skill dir): `/config/clawd/skills/report-viewer/`
- Similar skill: `skills/session-closeout/SKILL.md`
- Quiz template: `references/quiz-template.html`
- Quiz results dashboard: `/quiz-results` (live, auto-aggregiert)