# Create Your Own Report Template

Five steps to add a new template for recurring reports.

## Step 1: Copy a template

```bash
cp references/weekly-status.md references/[my-report].md
```

Or start from any existing template and adapt it.

## Step 2: Define placeholders

Replace every `[square bracket]` placeholder with concrete content for your report. Rule of thumb:

- **Content** = `[what goes here]`
- **Structure** = `[how many points / rows]`
- **Format** = `[traffic light, date, URL, etc.]`

Example:
```markdown
# [Project] — [Report type]
**Period:** [CW XX]
**Status:** [🟢🟡🔴]
```

## Step 3: Register it in README

Add an entry to `references/README.md`:

```markdown
| [my-report].md | [When to use it?] | [Format: md/html/excalidraw] |
```

## Step 4: Test

Create a test report with the new template:

```bash
curl -s -X POST http://localhost:8765/api/publish \
  -H "Content-Type: application/json" \
  -d '{"title":"Test [my-report]","format":"md","content":"# Test\n\n[Placeholder] example"}'
```

Check in the browser that:
- all placeholders make sense
- the layout (Mermaid, KaTeX, tables) renders correctly
- the comment function works

## Step 5: Commit

```bash
git add references/[my-report].md references/README.md
git commit -m "feat: add [my-report] template"
git push
```

Done. The template is now available to every agent that uses the report-viewer skill.

## Tips

- **Reusability:** Keep placeholders generic (`[Project]` instead of `[FooBar]`) so the template works for several projects.
- **Versioning:** If you change a template fundamentally, commit it as a breaking change and bump the skill version.
- **Examples:** see `weekly-status.md`, `research-summary.md`, `architecture-decision.md`.
