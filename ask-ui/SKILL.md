---
name: ask-ui
description: Answers a question about a plan, a section of code, or the current branch. Loads repo learnings and tooling constraints as context, reads the targeted code or plan, and produces a focused answer with file:line references. Read-only — never edits code. Use when you have a question about how something works, why a pattern is used, what a plan implies, or whether an approach fits the repo.
version: 1.0.0
triggers:
  explicit:
    - ask ui
    - answer this
    - explain this
    - explain the plan
  strong_intent:
    - how does this work
    - why is this done this way
    - what does this plan mean
    - walk me through
  question_form:
    - what is this
    - why does this
    - how does this
    - what happens when
confidence_threshold: 70
---

# ask-ui

**Arguments**: $ARGUMENTS — the question, optionally with a target (file path, "the plan", "this branch", "this change"). Examples:
- `ask-ui why does AccountForm use a controller wrapper`
- `ask-ui explain the plan`
- `ask-ui what would change in this branch if I switched to TanStack Query`

This is a **read-only** skill. It answers questions about existing code, plans, or pending changes. It does not edit files or run lint/typecheck. If the question implies a change, describe what the change would look like — do not perform it.

## Step 1: Parse the Question and Target

Read $ARGUMENTS. Separate:
- **Question**: what the user is asking
- **Target** (if explicit): a file path, "the plan", "this branch", "this change", or "this PR"

Target resolution rules — try in order, stop at first match:

1. **Explicit file path(s) in the question** (e.g., `apps/foo/Bar.tsx`, `Bar.tsx:42`):
   - Read each path. If a line number is given (`:N`), focus reading on lines around N (±30).

2. **"the plan" / "this plan" / "current plan"**:
   ```bash
   REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
   [ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
   BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
   ls -t ~/.claude/skill-output/$REPO/$BRANCH/plan-*.md 2>/dev/null | head -1
   ```
   Read the most recent plan file. If none exists, report:
   ```
   ⚠ No plan found for $REPO/$BRANCH. Run /plan-ui first, or pass a file path / question scope.
   ```
   Stop and ask the user how to proceed.

3. **"this branch" / "this change" / "this PR" / "the diff"**:
   ```bash
   git diff --name-only $(git merge-base HEAD main 2>/dev/null) HEAD 2>/dev/null
   ```
   If empty, fall back to staged + unstaged:
   ```bash
   git status --short | awk '{print $2}'
   ```
   Read each changed file. If many files (>10), read the ones whose names match keywords from the question; for the rest, just note their paths.

4. **No explicit target — open question**:
   - Extract the most meaningful noun(s) from the question.
   - Grep the repo to find candidate files:
     ```bash
     grep -rl "<noun>" --include="*.ts" --include="*.tsx" . 2>/dev/null | grep -v node_modules | head -10
     ```
   - If 0 candidates: ask the user to point to a file or scope (do not guess).
   - If 1–3 candidates: read all of them.
   - If 4+ candidates: read the top 3 by match relevance and note the others as `also referenced in: …`.

Record the resolved target — every subsequent step works against it.

## Step 2: Load Repo Learnings (Scoped)

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
```

Pick the source by what the repo has:
```bash
[ -d "$(git rev-parse --show-toplevel 2>/dev/null)/wiki" ] && SRC=wiki || SRC=flat
```

**If SRC=wiki** — query QMD scoped to `collections: ["wiki"]` with an `intent`. Always run a gotchas/conventions query; add a keyword-driven sub-query for the most specific noun in the question (components / data-fetching / state / routing / testing as relevant). Read the top `qmd://wiki/...` hits with `_get`/`_multi_get`.

**If SRC=flat** — read `~/.claude/repo-learnings/$REPO/index.md` and `gotchas.md` always; conditionally add `ui-patterns.md`/`advanced-patterns.md`/`test-patterns.md` based on the question's keywords.

If neither source yields anything:
```
⚠ No learnings found for {repo}. Answering from code only — accuracy may be lower for conventions/gotchas.
```
Proceed without halting.

Cap total loaded learnings at ~150 lines of synthesized notes — trim, do not paste verbatim.

## Step 3: Load Tooling Constraints (Only If Relevant)

Skip this step unless the question touches: types, strict mode, lint rules, import order, formatting, build config, module resolution, path aliases.

If relevant:
- Read root `tsconfig.json` (and app-level if it overrides) — note strict flags that affect the answer.
- Read ESLint config — note rules that explain the code's shape.
- Read Prettier config — only if formatting is in scope.

Do not list all rules. Only mention the constraints that bear on the specific question.

## Step 4: Read the Target

Re-read the target files from Step 1 with the question in mind. For each file, identify:
- The exact section that answers the question (note line ranges).
- Imports / dependencies relevant to the question.
- Related files referenced from the target (read them only if needed to answer — do not read transitively beyond one hop).

If the target is **the plan**:
- Read its sections in order. Note any "Open Questions" — these may be what the user is asking about.
- Cross-reference plan claims against current code state (does the file the plan references actually exist? Does the pattern it cites still exist?).

If the target is **the branch**:
- Use `git diff` to see what changed, not just file contents — the question is usually about the change, not the file as a whole.
  ```bash
  git diff $(git merge-base HEAD main 2>/dev/null) HEAD -- <file>
  ```

## Step 5: Answer

Produce a direct, focused answer. Structure:

```
## Answer

{1–4 sentences directly answering the question. Lead with the answer, not the setup.}

### Evidence
- `path/to/file.tsx:42-58` — {what this code does that supports the answer}
- `path/to/other.tsx:12` — {related reference}

### Relevant constraints (only if Step 3 ran)
- {tooling rule that explains the shape of the answer, e.g., "noUncheckedIndexedAccess forces the optional chain at L48"}

### Relevant learnings (only if any were load-bearing)
- {1-line gotcha or pattern, with the note name in parentheses}

### Caveats / what I didn't check
- {anything outside the scope read — e.g., "didn't follow the hook into its server handler"}
- {open questions in the plan that bear on the answer, if target was a plan}
```

Rules for the answer:
- Lead with the conclusion. No "Great question…" or preamble.
- Always cite `file:line` (or `file:line-range`) for claims grounded in code.
- If the answer requires speculation (e.g., the code is ambiguous), say so explicitly — do not invent a confident answer.
- If the question is unanswerable from the target you read, say what would need to be read to answer it, and ask whether to proceed.
- Do **not** propose edits unless the user asked "how would I change X" — and even then, describe, don't execute.

## Step 6: Write Answer File (Only If Substantive)

If the answer is more than a couple of sentences or references multiple files, persist it so a follow-up agent can pick it up:

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write to `~/.claude/skill-output/$REPO/$BRANCH/ask-ui-$TS.md` with frontmatter:

```
---
skill: ask-ui
repo: {repo}
branch: {branch}
timestamp: {ISO-8601 datetime}
question: {original $ARGUMENTS, one line}
target: {resolved target from Step 1}
---
```

Then the answer content from Step 5.

For short answers (single-sentence or single-file references), skip the file write — just respond inline.
