---
name: cleanup-ui
description: Cleanup phase for UI code on the current branch. Runs lint fix, type-check, removes dead code, enforces comment standards. Calls cleanup-unit-tests and cleanup-e2e-tests if test files are touched. Use when finishing a feature branch or fixing lint and type errors.
version: 1.0.0
triggers:
  explicit:
    - cleanup ui
    - clean up this code
    - run cleanup
    - cleanup branch
  strong_intent:
    - fix lint errors
    - clean up dead code
    - remove unused imports
    - fix type errors
confidence_threshold: 80
---

# cleanup-ui

**Arguments**: $ARGUMENTS (optional: path to scope cleanup, otherwise uses branch diff)

## Step 1: Determine Scope

If a path argument is given: scope to that path.
Otherwise: get the list of changed files on the current branch.

```bash
git diff --name-only $(git merge-base HEAD main)..HEAD
```

## Step 2: Lint Fix

```bash
pnpm lint:fix 2>&1 | tee /tmp/lint-output.txt
```

Read output. List what was auto-fixed and what requires manual attention.

## Step 3: Type-Check

```bash
pnpm type-check 2>&1 | tee /tmp/type-check-output.txt
```

For each type error: read the file, understand the error, apply the fix. Do not use `as` casts or `any` to silence errors — fix the underlying type issue.

If a type error requires an architectural decision (e.g., a type is genuinely wrong at the domain level), surface it rather than guessing:
```
⚠ Type error requires decision: {file}:{line}
Issue: {description}
Options:
1. {option}
2. {option}
```

## Step 4: Dead Code Scan

For each changed file in scope:
- Unused variables (not prefixed `_` for a reason)
- Unused imports
- Commented-out code blocks
- `console.log` statements (should use the project's logger)
- Empty `catch` blocks
- `TODO` comments older than the current branch (leave new ones)

Remove dead code. Do not prefix unused variables with `_` to suppress warnings — delete them.

## Step 5: Comment Standards

For each comment in changed files:
- Comments that explain WHAT the code does: remove (code should be self-evident)
- Comments that explain WHY: keep
- `// TODO: ticket-number` format: keep
- `// HACK:`, `// NOTE:`, `// IMPORTANT:` with explanation: keep

## Step 6: Check for Test Files in Scope

```bash
git diff --name-only $(git merge-base HEAD main)..HEAD | grep -E "\.(test|spec)\.(ts|tsx)$"
```

If test files are in scope:
```
Test files detected in scope.
Running cleanup-unit-tests...
```
Call `/cleanup-unit-tests` for any unit test files.

```bash
git diff --name-only $(git merge-base HEAD main)..HEAD | grep -E "\.cy\.(ts|tsx)$"
```

If Cypress test files are in scope:
```
E2E test files detected in scope.
Running cleanup-e2e-tests...
```
Call `/cleanup-e2e-tests` for any E2E test files.

## Step 7: Final Verification

```bash
pnpm type-check 2>&1 | tail -5
pnpm lint 2>&1 | tail -5
```

## Step 8: Report

```
## Cleanup Complete

Lint: ✓ / ⚠ {remaining issues}
Type-check: ✓ / ⚠ {remaining issues}
Dead code removed: {list of removals}
Comments cleaned: {count}
Test cleanup: ✓ unit / ✓ e2e / skipped

Files modified: {list}
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/cleanup-ui-report-$TS.md`.
