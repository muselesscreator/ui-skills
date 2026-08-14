---
name: walkthrough
description: Visually explains a feature or set of code changes as a guided, plan-aware story/timeline — what files changed, why, whether it matches any plan/handoff on file, and how the pieces connect. Real diffs (or current file content, in feature-tour mode) are attached automatically per chapter, never hand-transcribed, with every touched file guaranteed a home. Produces an inline chat summary plus a published visual timeline artifact. Use for a narrated tour of a diff, branch, PR, or existing feature — not for answering a single targeted question (use ask-ui for that).
version: 2.1.0
triggers:
  explicit:
    - walkthrough
    - walk me through
    - walk me through this
    - explain this feature
    - explain these changes
    - explain this diff
    - teach me this diff
  strong_intent:
    - what changed and why
    - give me a tour of
    - narrate this change
  question_form:
    - what did this change do
    - how do these files fit together
confidence_threshold: 70
---

# walkthrough

**Arguments**: $ARGUMENTS — optional scope: a commit range (`abc123..def456`), a PR number, file/dir paths, "this branch"/"the diff", or a feature description. Empty defaults to the current branch's diff against the base branch.

Read-only. Never edits code — and never *shows* hand-copied code either: real diffs (or real file content, in feature-tour mode) are captured verbatim in Step 1 and attached automatically per chapter by the render step. Your job in Step 4 is narrative and structural judgment — grouping, why, plan alignment — never transcription. Produces two things every run: a chat summary and a published HTML artifact (a numbered timeline with attached code) rendered by a fixed template — you author only the markdown content, never HTML.

## Step 1: Resolve Scope and Mode, Capture the Ground Truth

```bash
source ~/.claude/skills/lib/skill-env.sh
```

Try in order, stop at first match:

1. **Commit range or ref** in $ARGUMENTS (`a..b`, `HEAD~3`, a SHA) → `git diff <range>`.
2. **PR number** (`#123`, "PR 123") and `gh` available → `gh pr diff <n>` and `gh pr view <n> --json title,body`.
3. **"this branch" / "this change" / "the diff" / empty** → `git diff $(git merge-base HEAD "$BASE") HEAD`. If empty, fall back to `git diff HEAD` (staged + unstaged combined).
4. **Explicit file/dir paths**, and they show no diff against `$BASE` → **feature-tour mode**: there is no change to narrate, so read the files as they stand and explain the existing design instead of a diff. Say so explicitly in the TL;DR ("no pending change — this is a tour of the current implementation").
5. **A prose feature description**, no path resolves → grep for the most relevant files (same fallback as `ask-ui` Step 1.4: 1–3 hits read fully, 4+ read top 3, note the rest). If zero hits, ask the user to point at a file or scope — do not guess.

Record: the diff (or file set), and whether this is **diff mode** (cases 1–3) or **feature-tour mode** (cases 4–5) — every later step depends on which.

**Persist the ground truth immediately** — this is what makes the completeness guarantee and attached-code rendering possible; Step 7 reads these files back, untouched by you:

- **Diff mode** (cases 1–3): write the *exact* diff used above to `$OUT/diff-$TS.patch`, and the touched-file list to `$OUT/files-$TS.txt` (one repo-relative path per line):
  ```bash
  # substitute whichever case matched:
  git diff <range-or-nothing> -- <paths> > "$OUT/diff-$TS.patch"
  git diff --name-only <range-or-nothing> -- <paths> > "$OUT/files-$TS.txt"
  # PR mode instead:
  gh pr diff <n> > "$OUT/diff-$TS.patch"
  gh pr view <n> --json files --jq '.files[].path' > "$OUT/files-$TS.txt"
  ```
  `files-$TS.txt` is the authoritative changed-file list Step 4's completeness sweep and Step 7's cross-check badge are measured against — every path in it must end up placed in the walkthrough.
- **Feature-tour mode** (cases 4–5): no diff exists, so write only the file list (expand any directory args with `find <dir> -type f`, and case 5's grep hits):
  ```bash
  printf '%s\n' <resolved file paths> > "$OUT/files-$TS.txt"
  ```
  Do not create a `diff-$TS.patch` — its absence is how Step 7 knows to synthesize attached content from current file text instead of a diff, and it's also how the completeness sweep knows to skip itself (see Step 4): a feature tour has no closed "changed files" set to be complete against.

## Step 2: Gather the "Why" — Commits, Learnings, Plans, Handoffs

Pull rationale, not just content:

```bash
git log --format='%h %s%n%b' $(git merge-base HEAD "$BASE" 2>/dev/null)..HEAD -- <paths> 2>/dev/null
```

Add the PR body if Step 1 fetched one. Load repo learnings scoped to the touched area — same source rule as `ask-ui` Step 2 (QMD `wiki` collection if `$ROOT/wiki` exists, else `~/.claude/repo-learnings/$REPO/{index,gotchas}.md`) — pull conventions that explain *why* the code is shaped this way when commit messages don't say. Skip silently if neither source yields anything; do not halt.

**Plan/handoff discovery** — most repos and branches won't have any of this; skip silently and move on the moment a lookup comes up empty, don't treat absence as a problem to solve:

- Look in `$OUT` (branch-scoped by `skill-env.sh`) for `plan-*.md` (written by `/plan-ui`) and `handoff-*.md` (written by `/savepoint`). Take the most recent of each by mtime.
- If a `plan-files.txt` sits alongside a plan, it's that plan's declared file scope (written by `/plan-ui` Step 5) — prefer a plan whose `plan-files.txt` overlaps this walkthrough's `files-$TS.txt` over an unrelated stale one; if several plans exist and none overlap, treat none as relevant.
- Check `$DECISIONS_HOME` for decision memos with `status: open` in their frontmatter whose title or body references a touched file or the plan you picked — an open memo touching a chapter is worth a line in that chapter's Why (e.g. "still an open question — see decision memo {id}"), not a flag of its own.
- Record what you found: the plan path (and its `plan-files.txt` contents, if present), the handoff path, and any relevant open memo ids/titles. Step 4 uses this for Why-lines, `deviation`/`undocumented`/`tradeoff` flags, and the `## Plan Coverage` section. Found nothing → proceed exactly as before, no plan context, no coverage section, no fabrication.

## Step 3: Read and Cluster

Read the full diff hunks (or full file contents in feature-tour mode). **More than ~8 touched files**: delegate the raw reading to a fresh `general-purpose` agent — task it to return, per file, a one-line purpose and the 1–2 hunks/snippets most worth showing verbatim; then do the clustering and narrative judgment yourself from that summary plus a direct read of the 3–4 most important hunks. Below that threshold, read everything directly.

**Diff mode only** — gather per-file size alongside content, so a 2k-line change doesn't read the same as a 20-line one:
- Commit range / branch-vs-base / staged+unstaged: `git diff --numstat <range-or-nothing> -- <paths>` → `added<TAB>removed<TAB>path` per file.
- PR mode: `gh pr view <n> --json files --jq '.files[] | "\(.path)\t\(.additions)\t\(.deletions)"'`.

Keep these as `+added/-removed` per file for Step 4. **Feature-tour mode has no size concept — skip this gathering step entirely, don't zero-fill.**

Group files into narrative **chapters**, ordered so each chapter's premise is established before the next depends on it — typically: data/types → core logic → integration/wiring → UI/presentation → tests/docs. This ordering is the judgment call that makes it a story instead of a file listing; do not just follow alphabetical or diff order. In diff mode, sum each chapter's member files' add/remove counts as you cluster — Step 4 needs the per-chapter total.

Default to **more, smaller chapters** over fewer large ones — a chapter is one idea you'd explain to a colleague in a sentence, not a whole layer of the stack. Split on each distinct concern or responsibility rather than lumping everything from one layer into a single chapter — e.g. "data/types" is a stage in the ordering, not license to merge three unrelated type changes into one chapter. A chapter that needs more than ~3 paragraphs or covers more than one genuinely separate idea is a sign to split it, not a sign to trim the prose.

**Scale the chapter count to the size of the change:** a small change (roughly ≤8 touched files, or a few hundred lines) → 3–5 chapters; a large one → 8–12+. Don't fragment into trivia (an import tweak, a formatting-only file doesn't need its own chapter — fold it into the chapter it supports); don't lump unrelated changes together to hit a lower count.

**A single file can appear in more than one chapter.** When one file carries two distinct beats (e.g. it adds a type *and* wires up a new integration point), split it across both chapters and give each its own `**Focus:**` range (see "Code shown" below) — that's exactly the case `**Focus:**` exists for, so each beat highlights only its own lines instead of both chapters repeating the same full file.

**Every file in `files-$TS.txt` needs a chapter** (diff mode only — see Step 4's completeness rule). As you cluster, keep a running tally against that list; anything left over at the end is not a failure, it's the accessory pile — group tests/config/generated/lockfiles/fixtures into their own clearly-labeled chapter(s) ("Tests", "Config", "Generated") rather than letting them vanish. Don't read these deeply — a sentence or two per file is enough so the reader can acknowledge and move on.

## Step 4: Author the Walkthrough Markdown

### Voice

Write the way the best professor you ever had would explain this change to you over coffee. Warm, clear, a little human. They know the material cold, so they never show off — they just make it land.

- **One idea per sentence.** Short, complete sentences a person absorbs on the first read. Don't cram three thoughts into one clause stitched together with dashes and semicolons.
- **Lead with the point, then explain it.** "Re-running this has to be safe, because you'll do it dozens of times while tuning data. That's what this teardown protects." Not a pile of qualifiers before you reach the idea.
- **Don't narrate the code — it's attached right beside your words.** Explain the *why*: the problem it solves, the decision behind it, the thing that would bite someone who didn't know. ❌ "This loops over the jobs and creates a claim." ✅ "Seeded jobs have to link through the join table, or they quietly vanish from the list page. That link is the whole reason this file exists."
- **Plain, not technical-for-its-own-sake.** Gloss a domain term the first time it shows up. Reach for the everyday word over the jargon one.
- **Say it once.** No throat-clearing ("It's worth noting that…"), no filler, no restating the title in the first sentence.

Banned outright — the tics that make writing read like AI: word-collapsing density (loosen it into real sentences); corporate/AI vocabulary (*leverage, utilize, delve, robust, seamless, streamline, facilitate, in order to, it's worth noting, that said, moreover*); telegraphic fragments that drop articles ("Handles auth, validates input" → write full sentences); hype and sycophancy (no "elegant", "powerful", "cleverly" — don't praise the code or the author); hedging ("this seems to roughly handle…" — be direct, and put real uncertainty in `## What to Check` or a `risk` flag, not wishy-washy prose).

Lengths: chapter title = the idea in a few words (a beat, not a filename — "Re-runnable by design", never "Changes to core.ts"). Narrative = 1–3 short paragraphs. `**Why:**` = one line, only when there's a genuinely interesting decision to point at.

### Structure

Write markdown following this **exact** structure — the artifact template parses it mechanically, so headings and bold labels must match verbatim:

```markdown
# {Feature or change title}

## TL;DR
{2-4 sentences: what changed, why, in plain language}

## Cast of Changes
| File | Role | What / Why | Size |
|---|---|---|---|
| `path/a.ts` | foundation | {one line} | +42/-3 |
| `path/b.tsx` | integration | {one line} | +18/-0 |

## Timeline

### {Chapter title}
**Files:** `path/a.ts`, `path/b.ts`
**Size:** +60/-3
**Why:** {one-line rationale}
**Focus:** `path/a.ts`:42-58
**Flag:** risk — {one-line, only when genuinely worth a careful look}

{1-3 short paragraphs of narrative prose — the story, not a restatement of the diff. Never a manual code/diff fence: the real diff (or real current file, in feature-tour mode) for every listed file is attached automatically after this prose by the render step.}

**Connects to:** {one line pointing at the next chapter — omit on the last chapter}

### {Next chapter title}
...

## Plan Coverage
{only if Step 2 found a relevant plan/handoff — omit the whole section otherwise}
**Code with no plan:** {files changed here with no plan unit behind them, one line each — or "none"}
**Plan with no code:** {plan items this change doesn't touch, one line each — or "none"}

## What to Check
- {something worth verifying, testing, or a follow-up question}
```

Rules:
- **Role** column values: `foundation`, `core logic`, `integration`, `presentation`, `tests`, `docs` — pick the closest fit, don't invent new taxonomy per file.
- **Size** column and **Size:** chapter line are diff-mode only, format exactly `+{added}/-{removed}` (zero on either side is fine, e.g. `+18/-0`) — the template parses this literally. **Omit both entirely in feature-tour mode** — no column, no line; there's nothing to size.
- Chapter numbering is automatic in the artifact (don't hand-number titles).
- **Never author a ` ```diff ` or code fence in a chapter.** That's the one hard rule this version changes: real code is attached automatically (see "Code shown" below), so a hand-typed fence would just be a second, possibly-wrong copy of something already rendered. Your prose can still say *what* changed in words; it just can't paste it.
- Keep each chapter's narrative to what a reader needs to follow the story — cite `file:line` only when it disambiguates, not on every sentence.
- `## What to Check` is mandatory — even feature-tours get at least one item (e.g., "the edge case this doesn't handle").

### Code shown (attached, not authored)

You never write code into the walkthrough. Every path in a chapter's `**Files:**` gets its real content rendered automatically right after your narrative:
- **Diff mode:** the real diff hunks for that file, from the `diff-$TS.patch` you saved in Step 1 — not a snippet you chose, the whole thing.
- **Feature-tour mode:** the file's real current content, read fresh at render time.

Your only lever over what's shown is **`**Focus:**`** — optional, one entry per file, `path:start-end` using new-side line numbers (comma-separate multiple: `` `path/a.ts`:42-58, `path/b.ts`:5-12 ``). Focus dims the rest of that file's attached code and is purely emphasis — the full file/diff always renders regardless, so a focus range that's slightly off, or omitted entirely, never hides anything. Use it when a chapter only cares about part of a file, or when the same file is split across two chapters (give each its own focus range so a shared file reads differently in each beat — that's the point of splitting it).

### Completeness (diff mode only)

Because a reader might read this and then approve the change, it must never hide a file. Every path in `$OUT/files-$TS.txt` (the newest one, from Step 1) must appear in some chapter's `**Files:**` (or the Cast of Changes table). If your clustering in Step 3 left any unassigned, don't drop them — add a final chapter (e.g. "Everything else") that places every remaining path with at least a one-line note, even if it's just "generated output, not hand-written."

You don't have to get this perfect by hand: Step 7's render step independently diffs `files-$TS.txt` against every path you actually referenced, and anything you still missed gets swept into an auto-generated "Unplaced files" card with its own diff attached, plus an amber coverage badge instead of a green one. Placing everything yourself is still the goal — the sweep is a backstop, not a substitute for the judgment call of where a file belongs in the story. Feature-tour mode has no `files-$TS.txt` and no coverage concept — skip this entirely there, same as the Size rule.

### Review lens (flags) — use sparingly

Add `**Flag:** type — one line` to a chapter only when there's genuine, actionable signal. Most chapters have none — a wall of flags is noise; if unsure, leave it off.

| type | when |
|------|------|
| `deviation` | the code does something a plan/handoff you found in Step 2 said differently |
| `undocumented` | a real, non-trivial change with no plan/handoff behind it |
| `risk` | correctness/security/perf surface worth a careful look |
| `tradeoff` | a defensible choice that diverged from the plan — worth someone recording back into the plan doc |

`deviation`/`undocumented`/`tradeoff` only make sense when Step 2 actually found a plan or handoff to compare against — without one, only `risk` applies.

## Step 5: Self-Review Pass (Sonnet Critic)

Spawn a fresh `general-purpose` agent, `model: sonnet`, as a second pair of eyes on the Step 4 draft before anything is published — the same role product-agent's storyline tone-critic plays. Give it the full Step 4 markdown plus the Voice section above (banned list + rules), and ask it to return exactly one of:

- `CLEAN` — no violations, nothing to change.
- A full rewritten markdown — sentence-level fixes only, for banned vocabulary, hedging, telegraphic fragments, or hype. It must not restructure chapters, reorder them, touch `**Files:**` / `**Size:**` / `**Focus:**` / `**Flag:**` lines, add or remove a flag, or change any fact — narrative prose only.

Take the returned markdown (or the original, on `CLEAN`) forward as the final draft for Step 7.

## Step 6: Write Output File

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/walkthrough-$TS.md"   # ← write the Step 5 draft (post-critic) to this exact path
```

## Step 7: Render and Publish the Artifact

**Always** publish. A fixed template renders the page — author no HTML, do not load `artifact-design`; the template already handles theme, contrast, and layout. The script locates `diff-*.patch` / `files-*.txt` itself (newest by mtime, same directory as the markdown) — nothing extra to pass:

```bash
source ~/.claude/skills/lib/skill-env.sh
~/.claude/skills/lib/render-walkthrough-artifact.sh "$(ls -t "$OUT"/walkthrough-*.md | head -1)"
# prints the generated .html path
```

It embeds the real diff (or, absent a patch file, reads each touched file fresh for feature-tour mode), computes the coverage badge against `files-*.txt`, and appends the "Unplaced files" sweep if anything was missed — all deterministic, none of it authored by you.

Call the **Artifact tool** with the printed `.html` path — `favicon: "🧭"` (stable across walkthrough artifacts), `description`: one sentence naming the feature/change, no `title` (the script injected one from the markdown's `# ` line). Each run mints its own URL.

## Step 8: Chat Summary

```
Walkthrough: {artifact URL}

**TL;DR:** {same 2-4 sentences as the markdown}

**Chapters** ({N}):
1. {chapter title}
2. {chapter title}
...

**Coverage:** {e.g. "all 14 files ✓" or "12/14 files — 2 swept into Unplaced files"} — diff mode only, omit in feature-tour mode
**Flags:** {list any deviation/undocumented/risk/tradeoff flags raised, or omit this line if none}

**What to check:**
- {item}
- {item}
```

Lead with the artifact link and TL;DR — those are the two things worth reading even if the reader never opens the page. Don't re-paste the full narrative or attached code inline; the artifact carries those.
