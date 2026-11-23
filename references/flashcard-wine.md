# Flashcard Format Specification

This file tells an LLM how to create flashcards for the report-viewer skill. The wine example at the bottom is illustrative only. The rules apply to any topic.

## What a flashcard is

A flashcard is one question with one answer. The learner sees the question first, tries to recall the answer, then flips the card to check it, and rates it right or wrong.

## Rules for creating cards

1. **One fact per card.** A card asks one question with one answer. Split compound questions.
2. **Question on the front, answer on the back.** The front must be answerable from memory alone.
3. **Short answer.** The back is 1 to 2 lines. Put extra context in the optional `note`.
4. **Unambiguous.** A question must have exactly one correct answer. Avoid "what are the main…" without a closed list.
5. **No yes/no questions** unless the answer needs a reason. Prefer "what / which / how".
6. **Self-contained.** Each card must make sense alone, without the other cards.
7. **Language.** Use the language of the topic. Keep the file itself in English.
8. **Count.** 5 to 15 cards per set. Fewer than 5 is too thin, more than 15 overloads one session.

## Required structure per card

Each card is one block with exactly these fields:

```
### <n>. <question on the front>
**Answer:** <answer on the back>
**Note:** <optional context, can be omitted>
```

## Set-level header

Every set starts with:

```
# Flashcards: <topic>
**Date:** YYYY-MM-DD
**Scope:** <what the set covers and what it does not>
```

## Output to the viewer

The set is published as Markdown (`format: "md"`) or converted to the interactive flashcard view (`format: "html"`, see `SKILL.md` section 4.5 / 4.6). Each card must render without manual edits.

## Self-check before publishing (for the LLM)

Before returning a set, verify:
- [ ] 5 to 15 cards
- [ ] every card has a question and an answer
- [ ] no card asks two things
- [ ] no answer depends on another card
- [ ] the header has date and scope

## Example (illustrative only, topic is wine)

### 1. Which grape is the main variety in red Burgundy?
**Answer:** Pinot Noir
**Note:** Pinot Noir is the only red grape allowed in red Burgundy AOC.

### 2. What does "terroir" describe?
**Answer:** The combined influence of soil, climate and location on a wine's character.
