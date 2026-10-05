---
name: adhd-format
description: Restyles a markdown or plain-text document into an ADHD-friendly reading page — summary first, short sections with reading times, action checklists, progress tracking, focus mode, and adjustable type — while keeping every original sentence word for word. A deterministic check proves no source wording was dropped, changed, or invented before the page is published as an artifact. Use when someone wants a document made easier to read, skim, or get through with ADHD (or any attention/reading difficulty) — not for rewriting or simplifying the wording itself.
version: 1.0.0
triggers:
  explicit:
    - adhd-format
    - make this adhd friendly
    - adhd friendly version
    - format this for adhd
  strong_intent:
    - make this easier to read
    - help me get through this document
    - I can't focus on this doc
  question_form:
    - can you make this doc easier to read
confidence_threshold: 70
---

# adhd-format

**Arguments**: $ARGUMENTS — a path to a `.md` or `.txt` file, or nothing (then use the text the user pasted in the conversation). Any other format: stop and say v1 accepts markdown and plain text only.

**The one hard rule**: restyle only. Every source sentence appears in the output unchanged and in its original order — typos, capitalization, and punctuation included. Anything you write yourself goes inside a `:::` block or a `{+}` heading. `lib/adhd-fidelity.py` enforces this; a run that has not passed it does not publish.

## Step 1: Capture the source

```bash
D=~/.claude/skill-output/adhd-format/<slug>-$(date +%Y%m%d-%H%M%S); mkdir -p "$D"; echo "$D"
```

`<slug>` is the file's basename without extension, or a 2–4 word kebab-case name for pasted text. Copy a file with `cp <path> "$D/source.md"`, then record where it came from with `realpath <path> > "$D/source-path.txt"` — the render step uses it to turn `[[wiki-links]]` into links. For pasted text, Write it to `$D/source.md` exactly as pasted. The source label for Step 4 is the file's basename, or `Pasted text`.

## Step 2: Write the restyled copy

Read `source.md` once, then Write `$D/restyled.md`. You may:

- **Chunk into sections.** The page splits sections at `##`. Aim for 150–400 words per section. Reuse the source's own headings (changing only their `#` level); where the source has none, add a heading with a trailing `{+}` — `## Getting your accounts {+}`. If the source has no title, add `# <title> {+}` as the first line.
- **Break up walls of text** at sentence boundaries: split paragraphs, or turn a run of sentences into bullets (each bullet holds whole sentences).
- **Bold sparingly** — the key term or the action in a paragraph, about one per paragraph. Never bold whole sentences.
- **Add blocks** (each is fenced by `:::<kind>` and a closing `:::` on their own lines; no nesting):

| Block | Where | Content |
|---|---|---|
| `:::tldr` | first thing after the title, always | 3–5 bullets, ≤ 60 words: what this is, what matters, what the reader must do |
| `:::actions` | right after `tldr` when the document asks the reader to do anything | `- [ ] <action>` items, verb first, one action each, with any deadline |
| `:::summary` | top of any section over 250 words | 1–2 sentences |
| `:::terms` | the section where jargon first appears, only when the document defines or relies on it | `- **term** — meaning`, drawn only from the document |
| `:::callout` | beside a buried deadline, warning, or requirement | the point restated in one sentence; the original sentence stays where it was |

Added text states only what the document says. No outside facts, no advice, no opinions. Leave code blocks, tables, links (including `[[wiki-links]]`), and quotes exactly as they are. Leave YAML frontmatter where it is, above the title — the page folds it into a "Note metadata" panel. Never move, merge, or reorder source sentences.

## Step 3: Verify — capped at 3 runs

```bash
python3 ~/.claude/skills/lib/adhd-fidelity.py "$D/source.md" "$D/restyled.md" > "$D/fidelity.txt"; echo "exit=$?"; cat "$D/fidelity.txt"
```

- `exit=0` → Step 4.
- `exit=1` → fix every listed line in `restyled.md` with Edit: restore dropped or altered sentences to the exact source text; move invented text into a `:::` block or delete it. Re-run.
- `exit=2` → structure error (unclosed or unknown block); fix and re-run.

Count every run. After the third failing run, stop and present the cap-exhaustion menu (`~/.claude/skills/AUTHORING.md` → Interaction contract) with the remaining residual from `fidelity.txt`. Do not publish a failing copy unless the user picks "accept the residual"; the page then shows a "wording check did not pass" chip.

## Step 4: Render and publish

```bash
~/.claude/skills/lib/render-adhd-artifact.sh "$D/restyled.md" "<source label>" "$D/fidelity.txt"
```

Publish the printed `.html` path with the Artifact tool: `icon: "book"`, `description` = one sentence naming the document. Re-running on the same document in this session republishes the same path. Never edit the HTML; change `adhd-format/template.html` if the page itself needs to change.

## Step 5: Report

In chat, in this order:

1. The artifact link.
2. One line on the result: `<N> sections · <M> min read · wording verified (<n>/<n> sentences)`.
3. Only if relevant: anything you did not restructure and why (for example, a long table left as is).
