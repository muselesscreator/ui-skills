---
name: write-unit-tests
description: Writes unit tests for a component, hook, or utility. Loads repo test patterns and writes tests covering happy path, edge cases, and error states in the project's established style. Use when adding test coverage for a component, hook, or utility function.
version: 1.0.0
triggers:
  explicit:
    - write unit tests
    - add unit tests
    - write tests for
    - unit test this
  strong_intent:
    - add tests for this component
    - test this hook
    - test coverage for
  question_form:
    - can you write tests for
    - what should I test here
confidence_threshold: 80
---

# write-unit-tests

**Arguments**: $ARGUMENTS — path to the file or component to test

## Step 1: Load Test Context

Call `test-context` with the given path argument. It writes its output to a timestamped file and echoes the full path — read that file to get structured test conventions for this repo.

## Step 2: Read the Implementation

Read the file(s) to be tested. Understand:
- What does this unit do?
- What are its inputs and outputs?
- What external dependencies does it have? (APIs, stores, router, i18n, other hooks)
- What are the meaningful states? (loading, error, empty, populated, edge cases)

## Step 3: Check for Existing Tests

```bash
# Look for existing test file
find . -name "$(basename $TARGET .ts).test.ts" -o -name "$(basename $TARGET .tsx).test.tsx" 2>/dev/null
```

If tests exist: read them. Determine what's missing, not what to replace.

## Step 4: Plan Test Coverage

Before writing, list what will be tested:

```
Test plan for {file}:

Happy path:
- [ ] {scenario}
- [ ] {scenario}

Edge cases:
- [ ] {scenario}
- [ ] {scenario}

Error states:
- [ ] {scenario}

NOT testing (implementation details / framework behavior):
- {list}
```

Get confirmation from user if test plan is non-obvious, then proceed.

## Step 5: Write Tests

Using the test context from Step 1:
- Use the established test file naming and placement
- Use the mock patterns observed in this codebase (not invented ones)
- Use the factory/fixture patterns to build test data
- Use the assertion style consistent with the project

**Rules:**
- Test behavior, not implementation details
- Each test has one clear assertion focus
- Mock everything external to the unit under test
- Do not test framework code, trivial getters, or TypeScript-enforced invariants
- Async tests use the project's established async pattern (not invented `waitFor` usage)

## Step 6: Verify

```bash
# Run just the new test file
pnpm test {test-file-path} --run 2>&1 | tail -30
```

If tests fail: diagnose and fix before reporting success.

## Step 7: Report

```
✅ Unit tests written for {file}

Coverage added:
- {scenario tested}
- {scenario tested}

Test file: {path}
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/write-unit-tests-report-$TS.md`.
