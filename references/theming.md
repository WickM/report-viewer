# Theming — Report-Viewer

The viewer's look is driven by **CSS custom properties** in the `:root` block of
`static/css/style.css`. Changing the theme = editing those variables. Everything in
the chrome (header, cards, comment panel, dashboard, quiz/flashcard forms) reads
`var(--…)` — so a single palette swap re-themes the whole app.

## 1. The variables (the only knobs you need)

| Variable        | Meaning                          | Default (OpenClaw dark) |
|-----------------|----------------------------------|--------------------------|
| `--bg`          | page background                  | `#1e1e28`                |
| `--bg-card`     | card / panel / header background | `#282832`                |
| `--bg-hover`    | hover state (cards, buttons)     | `#343541`                |
| `--border`      | borders, dividers                | `#505050`                |
| `--text`        | primary text                     | `#e0e0e0`                |
| `--text-muted`  | secondary / meta text            | `#808080`                |
| `--accent`      | links, focus, primary buttons    | `#8abeb7`                |
| `--accent-hover`| accent on hover                  | `#a8d4cc`                |
| `--radius`      | corner radius                    | `6px`                    |
| `--font-sans`   | body font stack                  | system stack             |
| `--font-mono`   | code font stack                  | mono stack               |
| `--success`     | success / correct                | `#b5bd68`                |
| `--error`       | error / danger / delete          | `#cc6666`                |
| `--warning`     | warning / highlight              | `#ffff00`                |

Format-badge colors (`.fmt-*`) are **hardcoded** per badge in `style.css`
(`.fmt-md`, `.fmt-html`, `.fmt-excalidraw`, `.fmt-quiz`, `.fmt-flashcard`).
Adjust them manually to match a new accent if the badge colors clash.

## 2. How to change the theme (LLM procedure)

**Rule: the default (OpenClaw dark) theme is always kept as the fallback.** Never
overwrite the base `:root` block. Instead, add a new theme as an **override block**
keyed by a `data-theme` attribute on `<html>`, so the default still applies when no
attribute is set. This makes every custom theme reversible in one line (remove the
attribute / delete the block) and the dark theme is never lost.

1. **Decide the palette** from the user's request (e.g. "light theme", "blue/white",
   "high contrast"). Pick values for the 14 variables above. Keep contrast readable:
   `--text` must be clearly distinguishable from `--bg`; `--accent` from `--bg-card`.
2. **Add an override block** in `static/css/style.css`, after the base `:root`:
   ```css
   html[data-theme="light"] {
       --bg: #f5f5f5;
       /* …all 14 variables… */
   }
   ```
   Do **not** restructure the CSS or touch the base `:root`. Optionally retint the
   `.fmt-*` badge colors inside the same block if they clash on the new background.
3. **Activate the theme** by setting the attribute. For a global default switch, add
   `<html data-theme="light">` in the templates (index, report, excalidraw wrapper in
   `app.py`) — or set it per-report. No server restart needed for CSS-only changes;
   the browser may need a hard reload (Ctrl+Shift+R).
4. **Revert**: remove the `data-theme` attribute (back to the dark default) or delete
   the override block. The dark theme is always intact.
5. **Verify**: open the dashboard (`http://localhost:8765`) and one report of each
   type; confirm text is legible and accents are visible.

## 3. Worked example — light theme (as an override, dark stays the fallback)

Append this block **after** the base `:root` in `style.css` (do not edit `:root`):

```css
html[data-theme="light"] {
    --bg: #f5f5f5;
    --bg-card: #ffffff;
    --bg-hover: #e8e8e8;
    --border: #c0c0c0;
    --text: #222222;
    --text-muted: #666666;
    --accent: #2563eb;
    --accent-hover: #1d4ed8;
    --radius: 6px;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-mono: "SF Mono", "Fira Code", "Fira Mono", "Roboto Mono", monospace;
    --success: #15803d;
    --error: #b91c1c;
    --warning: #a16207;
}
```

Then set `<html data-theme="light">` to activate it. Remove the attribute to fall
back to the dark default. Badge colors are mid-tone with white text, so they stay
readable on light without changes (retint inside the block only if needed).

## 4. Re-theming already-published reports (they are frozen)

Published reports are **snapshots** — a CSS change does not reach them automatically.
Two ways to apply a theme to reports that already exist on disk
(`~/.report_viewer/reports/*.html`):

- **A. Re-publish** (preferred when you have the source): `POST /api/publish` with the
  same `filename`. The new HTML is built from the current templates, which carry the
  theme attribute. Use this for `md` / `excalidraw` / `quiz` reports you can regenerate.
- **B. In-place injection** (when the source is gone, or for a bulk switch): edit each
  existing file's `<html …>` tag to add `data-theme="light"`. This works because the
  report chrome (header, comment panel, cards) reads CSS variables — only the
  attribute is missing. It does **not** fix inline-hardcoded backgrounds (hand-built
  Chart.js dashboards, old excalidraw wrappers); for those, re-publish or patch the
  inline colors.

Bulk in-place switch (idempotent — skips files already themed):

```python
import re
from pathlib import Path
for f in (Path.home() / ".report_viewer" / "reports").glob("*.html"):
    html = f.read_text(encoding="utf-8")
    if "<html" not in html:
        continue
    def repl(m):
        tag = m.group(0)
        return tag if "data-theme" in tag else tag[:-1] + ' data-theme="light">'
    new = re.sub(r"<html[^>]*>", repl, html, count=1)
    if new != html:
        f.write_text(new, encoding="utf-8")
```

No server restart needed; hard-reload the affected pages. To revert all to dark, run
the same script but strip the `data-theme` attribute (or re-publish from dark templates).

## 4. Caveats (what a global swap does NOT re-theme)

- **Frozen published reports**: reports link `/static/css/style.css`, so the chrome
  (header bar, comment panel) updates automatically. But any **inline `<style>`** a
  specific report authored (e.g. a hand-built Chart.js dashboard with its own
  `background:#f5f5f5`, or the Excalidraw wrapper's `#1e1e28` body) does **not**
  follow the variables. Those need a re-publish with updated inline colors.
- **Chart.js palettes**: reports that hardcode chart colors (hex in `new Chart(...)`)
  keep them; update per-report if a full re-theme is required.
- **Excalidraw wrapper** (`_wrap_excalidraw` in `app.py`) uses inline hex for its
  header/canvas background — change those literals if the board chrome must match.

For a *complete* re-theme of a specific report, re-publish it (same `filename`) with
the new inline colors; the global `style.css` swap handles the shared chrome.
