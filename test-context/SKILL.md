---
name: test-context
description: Internal sub-skill. Loads test pattern learnings for the current repo and scans local test files to return structured test context used by write and cleanup test skills. Use when called by write-unit-tests, write-e2e-tests, cleanup-unit-tests, or cleanup-e2e-tests.
version: 1.0.0
internal: true
---

# test-context

This is an internal sub-skill called by write-unit-tests, write-e2e-tests, cleanup-unit-tests, and cleanup-e2e-tests. It is not invoked directly by users.

**Arguments**: $ARGUMENTS (optional: path to scope the context)

## Purpose

Load stored test pattern learnings for the current repo and augment them with a live scan of nearby test files. Return a structured context block that the calling skill uses to write or fix tests in the correct style.

## Step 1: Identify Repo

```bash
# Get repo name from git remote
git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//'
# Fallback: read name from package.json at root
```

## Step 2: Load Stored Learnings

Load test pattern learnings. Source depends on the repo:
```bash
[ -d "$(git rev-parse --show-toplevel 2>/dev/null)/wiki" ] && SRC=wiki || SRC=flat
```

**If SRC=wiki (work repo — canonical):** query QMD scoped to `collections: ["wiki"]` with `intent` for test conventions (unit + E2E patterns, mocks, fixtures, wait strategy) and test-related gotchas. Read top `qmd://wiki/...` hits.

**If SRC=flat (OSS/reference repo):** read `~/.claude/repo-learnings/$REPO/test-patterns.md` and the test-related entries in `gotchas.md`.

If neither source yields anything:
```
⚠ No test learnings found for this repo. For a work repo run /wiki-index; for an OSS checkout run /learn-repo.
Proceeding with live scan only.
```

## Step 3: Live Scan

If a path argument is provided, scan test files near that path. Otherwise scan the closest `__tests__`, `test/`, or `*.test.ts` / `*.spec.ts` files relative to the current working directory.

Capture and summarize:
- Test file naming conventions (`*.test.ts`, `*.spec.ts`, co-located vs `__tests__/`)
- Import patterns (what test utilities, render helpers, matchers are used)
- Mock patterns (how external dependencies, stores, routers are mocked)
- Factory/fixture patterns (how test data is built)
- Assertion style (what matchers, how async is handled)
- For E2E: intercept patterns, page object structure, wait conventions

## Step 4: Return Context

Output a structured markdown block:

```
## Test Context for {repo-name}

### File Conventions
[naming, placement]

### Mock Patterns
[how stores, APIs, routers are mocked — with code examples from actual files]

### Factory Patterns
[how test data is built — with examples]

### Assertion Style
[async patterns, common matchers]

### E2E Conventions (if applicable)
[intercept patterns, page objects, wait strategy]

### Known Gotchas
[from test-patterns.md — things that have burned people before]
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this context block to `~/.claude/skill-output/$REPO/$BRANCH/test-context-$TS.md`. Echo the full output path so the calling skill can read the exact file rather than guessing.
