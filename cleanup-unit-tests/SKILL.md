---
name: cleanup-unit-tests
description: Fixes failing or broken unit tests. Loads repo test patterns, diagnoses failures, applies minor fixes (mocks, assertions, snapshots). Surfaces structural issues for human review. Use when unit tests are failing after a code change.
version: 1.0.0
triggers:
  explicit:
    - cleanup unit tests
    - fix unit tests
    - fix failing tests
    - fix broken tests
  strong_intent:
    - unit tests are failing
    - tests broke after my change
    - fix the test failures
confidence_threshold: 80
---

# cleanup-unit-tests

**Arguments**: $ARGUMENTS (optional: path to specific test file or package)

## Step 1: Load Test Context

Call `test-context` to get established mock patterns, factory conventions, and assertion style for this repo.

## Step 2: Run Tests and Capture Failures

```bash
# Scope to argument if provided, otherwise run all unit tests
pnpm test ${ARGUMENTS:-""} --run 2>&1 | tee /tmp/test-output.txt
```

Parse failures: group by file, extract error message and line number.

## Step 3: Categorize Each Failure

For each failing test, read the test file and the source file it tests. Categorize:

| Category | Fix approach |
|---|---|
| Mock is missing a new method/property | Add to mock — match the real interface |
| Assertion uses old value (source changed) | Update assertion to match new behavior |
| Test data factory missing new required field | Add field with sensible test default |
| Snapshot out of date | Update snapshot if change is intentional |
| Import path changed | Update import |
| Test is testing a removed behavior | Delete the test with a comment explaining why |
| Test logic is wrong for the new behavior | Rewrite the test to reflect new behavior |
| Structural issue (test architecture is wrong) | Surface for human review — do not guess |

**Do not:**
- Change test logic to make a failing test pass without understanding why it fails
- Add `// @ts-ignore` or cast to `any` to suppress errors
- Remove meaningful assertions to make tests green
- Mock a function differently than the rest of the file does it

## Step 4: Apply Fixes

Apply fixes for all categorized failures. For each fix:
- Brief comment explaining the fix is helpful if non-obvious
- Stay consistent with how other tests in the same file handle the same pattern

## Step 5: Re-run and Verify

```bash
pnpm test ${ARGUMENTS:-""} --run 2>&1 | tail -20
```

Iterate until all fixable failures are resolved.

## Step 6: Report

```
## Unit Test Cleanup Complete

Fixed ({count}):
- {test name}: {fix applied}

Surfaced for review ({count}):
- {test name}: {why it needs human decision}

Test run: {pass count} passing, {fail count} remaining
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/cleanup-unit-tests-report-$TS.md`.
