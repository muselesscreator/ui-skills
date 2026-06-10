---
name: fix-types
description: "Pipeline cleanup skill. Reads the typecheck-report produced by run-typecheck, reads each erroring file, applies correct type fixes (no 'as' casts or 'any'), and writes a report of what was fixed and what needs human decision."
version: 1.0.0
internal: true
---

# fix-types

Pipeline cleanup skill. Called by pipeline-next — not triggered directly.

Skipped by `pipeline-next` if `typecheck-report-latest.md` shows zero errors.

## Inputs

- `~/.claude/skill-output/$REPO/$BRANCH/typecheck-report-latest.md` (required)
- `~/.claude/skill-output/$REPO/$BRANCH/pipeline-state.json` (for state update)

## Step 1: Get Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
OUTPUT_DIR=~/.claude/skill-output/$REPO/$BRANCH
TS=$(date +%Y%m%d-%H%M%S)-$$
```

Read `$OUTPUT_DIR/typecheck-report-latest.md`. If it does not exist, write an ERROR report (see Shared Patterns) and exit.

## Step 2: Early Exit on Zero Errors

If the typecheck report shows "Total errors: 0", write a minimal output file and exit cleanly:

```
---
skill: fix-types
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs:
  - typecheck-report-latest.md
---

## Type Fixes Report

No type errors to fix.
```

Symlink as `type-fixes-latest.md`. Update pipeline-state.json. Exit.

## Step 3: Fix Errors by File

For each file listed in the typecheck report's "Errors by File" section, working through them in the order they appear:

**a. Read the file** in full. Understand the surrounding context of each error before touching anything.

**b. Apply the fix based on category:**

**`missing-null-check`**
- Add a proper null/undefined check using optional chaining (`?.`), early return guard, or explicit `if (x == null)` check
- Do NOT add `!` non-null assertion operators — these silence the error without actually making the code safe
- Prefer the check closest to where the value is used

**`type-mismatch`**
- Fix the actual type — either the value being assigned is wrong (fix the value) or the type annotation is wrong (fix the annotation to match reality)
- Do NOT use `as TypeName` to silence the error unless `TypeName` is demonstrably correct and the cast is narrowing to a known type (e.g. the return of a well-typed fetch)
- Do NOT use `as unknown as TypeName` under any circumstances

**`missing-property`**
- Add the required property with the correct type and a meaningful value
- Do NOT wrap the type in `Partial<>` to skip providing the property
- If the property is genuinely optional at the domain level, update the type definition to mark it `?` — and update all downstream consumers if needed

**`implicit-any`**
- Add an explicit type annotation
- Do NOT use `any` as the annotation
- If the type is genuinely unknown at call time (e.g. JSON from an external source), use `unknown` and add a type guard or schema validation before using the value

**`unused`**
- DELETE the unused variable, parameter, or import entirely
- NEVER prefix with `_` to suppress the warning — this leaves dead code in place and misleads future readers into thinking the value is intentionally unused-but-kept
- If it is a function parameter that must exist for interface/callback compatibility (e.g. `(event, _context) => ...`), that is the rare legitimate case for `_` — note it explicitly in your report

**`other`**
- Apply the minimal correct fix
- If the right fix is unclear without an architectural decision, surface it (see step 3d below) rather than guessing

**c. After fixing all errors in a file**, verify the fix does not introduce a new type error in an adjacent line.

**d. If a fix requires an architectural decision** — the type is genuinely wrong at the domain level and both possible fixes have real tradeoffs — do NOT guess. Record it as needing human decision:

```
⚠ Decision needed in {file}:{line}
Error: {error message}
Options:
1. {option A} — {tradeoff}
2. {option B} — {tradeoff}
```

Do not partially apply a guess. Leave the code unchanged for that error and record it in the report.

## Step 4: Write Report

```bash
REPORT=$OUTPUT_DIR/type-fixes-$TS.md
```

Write `$REPORT` with this structure:

```
---
skill: fix-types
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs:
  - typecheck-report-latest.md
---

## Type Fixes Report

### Fixed
- `{relative/path/to/file.tsx}:{line}`: {what was fixed and how}
- `{relative/path/to/file.ts}:{line}`: {what was fixed and how}
(If nothing was auto-fixed: write "None")

### Needs Human Decision
- `{relative/path/to/file.tsx}:{line}`: {description of the decision needed, with options}
(If none: write "None")
```

## Step 5: Symlink and Update State

```bash
ln -sf $REPORT $OUTPUT_DIR/type-fixes-latest.md
```

Update `pipeline-state.json` if it exists — set `phases.fix-types.status` to `"complete"` and `phases.fix-types.output` to `"type-fixes-latest.md"`. Do not create `pipeline-state.json` if it doesn't exist; skip the update silently.

---

## Shared Patterns

**Missing input files**: If `typecheck-report-latest.md` is missing, write:
```
---
skill: fix-types
...
---

## ERROR: Missing Input

Required input not found: typecheck-report-latest.md
This file is produced by: run-typecheck

Run run-typecheck first, then re-run fix-types.
```
Symlink as `type-fixes-latest.md` and exit.

**pipeline-state.json missing**: Proceed normally, skip state update.

**The `_` prefix rule**: NEVER prefix unused variables with `_` to suppress TypeScript's "declared but never used" warning. The only legitimate use of `_` prefix is for function parameters that must exist for interface compatibility (e.g. callback signatures). In all other cases, delete the variable entirely. Underscore prefixes leave dead code in the codebase and create the false impression that the variable is intentionally unused-but-kept.
