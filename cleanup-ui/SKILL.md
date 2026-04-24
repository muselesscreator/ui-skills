---
name: cleanup-ui
description: Cleanup phase for UI code on the current branch. Runs lint fix, type-check, removes dead code. Calls cleanup-unit-tests and cleanup-e2e-tests if test files are touched. Use when finishing a feature branch or fixing lint and type errors.
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
Otherwise: resolve changed files using the first source that returns results:

```bash
# 1. Committed changes ahead of main
CHANGED=$(git diff --name-only $(git merge-base HEAD main) HEAD 2>/dev/null)
# 2. Staged changes (committed ahead = 0 but staged)
[ -z "$CHANGED" ] && CHANGED=$(git diff --name-only --cached)
# 3. Unstaged + untracked changes (branch with no commits yet)
[ -z "$CHANGED" ] && CHANGED=$(git status --short | grep -v '^?? \.claude\|^?? \.cursor\|^?? thoughts/\|^?? specs/' | awk '{print $2}')
echo "$CHANGED"
```

Extract the unique package directories from the changed files to scope lint to only affected packages:

```bash
echo "$CHANGED" | sed 's|/src/.*||' | sort -u
```

## Step 2: Lint Fix

Run lint fix scoped to affected packages only (faster than full-repo):

```bash
# Build --filter flags from changed package paths
# e.g. if apps/app/src/foo.ts changed, run: pnpm --filter @eli/app lint:fix
# Fall back to pnpm lint:fix if package mapping is unclear
```

Always run lint:fix **after all manual edits are complete** — running it mid-edit may auto-format partially-added imports incorrectly.

```bash
pnpm lint:fix 2>&1 | tee /tmp/lint-output.txt
```

Read output. List what was auto-fixed and what requires manual attention.

## Step 3: Type-Check

```bash
pnpm type-check 2>&1 | tee /tmp/type-check-output.txt
```

For each type error: read the file, understand the error, apply the fix. Do not use `as` casts or `any` to silence errors — fix the underlying type issue.

**NEVER prefix unused variables with `_` to suppress errors.** If something is unused, delete it. Underscore-prefixed dead code is still dead code — it creates false impressions that the variable is intentionally unused-but-kept, which causes future bugs and confusion.

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

Remove dead code. **NEVER prefix unused variables with `_` to suppress warnings — delete them entirely.** Underscore prefixes leave dead code in place and mislead future readers into thinking the variable is intentionally unused-but-kept.

## Step 5: Check for Affected Test Files

Use the same `$CHANGED` list from Step 1 (do not re-run git diff).

**Unit tests — direct:**
```bash
echo "$CHANGED" | grep -E "\.(test|spec)\.(ts|tsx)$"
```
If unit test files are in scope, call `/cleanup-unit-tests` for them.

**E2E tests — direct:**
```bash
echo "$CHANGED" | grep -E "\.cy\.(ts|tsx)$"
```
If Cypress spec files are in scope, call `/cleanup-e2e-tests` for them.

**E2E tests — indirect (changed source may break existing specs):**
Even if no `.cy.ts` files are in the diff, check whether the changed source files are exercised by existing E2E specs:

```bash
# For each changed source file, extract its component/feature name and search E2E specs
for f in $(echo "$CHANGED" | grep -E "\.(ts|tsx)$" | grep -v test | grep -v spec); do
  name=$(basename "$f" | sed 's/\.[^.]*$//')
  grep -rl "$name" packages/e2e/tests/specs/ 2>/dev/null
done | sort -u
```

If any E2E specs reference the changed components or feature paths:
```
⚠ Existing E2E specs may be affected by source changes:
  - {spec file}: references {component/feature}
```

Read those specs and their page objects. Determine if the source changes break any existing flow:
- Selector changes (`data-key` attributes added, removed, or renamed)
- New required interactions (a step was added to a flow)
- Changed page structure (a component was moved or conditionally rendered)
- API intercept changes (new tRPC calls, changed route shapes)

If specs are broken: call `/cleanup-e2e-tests` scoped to those files.
If specs are intact but the check revealed a gap in coverage, note it in the report but do not fix it here — that's work for `/write-e2e-tests`.

## Step 6: Final Verification

```bash
pnpm type-check 2>&1 | tail -5
pnpm lint 2>&1 | tail -5
```

## Step 7: Update Repo Learnings

After cleanup, capture anything non-obvious that was encountered. Read the existing learnings:

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
LEARNINGS_DIR=~/.claude/repo-learnings/$REPO
```

**`gotchas.md` — add if:**
- A type error required a non-obvious fix that will likely recur (e.g., a generic type that must be explicitly parameterized, a discriminated union that can't be narrowed automatically)
- A lint rule forced a specific code shape that isn't obvious from the rule name alone
- You removed dead code that revealed a misuse pattern worth flagging

**`standards.md` — add if:**
- A tooling rule caused a non-trivial rewrite (add: what the rule is, what it rejected, what it accepts)
- A Prettier/ESLint combination caused a conflict that required a specific resolution

Only add entries that would save future work. Do not add entries for issues that are already documented or are self-evident from the rule name.

If nothing new to add:
```
✓ No learnings updates — cleanup followed known patterns.
```

Otherwise append to the relevant files and update `index.md` `Last analyzed` date to today.

## Step 8: Report

```
## Cleanup Complete

Lint: ✓ / ⚠ {remaining issues}
Type-check: ✓ / ⚠ {remaining issues}
Dead code removed: {list of removals}
Test cleanup: ✓ unit / ✓ e2e / skipped
Learnings updated: {list of files updated, or "none"}

Files modified: {list}
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/cleanup-ui-report-$TS.md`.
