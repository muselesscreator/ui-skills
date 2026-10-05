# adhd-format — rationale

Why the rules in `SKILL.md` and the defaults in `template.html` are what they are. Not loaded at runtime.

### "restyle only. Every source sentence appears in the output unchanged"

A reformatting tool that quietly drops or rewrites a sentence is worse than no tool: the reader trusts the restyled copy instead of the original. Plain-language rewriting was considered and rejected for v1 because no deterministic check can prove a rewrite kept the meaning. Sentence-level alignment can prove a restyle kept the wording, so the skill only does what it can verify.

### "Anything you write yourself goes inside a `:::` block or a `{+}` heading"

The fidelity check needs a mechanical way to tell added text from source text, and the reader needs the same distinction visually. One marker serves both: the checker strips these regions, and the template tints and labels them "added".

### `:::tldr` "first thing after the title, always"

Working memory is small and starting is the hardest step for ADHD readers. A summary up front lets the reader decide what matters before committing to the full text (W3C COGA, "Making Content Usable for People with Cognitive and Learning Disabilities").

### "Aim for 150–400 words per section"

Sections are the unit of progress: each gets a reading time, a contents entry, and a "Done — next section" button. Sections much longer than this make the progress bar stall; much shorter ones make the contents list too long to scan.

### "Bold sparingly"

Emphasis only works when it is rare. When most of a paragraph is bold, nothing stands out (British Dyslexia Association style guide; the same reasoning applies to attention).

### Template default: Atkinson Hyperlegible, 18px, line-height 1.75, ~64ch measure, left-aligned, off-white ground

These follow the BDA style guide and COGA guidance: sans-serif, 16px or larger, line spacing of at least 1.5, 60–75 characters per line, no justified text, no pure white background. Italic emphasis is rendered upright with an underline because italics reduce legibility for many readers.

### Template: "Bold word starts" off by default, never called "Bionic Reading"

Controlled studies of Bionic-style fixation bolding found no improvement in reading speed or comprehension, but some readers prefer it, so it is a toggle. "Bionic Reading" is a registered trademark, so the UI uses a generic name. Implemented with `text-vide` (MIT), loaded from jsdelivr.

### Template: OpenDyslexic offered as an option, not the default

There is no measured reading benefit from dyslexia-specific fonts, but some readers prefer them. The font is embedded from `@fontsource/opendyslexic` (SIL OFL 1.1) as `opendyslexic.css` because the artifact CSP only allows Google Fonts as a font host.

### `[[wiki-links]]` stay verbatim in the markdown and are resolved at render time

Obsidian-style notes link with `[[target|alias]]`, which reads as noise when shown raw. Rewriting them in `restyled.md` would make the fidelity check flag every linked sentence as altered, so the markdown keeps them as written and the page shows each as its alias (or target). `lib/adhd-links.py` resolves targets from `source-path.txt`: another reading page restyled from that note first, so a set of restyled notes links to itself; then the note in its Obsidian vault; then the `.md` file. Unresolved links stay readable text. The hrefs are applied after DOMPurify, because it strips `obsidian:` and `file:` URLs.

### Frontmatter is folded into a "Note metadata" panel, not deleted

YAML frontmatter is source text, so `restyled.md` keeps it and the fidelity check sees it unchanged. Rendered as markdown it is noise — its closing `---` even turns the whole block into a setext heading. The render script lifts a leading `---` block (only blank lines or `:::` blocks above it) into a collapsed panel in the header: off the reading path, still on the page.

### Prior art

As of 2026-10, the closest existing tool was `snow-shen/adhd-reader` (a Claude Code skill producing a paged HTML reader, without a wording check). The popular "ADHD" skills (`i-have-adhd`, `hyperfocus`, `attention-span`) reformat Claude's replies, not documents. No existing tool combined a verbatim restyle, a fidelity check, and an interactive reader, so the restructure prompt, the checker, and the template are built here.
