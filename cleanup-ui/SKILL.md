---
name: cleanup-ui
description: Cleanup phase for UI code on the current branch. Runs lint fix, type-check, removes dead code. Calls cleanup-unit-tests and cleanup-e2e-tests if test files are touched. Use when finishing a feature branch or fixing lint and type errors.
version: 1.2.0
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

## Step 1: Environment Preflight (hard gate — run before anything else)

```bash
~/.claude/skills/lib/env-preflight.sh
```

This checks two things that have nothing to do with the branch being cleaned up but will make it *look* like the branch is full of errors if they're wrong: (1) the Node version actually active in this shell vs. `engines.node` in the root `package.json` — a repo can pin the right version and still silently run an older one if it was never installed via asdf/nvm; (2) if the repo has a `db:generate` script (Prisma or equivalent codegen), that it runs clean — a stale/broken generated client cascades into type errors across every package that imports it.

**If this fails, STOP.** Do not proceed to Step 2 (scope), Step 4 (type-check), or edit any file. A broken toolchain is not something cleanup-ui's fix loop can resolve, and treating its symptoms as "type errors to fix" is exactly how a prior run stripped real type assertions and `eslint-disable` comments across 16 unrelated files trying to make false-positive errors go away (three separate runs, three different wrong diagnoses, before someone manually upgraded Node and reverted the damage). Skip straight to Step 9 and write the report with `Status: BLOCKED — environment`, quoting the failure line(s) from `$OUT/cleanup-preflight-fail.txt` verbatim, and naming the concrete fix (e.g. "install Node X via asdf, reshim, re-run `pnpm install` + `db:generate`"). This is not a cap-exhaustion menu — an environment failure is knowable in one preflight run, so there's nothing to iterate on; end the turn immediately.

If it passes, proceed normally — the rest of this skill can trust that a failing type-check/lint from here on reflects real code, not a broken environment.

## Step 2: Determine Scope

Resolve the changed files and the affected packages' `--filter` flags in one call. With a path argument, pass it to restrict the set to that path:

```bash
~/.claude/skills/lib/cleanup-scope.sh "$ARGUMENTS"
```

This writes the changed-file list to `$OUT/cleanup-scope-changed.txt` and the space-separated `pnpm --filter` flags to `$OUT/cleanup-scope-filters.txt` (empty when no package mapped → use the full-repo fallback), where `$OUT` is the repo+branch-scoped skill-output dir from `skill-env.sh` — so concurrent runs in other worktrees don't clobber each other. It prints a summary; read it to know the scope. Later steps reuse these files instead of re-running git.

## Step 3: Lint Fix

Always run lint:fix **after all manual edits are complete** — running it mid-edit may auto-format partially-added imports incorrectly.

Run ESLint fix scoped to the affected packages (faster than full-repo), falling back to full-repo if no filters were resolved:

```bash
source ~/.claude/skills/lib/skill-env.sh
FILTERS=$(cat "$OUT/cleanup-scope-filters.txt" 2>/dev/null)
if [ -n "$FILTERS" ]; then pnpm $FILTERS lint:fix 2>&1 | tee "$OUT/lint-output.txt"
else pnpm lint:fix 2>&1 | tee "$OUT/lint-output.txt"; fi
```

Read output. List what was auto-fixed and what requires manual attention.

**Also run Prettier** — ESLint and Prettier are separate checks in CI (`lint` vs `lint:prettier`). ESLint's `lint:fix` does NOT run Prettier. Always run Prettier write after ESLint fix, scoped to the same packages:

```bash
source ~/.claude/skills/lib/skill-env.sh
FILTERS=$(cat "$OUT/cleanup-scope-filters.txt" 2>/dev/null)
if [ -n "$FILTERS" ]; then pnpm $FILTERS lint:prettier:fix 2>&1 | tee "$OUT/prettier-output.txt"
else pnpm prettier . --write 2>&1 | tail -5; fi
```

If a package has no `lint:prettier:fix` script, run `pnpm prettier <files> --write` directly on the changed files.

## Step 4: Type-Check

Scope to the affected packages (faster, and keeps unrelated pre-existing failures out of the signal), falling back to full-repo only when Step 2 resolved no filters:

```bash
source ~/.claude/skills/lib/skill-env.sh
FILTERS=$(cat "$OUT/cleanup-scope-filters.txt" 2>/dev/null)
if [ -n "$FILTERS" ]; then pnpm $FILTERS type-check 2>&1 | tee "$OUT/type-check-output.txt"
else pnpm type-check 2>&1 | tee "$OUT/type-check-output.txt"; fi
```

**Scope discipline — read this before touching anything below.** Only fix errors in files listed in `$OUT/cleanup-scope-changed.txt` (Step 2's changed-file list). If an error surfaces in a file that is NOT in that list, it is pre-existing/out-of-scope: name it in the report as a residual, do not edit it. Editing a file outside the change set is the failure mode this rule prevents, not a broader version of success (`RATIONALE.md`).

For each in-scope type error: read the file, understand the error, apply the fix. Do not use `as` casts or `any` to silence errors — fix the underlying type issue.

**NEVER remove an existing type assertion (`as X`, non-null `!`), an `eslint-disable` comment, or any other existing suppression as the fix for an error you're seeing — even in an in-scope file.** A suppression that now *looks* redundant is usually a symptom of Step 1's preflight not being clean for that exact spot (stale build cache, partially-regenerated client, project-reference not rebuilt), not a dead guard (`RATIONALE.md`). Before removing any pre-existing assertion or disable comment: confirm Step 1 passed clean in *this* run, then state in the report why it is genuinely dead (e.g. "this branch's ternary now narrows the type upstream"). Never delete one just because the error you're chasing would go away.

**NEVER prefix unused variables with `_` to suppress errors.** If something is unused, delete it. Underscore-prefixed dead code is still dead code — it creates false impressions that the variable is intentionally unused-but-kept, which causes future bugs and confusion.

If a type error requires an architectural decision (e.g., a type is genuinely wrong at the domain level), don't guess — route it through a decision memo instead of leaving it as inline prose (AUTHORING.md § Decision memos & per-repo review heuristics):
- **Dedupe before raising**: `~/.claude/skills/lib/decide.sh list open` first; if an open memo already covers this exact error, reference its id instead of raising a near-duplicate.
- **New finding**: get the next id (`~/.claude/skills/lib/decide.sh next-id`) and Write a memo to `$OUT/decisions/d{NNN}-cleanup-ui-{slug}.md` — frontmatter `id, title, status: open, raised_by: cleanup-ui, raised_at, resolution:` (empty), then the same content as before, now persisted and tracked:
  ```
  Type error requires decision: {file}:{line}
  Issue: {description}
  Options:
  A) {option} (recommended)
  B) {option}
  ```
- **Running interactively** (AskUserQuestion available): present the memo's options via AskUserQuestion right away, then `~/.claude/skills/lib/decide.sh resolve <id>` with the chosen answer piped on stdin.
- **Running isolated** (no AskUserQuestion — e.g. spawned as an `/orch-ui` subagent): never attempt AskUserQuestion. Leave the memo `open`, cite it by id in the report, and treat this run as blocked in your final summary — a wrapping subagent should reply `STATUS: BLOCKED` and list the id(s) under `DECISIONS:`, not `PASS`/`FAIL`.

## Step 5: Dead Code Scan

For each changed file in scope (same scope-discipline rule as Step 4 — files outside `$OUT/cleanup-scope-changed.txt` are out of bounds here too):
- Unused variables (not prefixed `_` for a reason)
- Unused imports
- Commented-out code blocks
- `console.log` statements (should use the project's logger)
- Empty `catch` blocks
- `TODO` comments older than the current branch (leave new ones)

Remove dead code. **NEVER prefix unused variables with `_` to suppress warnings — delete them entirely.** Underscore prefixes leave dead code in place and mislead future readers into thinking the variable is intentionally unused-but-kept.

**Existing type assertions and `eslint-disable` comments are not in scope for this scan.** They aren't unused imports or commented-out code — don't reach for this step as a backdoor to remove them; the Step 4 rule governs those and requires more than "it looks unnecessary."

## Step 6: Check for Affected Test Files

Map the changed files (from Step 2) to the tests they affect — directly and indirectly — in one call:

```bash
source ~/.claude/skills/lib/skill-env.sh
~/.claude/skills/lib/find-affected-tests.sh < "$OUT/cleanup-scope-changed.txt"
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

## Step 7: Final Verification (capped at 3 attempts)

Run all three gate checks (type-check, lint, lint:prettier) and report pass/fail by exit code. Prettier is a separate CI check from ESLint and is verified explicitly. All three are scoped to the affected packages (falling back to full-repo only when Step 2 resolved no filters) — this is the same scoping already applied in Step 4, kept consistent here so a residual failure means "this package, in scope" rather than mixing in full-monorepo noise:

```bash
~/.claude/skills/lib/cleanup-verify.sh
```

This loop carries an integer cap of **3 attempts** (AUTHORING.md § Iteration caps). The only clean exit is applied-and-verified: a fix is made, then `cleanup-verify.sh` is re-run and shows clean — presenting a diagnosis without a clean re-run is not a clean exit, and neither is stopping mid-loop on the assumption a fix worked.

If a residual failure here is in a package outside Step 2's scope, that's the Step 4 scope-discipline rule again: name it as pre-existing/out-of-scope in the report, do not chase it into a fix. If verify keeps surfacing failures in packages that were clean at Step 4, re-run Step 1's preflight before spending another attempt on it — a failure appearing only at this late stage, in packages you didn't touch, is a stronger signal of a toolchain regression (e.g. a background process regenerated a client, a lockfile changed) than of a new bug in your own edits.

- **Attempt 1**: run the script. If it exits 0, all three are clean — done; record `attempts: 1/3` for the report.
- **On failure**: read the noted `$OUT/cleanup-verify-*.txt` log(s), fix the underlying issue (same rules as Step 4 — no `as`/`any` casts, no `_`-prefixing unused vars, no removing existing assertions/disables, no editing out-of-scope files), and re-run. Append one line per attempt to `$OUT/cleanup-verify-attempts.txt` (`attempt N: {which of type-check/lint/lint:prettier failed}`) so the count and last-pass residual survive a context reset, not just this turn's memory.
- **Attempts 2 and 3**: repeat the same fix → re-run cycle.
- **At cap** (3 attempts exhausted and at least one check still fails): stop fixing and emit the cap-exhaustion menu (AUTHORING.md § Interaction contract), naming the exact residual:
  ```
  Cleanup verify hit its cap (3/3) — still failing: {type-check | lint | lint:prettier, whichever remain}
  Last residual: {1-line summary per still-failing check, from the logs}
  A) Keep iterating — grant a new bounded attempt count and continue fixing
  B) Accept the residual and proceed — hand off with the failure noted in the report
  C) Stop here for human review
  ―) None of these — add context
  ```
  This ends the turn — never auto-pick an option, never treat silence as B. **Interactive**: ask directly via AskUserQuestion. **Isolated** (no AskUserQuestion): write the menu into the report body verbatim and treat this run as blocked in your final summary — a wrapping subagent should reply `STATUS: BLOCKED`, not `PASS`/`FAIL`.

Prettier failures in CI are a separate check from ESLint (`lint:prettier` Turbo task) and will not be caught by `pnpm lint` alone.

## Step 8: Update Repo Learnings

After cleanup, capture anything non-obvious that was encountered. Resolve context (sets `$LEARNINGS_DIR`, `$SRC`, etc.) with the shared helper:

```bash
source ~/.claude/skills/lib/skill-env.sh
```

**`gotchas.md` — add if:**
- A type error required a non-obvious fix that will likely recur (e.g., a generic type that must be explicitly parameterized, a discriminated union that can't be narrowed automatically)
- A lint rule forced a specific code shape that isn't obvious from the rule name alone
- You removed dead code that revealed a misuse pattern worth flagging
- Step 1's preflight caught a real environment issue (add: what was pinned vs. what was active, what it cascaded into) — this is exactly the kind of recurrence-risk gotcha this file exists for

**`standards.md` — add if:**
- A tooling rule caused a non-trivial rewrite (add: what the rule is, what it rejected, what it accepts)
- A Prettier/ESLint combination caused a conflict that required a specific resolution

Only add entries that would save future work. Do not add entries for issues that are already documented or are self-evident from the rule name.

If nothing new to add:
```
✓ No learnings updates — cleanup followed known patterns.
```

Otherwise append to the relevant files and update `index.md` `Last analyzed` date to today.

## Step 9: Report

```
## Cleanup Complete

Environment: ✓ preflight clean / ✗ BLOCKED — {failure line(s) from Step 1}
Lint: ✓ / ⚠ {remaining issues}
Type-check: ✓ / ⚠ {remaining issues}
Verify attempts: {n}/3 — {✓ clean | ⚠ residual: which check(s) still fail}
Out-of-scope residuals: {file: error, pre-existing — not touched | "none"}
Decisions raised: {ids from Step 4, or "none"}
Dead code removed: {list of removals}
Test cleanup: ✓ unit / ✓ e2e / skipped
Learnings updated: {list of files updated, or "none"}

Files modified: {list — must be a subset of $OUT/cleanup-scope-changed.txt}
```

If Step 1 was BLOCKED, this report is the entire output of the run — write it immediately with `Status: BLOCKED — environment` and stop; do not fill in Lint/Type-check/Verify/Dead-code fields since those steps never ran.

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/cleanup-ui-report-$TS.md"   # ← write the report to this exact path
```

Write this report to the path echoed above.

```bash
# Record this run in the session runlog, so a skill invoked BY HAND is still a
# cycle /analyze-cycle can resolve. Silently no-ops when a cycle runner already
# logs this step. Guards + rationale: lib/runlog.sh. A Step-1 environment block
# is BLOCKED here, not FAIL — that distinction is what keeps a toolchain problem
# from being read as a skill defect in the retro.
source ~/.claude/skills/lib/skill-env.sh
source ~/.claude/skills/lib/runlog.sh
runlog_append cleanup "PASS|FAIL|BLOCKED" "<cleanup-ui-report path just written, or ->" \
  "<one-sentence summary>" "<residual lint/type failures left out of scope, or ->" "<decision memo ids, or ->"
```
