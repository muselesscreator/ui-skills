---
name: impl-ui
description: Implements a UI feature or change. Loads repo learnings and any existing plan, implements the change checking standards inline, then triggers test writing. Use when building a new UI feature, modifying an existing component, or executing a /plan-ui output.
version: 1.0.0
triggers:
  explicit:
    - implement ui
    - build this feature
    - implement this change
    - impl ui
  strong_intent:
    - go ahead and build it
    - implement what we planned
    - write the code for
confidence_threshold: 75
---

# impl-ui

**Arguments**: $ARGUMENTS — task description or "use plan" to pick up from /plan-ui output

## Step 1: Load Context

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
```

Load `~/.claude/repo-learnings/$REPO/ui-patterns.md`, `file-structure.md`, `gotchas.md`, `standards.md`.

If $ARGUMENTS contains "use plan": find the most recent plan file with `ls -t ~/.claude/skill-output/$REPO/$BRANCH/plan-*.md 2>/dev/null | head -1` and read it as the implementation spec.
If $ARGUMENTS contains a file path: read that file as the implementation spec.
Otherwise: treat $ARGUMENTS as the task description and derive the approach from learnings + live code reading.

## Step 2: Identify Reference Implementation

From `index.md`, pick the most relevant reference implementation for this task type. Read it. This is the pattern to follow.

## Step 3: Implement

Build the change. At each meaningful decision point, check against:
- The loaded ui-patterns: am I following the established data layer pattern?
- The loaded file-structure: am I placing files at the right level?
- The loaded gotchas: am I about to do something the codebase has flagged as a trap?
- The loaded standards: am I naming things consistently?

Do not deviate from established patterns without flagging it:
```
⚠ Deviation from pattern: [description]
Reason: [why this case is different]
Proceeding? [yes/no — ask if non-obvious]
```

## Step 4: Post-Implementation Check

After writing all files:

1. **Self-review against standards:**
   - No `any` or unchecked type assertions
   - No hardcoded user-facing strings (check for i18n conventions if present)
   - No business logic in presentational components
   - No direct calls to server layer from component (should go through data hooks)
   - Imports ordered correctly per project conventions

2. **Test gap check** — based on what was written:
   - List what new unit tests are needed
   - List what new E2E tests are needed
   - List what existing tests are likely affected

3. **Report:**
```
## Implementation Complete

Files created:
- {path}

Files modified:
- {path}

Standards check:
✓ Type safety
✓ Pattern compliance
✓ Import conventions
⚠ {any deviation noted}

Test work needed:
- Unit: {list}
- E2E: {list}

Next steps:
- Run /write-unit-tests {path} to write unit tests
- Run /write-e2e-tests "{flow description}" to write E2E tests
- Run /cleanup-ui to lint/type-check
- Run /validate-ui "{original task description}" to confirm behavioral correctness
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/impl-report-$TS.md` so the next agent can read what was built, what tests are needed, and what to run next.
