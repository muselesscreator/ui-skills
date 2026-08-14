---
name: walkthrough
description: Visually explains a feature or set of code changes as a guided story/timeline — what files changed, why, and how the pieces connect. Produces an inline chat summary plus a published visual timeline artifact with code blocks. Use for a narrated tour of a diff, branch, PR, or existing feature — not for answering a single targeted question (use ask-ui for that).
version: 1.0.0
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

Read-only. Never edits code. Produces two things every run: a chat summary and a published HTML artifact (a numbered timeline with code blocks) rendered by a fixed template — you author only the markdown content, never HTML.

## Step 1: Resolve Scope and Mode

```bash
source ~/.claude/skills/lib/skill-env.sh
```

Try in order, stop at first match:

1. **Commit range or ref** in $ARGUMENTS (`a..b`, `HEAD~3`, a SHA) → `git diff <range>`.
2. **PR number** (`#123`, "PR 123") and `gh` available → `gh pr diff <n>` and `gh pr view <n> --json title,body`.
3. **"this branch" / "this change" / "the diff" / empty** → `git diff $(git merge-base HEAD "$BASE") HEAD`. If empty, fall back to `git status --short` (staged + unstaged).
4. **Explicit file/dir paths**, and they show no diff against `$BASE` → **feature-tour mode**: there is no change to narrate, so read the files as they stand and explain the existing design instead of a diff. Say so explicitly in the TL;DR ("no pending change — this is a tour of the current implementation").
5. **A prose feature description**, no path resolves → grep for the most relevant files (same fallback as `ask-ui` Step 1.4: 1–3 hits read fully, 4+ read top 3, note the rest). If zero hits, ask the user to point at a file or scope — do not guess.

Record: the diff (or file set), and whether this is **diff mode** or **feature-tour mode** — every later step depends on which.

## Step 2: Gather the "Why"

Pull rationale, not just content:

```bash
git log --format='%h %s%n%b' $(git merge-base HEAD "$BASE" 2>/dev/null)..HEAD -- <paths> 2>/dev/null
```

Add the PR body if Step 1 fetched one. Load repo learnings scoped to the touched area — same source rule as `ask-ui` Step 2 (QMD `wiki` collection if `$ROOT/wiki` exists, else `~/.claude/repo-learnings/$REPO/{index,gotchas}.md`) — pull conventions that explain *why* the code is shaped this way when commit messages don't say. Skip silently if neither source yields anything; do not halt.

## Step 3: Read and Cluster

Read the full diff hunks (or full file contents in feature-tour mode). **More than ~8 touched files**: delegate the raw reading to a fresh `general-purpose` agent — task it to return, per file, a one-line purpose and the 1–2 hunks/snippets most worth showing verbatim; then do the clustering and narrative judgment yourself from that summary plus a direct read of the 3–4 most important hunks. Below that threshold, read everything directly.

**Diff mode only** — gather per-file size alongside content, so a 2k-line change doesn't read the same as a 20-line one:
- Commit range / branch-vs-base / staged+unstaged: `git diff --numstat <range-or-nothing> -- <paths>` → `added<TAB>removed<TAB>path` per file.
- PR mode: `gh pr view <n> --json files --jq '.files[] | "\(.path)\t\(.additions)\t\(.deletions)"'`.

Keep these as `+added/-removed` per file for Step 4. **Feature-tour mode has no size concept — skip this gathering step entirely, don't zero-fill.**

Group files into narrative **chapters**, ordered so each chapter's premise is established before the next depends on it — typically: data/types → core logic → integration/wiring → UI/presentation → tests/docs. This ordering is the judgment call that makes it a story instead of a file listing; do not just follow alphabetical or diff order. In diff mode, sum each chapter's member files' add/remove counts as you cluster — Step 4 needs the per-chapter total.

## Step 4: Author the Walkthrough Markdown

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

{1-3 short paragraphs of narrative prose — the story, not a restatement of the diff}

```diff
- old line(s)
+ new line(s)
```

**Connects to:** {one line pointing at the next chapter — omit on the last chapter}

### {Next chapter title}
...

## What to Check
- {something worth verifying, testing, or a follow-up question}
```

Rules:
- **Role** column values: `foundation`, `core logic`, `integration`, `presentation`, `tests`, `docs` — pick the closest fit, don't invent new taxonomy per file.
- **Size** column and **Size:** chapter line are diff-mode only, format exactly `+{added}/-{removed}` (zero on either side is fine, e.g. `+18/-0`) — the template parses this literally. **Omit both entirely in feature-tour mode** — no column, no line; there's nothing to size.
- Chapter numbering is automatic in the artifact (don't hand-number titles).
- Use a ` ```diff ` fence only when you have a real before/after; in **feature-tour mode** use a plain fenced block (` ```ts `, etc.) showing the current code, and make `**Why:**` a design-rationale line, not a change-rationale line.
- Keep each chapter's narrative to what a reader needs to follow the story — cite `file:line` only when it disambiguates, not on every sentence.
- `## What to Check` is mandatory — even feature-tours get at least one item (e.g., "the edge case this doesn't handle").

## Step 5: Write Output File

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/walkthrough-$TS.md"   # ← write the Step 4 markdown to this exact path
```

## Step 6: Render and Publish the Artifact

**Always** publish. A fixed template renders the page — author no HTML, do not load `artifact-design`; the template already handles theme, contrast, and layout.

```bash
source ~/.claude/skills/lib/skill-env.sh
~/.claude/skills/lib/render-walkthrough-artifact.sh "$(ls -t "$OUT"/walkthrough-*.md | head -1)"
# prints the generated .html path
```

Call the **Artifact tool** with the printed `.html` path — `favicon: "🧭"` (stable across walkthrough artifacts), `description`: one sentence naming the feature/change, no `title` (the script injected one from the markdown's `# ` line). Each run mints its own URL.

## Step 7: Chat Summary

```
Walkthrough: {artifact URL}

**TL;DR:** {same 2-4 sentences as the markdown}

**Chapters** ({N}):
1. {chapter title}
2. {chapter title}
...

**What to check:**
- {item}
- {item}
```

Lead with the artifact link and TL;DR — those are the two things worth reading even if the reader never opens the page. Don't re-paste the full narrative or code blocks inline; the artifact carries those.
