---
name: write-e2e-tests
description: Writes E2E tests for a feature flow or user story. Loads repo E2E conventions and writes tests using the project's established intercept, page object, and wait patterns. Use when adding end-to-end coverage for a user flow or feature.
version: 1.0.0
triggers:
  explicit:
    - write e2e tests
    - add e2e tests
    - write cypress tests
    - add end-to-end tests
  strong_intent:
    - test this flow end to end
    - add e2e coverage for
    - cypress test for this feature
  question_form:
    - can you write e2e tests for
    - what should the e2e test cover
confidence_threshold: 80
---

# write-e2e-tests

**Arguments**: $ARGUMENTS — description of the flow or feature to test

## Step 1: Load Test Context

Call `test-context` scoped to the E2E test directory. It writes its output to a timestamped file and echoes the full path — read that file to get E2E-specific conventions: intercept patterns, page object structure, wait strategy, form interaction patterns.

## Step 2: Find Relevant Existing E2E Tests

Search for existing tests that cover similar flows:

```bash
grep -r "{key terms from flow}" packages/e2e/ --include="*.cy.ts" -l 2>/dev/null | head -5
```

Read 1-2 relevant existing tests to understand the exact patterns used here.

## Step 3: Identify What to Test

Based on the flow description:
- What is the user journey? (start state → actions → end state)
- What API calls will be made? (identify intercept points)
- What navigation happens?
- What success and failure states need coverage?

## Step 4: Plan the Test

```
E2E test plan for: {flow description}

User journey:
1. {step}
2. {step}
3. {step}

API intercepts needed:
- {method} {route} → {alias}

Page objects needed:
- {existing page object} or {new page object to create}

Test cases:
- Happy path: {description}
- Error state: {description}
- Edge case: {description if relevant}
```

## Step 5: Write Tests

Following the patterns from Step 1 and Step 2:
- Place test in the correct directory per project conventions
- Use existing page objects where possible; create new ones following the same structure
- Use the project's intercept pattern (not ad-hoc `cy.wait('@alias')` without intercept setup)
- Use the project's wait strategy (network intercepts, not `cy.wait(5000)`)
- Handle navigation synchronization the way existing tests do

**Rules:**
- Always wait for specific network events, never arbitrary timeouts
- Use page objects — do not write raw `cy.get()` selectors in test files
- Intercept before triggering the action, not after
- Clean up test data if the project has a cleanup pattern

## Step 6: Verify

```bash
cd packages/e2e  # or wherever E2E tests live in this repo
# Run only the new test (add .only temporarily)
pnpm cypress run --spec "{test-file-path}" --headless 2>&1 | tail -50
```

If test fails: diagnose root cause before reporting. Check screenshots. Compare selectors against actual DOM.

Remove `.only` after confirming the test passes.

## Step 7: Report

```
✅ E2E tests written for {flow}

Coverage added:
- {test case}
- {test case}

Test file: {path}
Page objects created/modified: {list}
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/write-e2e-tests-report-$TS.md`.
