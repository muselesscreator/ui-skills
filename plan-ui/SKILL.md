---
name: plan-ui
description: Pre-implementation planning for UI work. Loads repo learnings, reads relevant code, and produces a focused implementation plan with file placements, patterns to follow, and test impact analysis. Use when planning a UI feature, deciding where files should go, or choosing which patterns to follow before writing code.
version: 1.0.0
triggers:
  explicit:
    - plan ui
    - plan this feature
    - plan this change
    - plan before I implement
  strong_intent:
    - how should I approach this
    - where should I put this
    - what pattern should I follow for
  question_form:
    - how do I implement
    - where does this go
    - what's the right pattern for
confidence_threshold: 75
---

# plan-ui

**Arguments**: $ARGUMENTS — description of the UI task to plan

## Step 1: Load and Refresh Repo Learnings

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
```

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

If neither source yields anything:
```
⚠ No learnings found for {repo-name}. For a work repo run /wiki-index; for an OSS checkout run /learn-repo.
Proceeding with live analysis only — this will be slower.
```

## Step 2: Check Local Code State

Before reading tooling config, get a snapshot of what's in flight on the current branch. This prevents the plan from colliding with in-progress work.

```bash
# What's changed on this branch vs main?
BRANCH=$(git branch --show-current 2>/dev/null)
git diff --name-only $(git merge-base HEAD main 2>/dev/null) HEAD 2>/dev/null || git status --short | awk '{print $2}'
```

For each changed file that is relevant to the task (same feature area, shared components, data hooks), read it now. Note any pending changes that:
- Affect types or interfaces the task will touch
- Modify components the task depends on
- Add or remove patterns that contradict what learnings describe

Flag conflicts as:
```
⚠ In-flight change: {file} has pending edits that affect {aspect of the task}.
This plan accounts for those changes.
```

## Step 3: Read Tooling Config

Find and read the project's enforcement config so the plan can account for rules that will block implementation.

**TypeScript:**
```bash
# Find the relevant tsconfig (prefer app-level over root)
find . -name "tsconfig*.json" -not -path "*/node_modules/*" | head -10
```
Read the tsconfig(s). Note strict flags that affect UI code: `strict`, `strictNullChecks`, `noImplicitAny`, `noUncheckedIndexedAccess`, `noImplicitReturns`, `exactOptionalPropertyTypes`, etc.

**ESLint:**
```bash
find . -maxdepth 3 -name ".eslintrc*" -o -name "eslint.config.*" | grep -v node_modules | head -5
```
Read the config. Extract rules relevant to UI work: import ordering, no-explicit-any, jsx rules, unused vars, no-restricted-imports, any plugin-specific rules.

**Prettier:**
```bash
find . -maxdepth 3 -name ".prettierrc*" -o -name "prettier.config.*" | grep -v node_modules | head -3
```
If present, note non-default settings (printWidth, singleQuote, trailingComma, etc.). If absent, note that Prettier defaults apply.

Carry these constraints forward into the plan.

## Step 4: Understand the Task

Parse the task description from $ARGUMENTS. Identify:
- Is this a new feature, a modification, a refactor, or a bug fix?
- What parts of the UI are involved? (new view, new component, new form, state change, style update)
- Are there existing files that need to be read for context?

## Step 5: Read Relevant Existing Code

Based on the task, find and read:
- The most relevant existing feature for pattern reference (use reference implementations from `index.md` if relevant)
- The files that will be modified
- Any parent views or layouts that affect where this fits

## Step 6: Read Existing Tests for Affected Files

**Unit tests:** For each file identified in Step 5 as being modified, find and read its co-located test file(s):

```bash
# Find test files co-located with or adjacent to affected source files
# e.g. Component.tsx → Component.test.tsx, Component.spec.tsx, __tests__/Component.tsx
```

For each unit test file found:
- Note what is currently tested (happy path, edge cases, mocked dependencies)
- Identify tests that will break due to the planned changes (changed props, renamed exports, new required deps)
- Identify tests that will need to be extended to cover new behavior
- Note any mocks or fixtures that reference things being changed

If no unit test files exist for a modified file, flag it:
```
⚠ No unit tests found for {file} — new tests will need to be written from scratch.
```

**E2E tests:** Scan existing E2E specs for flows that exercise the affected feature area — even if those spec files are not being modified:

```bash
# Find specs that reference the feature area, affected component names, or route paths
grep -rl "{feature-name}\|{ComponentName}\|{route-path}" packages/e2e/tests/specs/ 2>/dev/null
```

For each E2E spec found that hits the affected area:
- Read the spec and its associated page object
- Identify which flows would exercise the changed component or behavior
- Determine if the change would break any existing flow (selector changes, new required interactions, changed page structure)
- Note any intercepts or data factories that reference the changed API surface

If no E2E specs cover the affected area:
```
⚠ No E2E coverage found for this feature area — consider whether a new spec is needed.
```

Carry all findings into the Test Plan section of the plan.

## Step 7: Produce Implementation Plan

Output a structured plan:

```
## Implementation Plan: {task description}

### Approach
[1-2 sentences on the overall approach]

### Files to Create
- {path} — {purpose}
- {path} — {purpose}

### Files to Modify
- {path} — {what changes and why}

### Patterns to Follow
- [specific pattern from learnings, with reference file]
- [specific pattern from learnings, with reference file]

### Gotchas to Avoid
- [specific gotcha relevant to this task]

### Tooling Constraints
**TypeScript:** [strict flags that affect this implementation — e.g., "strictNullChecks: all optional props need explicit undefined handling"]
**ESLint:** [rules that apply to planned code — e.g., "import/order enforced: group third-party before internal", "no-explicit-any: use unknown + type guard instead"]
**Prettier:** [non-default settings if any, or "defaults apply"]

### Test Plan

**Unit tests — updates required:**
- {test file}: {specific test(s) that break} — {what needs to change and why}
- {test file}: extend {test name} to cover {new behavior}
- (or "No existing unit tests affected")

**Unit tests — new coverage needed:**
- {path/to/Component.test.tsx}: cover {behavior/case}
- (or "None — existing coverage is sufficient")

**E2E tests — updates required:**
- {spec file}: {flow that breaks} — {what needs to change}
- (or "No existing E2E tests affected")

**E2E tests — new coverage needed:**
- {path/to/feature.spec.ts}: cover {user flow}
- (or "None — existing coverage is sufficient")

### Open Questions
[Any decisions that require user input before implementation]
```

Keep the plan concrete and short. Reference specific file paths wherever possible. Do not restate the steering docs — reference what the code actually does.

## Step 8: Write Output File

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write the full implementation plan produced in Step 4 to `~/.claude/skill-output/$REPO/$BRANCH/plan-$TS.md`. This file is read by `/impl-ui` when invoked with `use plan` — it picks up the most recent `plan-*.md` in the branch directory.

## Step 9: Final User-Facing Summary

After writing the plan file, print a summary to the conversation. The user should not have to open the plan file to know what decisions are pending.

**Rules:**
- **Always list every Open Question inline, in full** — verbatim from the plan, numbered, with any context/options needed to answer. Never write "see the plan for questions" or "open the plan to review questions."
- If the entire plan is short (under ~80 lines), print the whole plan inline instead of a summary. Still call out the Open Questions section explicitly at the end so it isn't missed.
- Otherwise, print a compact summary using this shape:

```
Plan written to: {relative path to plan file}

**Approach:** {one sentence}

**Scope:** {N files to create, M files to modify}

**Open Questions** ({count}):
1. {full question text, including any options or trade-offs}
2. {full question text, including any options or trade-offs}
...

(or "**Open Questions:** none — ready to implement" if there are zero)
```

If there are open questions, end the message by asking the user to answer them before `/impl-ui` runs. Do not proceed to implementation while questions are unanswered.
