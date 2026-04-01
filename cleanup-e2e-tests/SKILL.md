---
name: cleanup-e2e-tests
description: Fixes failing or broken E2E tests. Diagnoses failures, fixes intercepts, selectors, page objects, and wait patterns. Surfaces architectural issues for human review. Use when E2E or Cypress tests are failing after a change.
version: 1.0.0
triggers:
  explicit:
    - cleanup e2e tests
    - fix e2e tests
    - fix cypress tests
    - fix failing e2e
  strong_intent:
    - e2e tests are failing
    - cypress is failing
    - e2e broke after my change
confidence_threshold: 80
---

# cleanup-e2e-tests

**Arguments**: $ARGUMENTS (optional: path to specific test file or error description)

## Step 1: Load Test Context

Call `test-context` scoped to the E2E directory to get intercept patterns, page object conventions, and wait strategy.

## Step 2: Identify Failures

If a CI URL is provided in $ARGUMENTS: fetch CI logs using `gh run view`.
If a test file is provided: run it directly.
Otherwise: run the E2E suite and capture failures.

```bash
cd packages/e2e  # or equivalent in this repo
pnpm cypress run --spec "${TEST_FILE:-**/*.cy.ts}" --headless 2>&1 | tee /tmp/e2e-output.txt
```

## Step 3: Triage Each Failure

**Always check screenshots first:**
```bash
ls -lt cypress/screenshots/**/*.png 2>/dev/null | head -5
```
Read screenshots with the Read tool. They often reveal the real state at failure time.

**Then check error type:**

| Error | Investigation |
|---|---|
| Element not found | Compare selector in test/page-object vs actual DOM attributes |
| Timeout waiting for element | Check if network intercept is set up before the action that triggers it |
| Wrong URL after navigation | Check if page object `submit()` uses network synchronization |
| API returned unexpected data | Check if test data setup is correct; check if intercept mock matches actual response shape |
| Test passes locally, fails in CI | Check for hardcoded ports, environment-specific URLs, timing differences |

**Priority order:**
1. Is the server responding? (check health endpoint)
2. Do screenshots show a validation error or unexpected UI state?
3. Does the test selector match the actual DOM?
4. Is there a missing network intercept?

## Step 4: Apply Fixes

Fix in order of priority. Common fixes:
- **Selector mismatch:** Update the page object to use the correct `data-*` attribute
- **Missing intercept:** Add `cy.intercept()` before the action that triggers the request
- **Wrong wait:** Replace `cy.wait(N)` with `cy.wait('@alias')` or a condition assertion
- **Navigation race:** Add network synchronization to the page object's `submit()` method
- **Data mismatch:** Update test fixtures or seed data

**Rules:**
- Fix in the page object when possible — not in the individual test
- Do not add `cy.wait(N)` — find the right condition to wait for
- Do not remove assertions to make tests pass
- Add `.only` to isolate the failing test before fixing; remove it after confirming

## Step 5: Verify

```bash
# Run isolated test first
pnpm cypress run --spec "{fixed-test-file}" --headless 2>&1 | tail -30
```

Only run broader suite after isolated test passes.

## Step 6: Report

```
## E2E Test Cleanup Complete

Fixed ({count}):
- {test name}: {root cause} → {fix applied}

Surfaced for review ({count}):
- {test name}: {why it needs human decision}
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/cleanup-e2e-tests-report-$TS.md`.
