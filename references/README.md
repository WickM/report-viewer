# Report Templates

Templates for recurring reports. Each template is a Markdown file with placeholders in `[square brackets]`. When publishing with `source_path`, replace the placeholders; the rest stays as is.

## Templates

| Template | When | Format |
|----------|------|--------|
| `weekly-status.md` | Weekly status report (Mon–Fri, traffic light, top 3) | `md` |
| `research-summary.md` | Research summary (thesis, evidence, counter-evidence, conclusion) | `md` |
| `architecture-decision.md` | Architecture decision (ADR format: context, decision, consequences) | `md` |
| `flashcard-template.html` | Interactive flashcard (flip + right/wrong). Fill `[TITLE]` and `CARDS` | `html` |
| `flashcard-wine.md` | Spec: how an LLM creates flashcards from the template (any topic) | — |
| `quiz-template.html` | Interactive quiz with multiple choice + automatic result saving | `html` |

## Custom template

See `CUSTOM.md` — five steps to your own template.

## Usage

1. Copy a template from `references/`
2. Replace the `[...]` placeholders
3. Save as a `.md` file (e.g. in the brain vault under `03_Projects/` or `brain/research/`)
4. Publish with `source_path`:
   ```bash
   curl -s -X POST http://localhost:8765/api/publish \
     -H "Content-Type: application/json" \
     -d '{"title":"[Title]","format":"md","source_path":"/path/to/file.md"}'
   ```
