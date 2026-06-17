---
name: validate-ui
description: Behavioral validation of a UI implementation against its stated requirements. Checks whether the feature does what was asked, identifies gaps, and flags unrequested changes. Use when verifying a completed feature matches its spec, checking for scope creep, or reviewing before opening a PR.
version: 1.0.0
triggers:
  explicit:
    - validate ui
    - validate this feature
    - does this match the spec
    - check against requirements
  strong_intent:
    - does this do what was asked
    - review the implementation against the ticket
    - are there any gaps
    - check for scope creep
  question_form:
    - does this match what was requested
    - what's missing from this implementation
    - did I implement everything
confidence_threshold: 75
---

# validate-ui

**Arguments**: $ARGUMENTS — the original feature request, task description, or ticket URL

## Step 1: Get the Spec

Parse $ARGUMENTS to find the original requirements:
- If a Linear/GitHub ticket URL: fetch its content
- If a text description: use it directly
- If "use plan": read the most recent /plan-ui output

Extract:
- What the feature is supposed to do
- What the user-facing behavior should be
- Any specific acceptance criteria stated

## Step 2: Get the Implementation

```bash
source ~/.claude/skills/lib/skill-env.sh   # sets BASE (default branch), OUT, TS
# What changed on this branch
git diff --name-only "$(git merge-base HEAD "$BASE")"..HEAD
```

Read the changed files. Understand what was actually built.

## Step 3: Behavioral Comparison

Compare spec against implementation **from the user's perspective** — not from a code quality lens. Ask:

1. **Does it do what was asked?**
   - For each stated requirement: is it implemented?
   - Are there implicit requirements (loading states, error states, empty states) that are expected but not stated?

2. **Are there gaps?**
   - Requirements that are partially implemented
   - Happy path works but edge cases are missing
   - Feature works but is not accessible (missing ARIA, keyboard navigation)

3. **Are there unrequested changes?**
   - Changes to files not related to the feature
   - Behavior changes in existing functionality
   - New dependencies or global state changes that weren't requested
   - Refactors that weren't asked for (even if they look like improvements)

## Step 4: Check for Tests

Are the required tests present?
- Unit tests for the new logic
- E2E tests for the new flow
- Existing tests updated for changed behavior

## Step 5: Output Validation Report

```
## Validation Report: {feature name}

**Verdict: COMPLETE | GAPS FOUND | OUT OF SCOPE CHANGES**

### Requirements Check

✓ {requirement}: implemented at {file:line}
✓ {requirement}: implemented at {file:line}
✗ {requirement}: NOT implemented — {what's missing}
⚠ {requirement}: partially implemented — {what's missing}

### Implicit Requirements

✓ Loading state handled
✓ Error state handled
✗ Empty state not handled — {where it's needed}

### Unrequested Changes

⚠ {file}: {description of change not in spec} — confirm intentional?

### Test Coverage

✓ Unit tests present
✗ E2E tests missing for {flow}

### Summary

{1-2 sentences on overall status and what to address before this is done}
```

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/validation-report-$TS.md"   # ← write the report to this exact path
```

Write this report to the path echoed above so the next agent can read the verdict and act on gaps or unrequested changes.
