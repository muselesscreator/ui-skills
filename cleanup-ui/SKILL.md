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

Resolve the changed files and the affected packages' `--filter` flags in one call. With a path argument, pass it to restrict the set to that path:

```bash
~/.claude/skills/lib/cleanup-scope.sh "$ARGUMENTS"
```

This writes the changed-file list to `/tmp/cleanup-ui-changed.txt` and the space-separated `pnpm --filter` flags to `/tmp/cleanup-ui-filters.txt` (empty when no package mapped → use the full-repo fallback). It prints a summary; read it to know the scope. Later steps reuse these files instead of re-running git.

## Step 2: Lint Fix

Always run lint:fix **after all manual edits are complete** — running it mid-edit may auto-format partially-added imports incorrectly.

Run ESLint fix scoped to the affected packages (faster than full-repo), falling back to full-repo if no filters were resolved:

```bash
FILTERS=$(cat /tmp/cleanup-ui-filters.txt 2>/dev/null)
if [ -n "$FILTERS" ]; then pnpm $FILTERS lint:fix 2>&1 | tee /tmp/lint-output.txt
else pnpm lint:fix 2>&1 | tee /tmp/lint-output.txt; fi
```

Read output. List what was auto-fixed and what requires manual attention.

**Also run Prettier** — ESLint and Prettier are separate checks in CI (`lint` vs `lint:prettier`). ESLint's `lint:fix` does NOT run Prettier. Always run Prettier write after ESLint fix, scoped to the same packages:

```bash
FILTERS=$(cat /tmp/cleanup-ui-filters.txt 2>/dev/null)
if [ -n "$FILTERS" ]; then pnpm $FILTERS lint:prettier:fix 2>&1 | tee /tmp/prettier-output.txt
else pnpm prettier . --write 2>&1 | tail -5; fi
```

If a package has no `lint:prettier:fix` script, run `pnpm prettier <files> --write` directly on the changed files.

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

Map the changed files (from Step 1) to the tests they affect — directly and indirectly — in one call:

```bash
~/.claude/skills/lib/find-affected-tests.sh < /tmp/cleanup-ui-changed.txt
```

This prints four lists: `DIRECT_UNIT` / `DIRECT_E2E` (test files in the change set) and `INDIRECT_UNIT` / `INDIRECT_E2E` (sibling unit tests that exist on disk, and e2e specs that reference a changed source's name — found before CI does).

- If `DIRECT_UNIT` or `INDIRECT_UNIT` is non-empty: call `/cleanup-unit-tests` for those files (the indirect ones catch a source rename/reorder breaking its test).
- If `DIRECT_E2E` is non-empty: call `/cleanup-e2e-tests` for those specs.

For any `INDIRECT_E2E` specs (source changes may break an existing flow):
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

Run all three gate checks (type-check, lint, lint:prettier) and report pass/fail by exit code. Prettier is a separate CI check from ESLint and is verified explicitly:

```bash
~/.claude/skills/lib/cleanup-verify.sh
```

All three must pass (the script exits non-zero otherwise). On a failure, read the noted `/tmp/cleanup-ui-*.txt` log, fix, and re-run. Prettier failures in CI are a separate check from ESLint (`lint:prettier` Turbo task) and will not be caught by `pnpm lint` alone.

## Step 7: Update Repo Learnings

After cleanup, capture anything non-obvious that was encountered. Resolve context (sets `$LEARNINGS_DIR`, `$SRC`, etc.) with the shared helper:

```bash
source ~/.claude/skills/lib/skill-env.sh
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
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/cleanup-ui-report-$TS.md"   # ← write the report to this exact path
```

Write this report to the path echoed above.
