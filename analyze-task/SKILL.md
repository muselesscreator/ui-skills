---
name: analyze-task
description: Pre-planning fact-gathering for UI work. Resolves the fixed, task-independent context — repo learnings, in-flight branch state, tooling constraints, task classification, and the files the user explicitly named — and distills it into a single bounded "task context" artifact. /plan-ui consumes it today; /impl-ui, /validate-ui, and /pr-review-ui can adopt it to stop re-deriving the same facts. Use before planning, or whenever you want the constraints around a task gathered without committing to an approach.
version: 1.0.0
triggers:
  explicit:
    - analyze task
    - analyze this task
    - gather context for
    - what are the constraints for
  strong_intent:
    - what do I need to know before planning
    - what's in flight that affects this
  question_form:
    - what tooling rules apply here
    - what files does this touch
confidence_threshold: 75
---

# analyze-task

**Arguments**: $ARGUMENTS — description of the UI task to analyze.

This skill gathers **fixed facts** only — the constraints knowable *before* any planning judgment. It deliberately does **not** discover the full set of affected files (that is a planning conclusion, and belongs to `/plan-ui`). The seam is **mentioned vs. affected**: files the user *named* are metadata and are read here; files the change *turns out to touch* are discovered later, during planning.

Its product is a distilled, reusable artifact — not a dump of raw file contents.

## Step 1: Resolve context

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
OUT=~/.claude/skill-output/$REPO/$BRANCH
mkdir -p "$OUT"
```

## Step 2: Load and refresh repo learnings

Load learnings. Source depends on the repo:
```bash
[ -d "$(git rev-parse --show-toplevel 2>/dev/null)/wiki" ] && SRC=wiki || SRC=flat
```

**If SRC=wiki (work repo — canonical):** query QMD scoped to `collections: ["wiki"]` with an `intent`. Always pull reference implementations, gotchas/conventions, file placement, and enforced standards (TS/ESLint/Prettier); add a keyword-driven sub-query per the task's focus (components / data-fetching / state). Read top `qmd://wiki/...` hits with `_get`/`_multi_get`. The wiki is maintained via `/wiki-ingest`, so no staleness check is needed.

**If SRC=flat (OSS/reference repo):** read `~/.claude/repo-learnings/$REPO/index.md` (reference implementations), `gotchas.md`, `file-structure.md`, `standards.md` always; add `ui-patterns.md`/`advanced-patterns.md` based on task keywords. Check freshness from the `Last analyzed` header — if >20 source files changed since:
```bash
git log --since="{last-analyzed}" --name-only --pretty=format: | sort -u | grep -v '^$' | grep -E "\.(ts|tsx|js|jsx)$" | wc -l
```
If stale, call `/update-learnings` then re-read.

If a `learnings-context-latest.md` already exists in `$OUT` (a prior `/load-learnings` run in this branch), read it instead of re-querying — it is already distilled.

If neither source yields anything:
```
⚠ No learnings found for {repo-name}. For a work repo run /wiki-index; for an OSS checkout run /learn-repo.
Proceeding with live analysis only — this will be slower.
```

## Step 3: Check in-flight branch state

Snapshot what's already changed on the branch so the analysis (and the plan downstream) doesn't collide with in-progress work.

```bash
git diff --name-only $(git merge-base HEAD main 2>/dev/null) HEAD 2>/dev/null || git status --short | awk '{print $2}'
```

For each changed file relevant to the task (same feature area, shared components, data hooks), read it now. Note any pending changes that:
- Affect types or interfaces the task will touch
- Modify components the task depends on
- Add or remove patterns that contradict what learnings describe

Record these as **in-flight conflicts** in the artifact — do not resolve them; planning does that.

## Step 4: Read tooling config

Find and read the project's enforcement config so downstream steps account for rules that will block implementation.

**TypeScript:**
```bash
find . -name "tsconfig*.json" -not -path "*/node_modules/*" | head -10
```
Read the relevant tsconfig(s) (prefer app-level over root). Note strict flags that affect UI code: `strict`, `strictNullChecks`, `noImplicitAny`, `noUncheckedIndexedAccess`, `noImplicitReturns`, `exactOptionalPropertyTypes`, etc.

**ESLint:**
```bash
find . -maxdepth 3 -name ".eslintrc*" -o -name "eslint.config.*" | grep -v node_modules | head -5
```
Extract rules relevant to UI work: import ordering, no-explicit-any, jsx rules, unused vars, no-restricted-imports, any plugin-specific rules.

**Prettier:**
```bash
find . -maxdepth 3 -name ".prettierrc*" -o -name "prettier.config.*" | grep -v node_modules | head -3
```
If present, note non-default settings (printWidth, singleQuote, trailingComma, etc.). If absent, note that Prettier defaults apply.

## Step 5: Classify the task and read the files it names

Parse the task description from $ARGUMENTS. Identify:
- Is this a new feature, a modification, a refactor, or a bug fix?
- What parts of the UI are involved? (new view, new component, new form, state change, style update)
- Which files does the task **explicitly name or reference**? Read those now — they are upfront metadata.

Do **not** go hunting for files the change might touch. Discovering the affected set is planning work; leaving it for `/plan-ui` is what keeps this artifact bounded and this step cheap.

If the task names no files, say so — that's a valid result, not a gap.

## Step 6: Write the task-context artifact

```bash
TS=$(date +%Y%m%d-%H%M%S)-$$
```

Distill everything from Steps 2–5 into a bounded artifact (aim ≤150 lines — synthesize, don't dump raw file contents). Write to `$OUT/analysis-$TS.md` with this exact frontmatter, then the body:

```
---
skill: analyze-task
repo: {repo}
branch: {branch}
timestamp: {ISO-8601 datetime}
task: {one-line task description from $ARGUMENTS}
---

## Task Classification
- Kind: {feature | modification | refactor | bug-fix}
- UI surface: {new view / component / form / state / style — what's involved}

## Mentioned Files
{Files the task explicitly named, each with a one-line note on what it currently does and why the task references it. Or "None named in the task."}

## In-Flight Conflicts
{From Step 3. Each: `{file}` — pending edits that affect {aspect}. Or "None — branch is clean relative to the task area."}

## Tooling Constraints
**TypeScript:** {strict flags that affect this implementation}
**ESLint:** {rules that will reject common patterns — no-explicit-any, import order, restricted imports}
**Prettier:** {non-default settings, or "defaults apply"}

## Relevant Learnings
**Reference implementations:** {most relevant files for this task type, path — one-line purpose. Max 8.}
**Patterns:** {actionable patterns relevant to the task, 1-2 sentences each.}
**File placement:** {where this kind of file goes in this repo.}
**Gotchas:** {one line each — all that are relevant; these are small and load-bearing.}

## Notes for Planning
{Anything the planner should weigh that isn't a hard fact — open ambiguities in the task framing, suspected-but-unconfirmed overlaps with in-flight work. Keep to 1-3 lines, or "None."}
```

If a section has no content, write the header with `(none)` so downstream skills know it was checked, not skipped.

Then symlink the latest:
```bash
ln -sf analysis-$TS.md "$OUT/analysis-latest.md"
```

If any step failed (QMD unreachable, no config readable), write the artifact anyway with an `## ERROR` section at the top describing what failed. Never fail silently.

## Step 7: Summary

Print a compact summary to the conversation:

```
Task analysis written to: {relative path}

**Task:** {one-line classification}
**Mentioned files:** {count, or "none named"}
**In-flight conflicts:** {count, or "none"}
**Tooling:** TS {strict? yes/no} · ESLint {key rule count} · Prettier {present/defaults}

Ready for /plan-ui — it will read analysis-latest.md, discover affected files, and produce the plan.
```

Do not restate the artifact. This step is fact-gathering only — surface no approach, no recommendation, no plan.
