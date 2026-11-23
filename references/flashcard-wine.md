# Flashcard Creation Spec (for LLMs)

Flashcards are **HTML**, not Markdown. An LLM creates a flashcard set by filling the template `flashcard-template.html` and publishing it as `format: "html"`. The wine example at the bottom is illustrative only. The rules apply to any topic.

## Workflow

1. Copy `flashcard-template.html`.
2. Replace `[TITLE]` with the set title (appears in `<title>` and `<h1>`).
3. Replace the `CARDS` array with 5 to 15 cards (see rules below).
4. Check the self-check list.
5. Publish: `POST /api/publish` with `format: "html"` and the full HTML as `content`.

Do not change the CSS, the markup, or the script. Only `[TITLE]` and the `CARDS` array change.

## What a flashcard is

One question on the front, one answer on the back. The learner tries to recall the answer, flips the card, and rates it right or wrong.

## Rules for each card

1. **One fact per card.** Split compound questions.
2. **Answerable from memory.** The question alone must be enough to try a recall.
3. **Short answer.** 1 to 2 sentences. No lists unless the answer is a closed list.
4. **Unambiguous.** Exactly one correct answer. No open "what are the main..." without a closed set.
5. **Prefer what / which / how.** Avoid yes/no unless the reason is the point.
6. **Self-contained.** No card refers to another card.
7. **Language.** The topic's language inside the card. The spec and template stay in English.
8. **Count.** 5 to 15 cards per set.

## Card format in the template

Each entry in `CARDS` is one object with exactly two keys:

```js
{ q: "<question>", a: "<answer>" },
```

Escape double quotes inside the text as `\"`. Do not add fields. The template renders `q` on the front and `a` on the back.

## Set title

`[TITLE]` is one line: `Flashcards: <topic>`. Include the scope if it helps, e.g. `Flashcards: EU AI Act, risk classes`.

## Self-check before publishing

- [ ] Output is a complete HTML document (not Markdown)
- [ ] `[TITLE]` replaced in `<title>` and `<h1>`
- [ ] 5 to 15 cards in `CARDS`
- [ ] every card has a non-empty `q` and `a`
- [ ] no card asks two things
- [ ] no leftover `[QUESTION` or `[ANSWER` placeholders
- [ ] valid JS: no unescaped quotes inside strings

## Example (illustrative only, topic is wine)

```js
const CARDS = [
  { q: "Which grape is the main variety in red Burgundy?", a: "Pinot Noir" },
  { q: "What does \"terroir\" describe?", a: "The combined influence of soil, climate and location on a wine's character." }
];
```
