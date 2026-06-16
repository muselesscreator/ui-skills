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

This skill owns the **planning judgment**: which files the change actually touches, the approach, the patterns to follow, the test impact, and the open questions. The fixed facts around the task — learnings, in-flight branch state, tooling constraints, task classification, user-named files — are gathered upstream by `/analyze-task` and consumed in Step 1. This skill does not re-derive them; it reasons over them and discovers the rest.

## Step 1: Load the Task-Context Artifact

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
OUT=~/.claude/skill-output/$REPO/$BRANCH
ANALYSIS=$(ls -t "$OUT"/analysis-*.md 2>/dev/null | head -1)
```

**If an analysis artifact exists** (`$ANALYSIS` is non-empty): read it. It supplies — already distilled — the task classification, mentioned files, in-flight conflicts, tooling constraints (TS/ESLint/Prettier), and relevant learnings. Trust it; do not re-query QMD or re-read tooling config. Carry its **Tooling Constraints** and **Gotchas** forward verbatim into the plan, and treat its **In-Flight Conflicts** as already-accounted-for.

**Fallback — no analysis artifact** (standalone `/plan-ui` with no prior `/analyze-task`): invoke `/analyze-task` with `$ARGUMENTS` first, then read the artifact it writes. If that is not possible, do the gathering inline — load learnings (QMD `wiki` collection for work repos, else `~/.claude/repo-learnings/$REPO/`), snapshot the branch diff against `main`, and read TS/ESLint/Prettier config — before continuing. Note in the plan that it ran without a pre-built analysis.

## Step 2: Read Relevant Existing Code

Now do the discovery the analysis deliberately left open — **which files this change actually touches.** Starting from the mentioned files and reference implementations in the artifact, find and read:
- The most relevant existing feature for pattern reference (use reference implementations from `index.md` if relevant)
- The files that will be modified
- Any parent views or layouts that affect where this fits

## Step 3: Read Existing Tests for Affected Files

**Unit tests:** For each file identified in Step 2 as being modified, find and read its co-located test file(s):

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

## Step 4: Produce Implementation Plan

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

## Step 5: Write Output File

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write the full implementation plan produced in Step 4 to `~/.claude/skill-output/$REPO/$BRANCH/plan-$TS.md`. This file is read by `/impl-ui` when invoked with `use plan` — it picks up the most recent `plan-*.md` in the branch directory.

Use the Write tool when it's available. **If you are running without a Write tool** (e.g. spawned as the read-only `Plan` agent type by `/orch-ui`), persist the same content with a quoted Bash heredoc instead — the quoted delimiter prevents `$`/backtick expansion of the plan body:

```bash
cat > ~/.claude/skill-output/$REPO/$BRANCH/plan-$TS.md <<'PLAN_EOF'
<full implementation plan markdown>
PLAN_EOF
```

## Step 6: Final User-Facing Summary

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
