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

## Step 1: Load Repo Learnings

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
```

Read `~/.claude/repo-learnings/$REPO/index.md`. If it doesn't exist:
```
⚠ No learnings found for {repo-name}. Run /learn-repo first for best results.
Proceeding with live analysis only — this will be slower.
```

If learnings exist, read:
- `ui-patterns.md`
- `file-structure.md`
- `gotchas.md`
- `standards.md`

## Step 2: Understand the Task

Parse the task description from $ARGUMENTS. Identify:
- Is this a new feature, a modification, a refactor, or a bug fix?
- What parts of the UI are involved? (new view, new component, new form, state change, style update)
- Are there existing files that need to be read for context?

## Step 3: Read Relevant Existing Code

Based on the task, find and read:
- The most relevant existing feature for pattern reference (use reference implementations from `index.md` if relevant)
- The files that will be modified
- Any parent views or layouts that affect where this fits

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

### Test Impact Analysis

**Unit tests:**
- Existing tests affected: {list or "none"}
- New tests needed: {list with what each should cover}

**E2E tests:**
- Existing E2E flows affected: {list or "none"}
- New E2E coverage needed: {list with what flows to cover}

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
