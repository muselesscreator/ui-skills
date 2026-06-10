---
name: run-typecheck
description: "Pipeline cleanup skill. Runs pnpm type-check, groups errors by file with line numbers and error categories, and writes a structured report for fix-types to consume."
version: 1.0.0
internal: true
---

# run-typecheck

Pipeline cleanup skill. Called by pipeline-next — not triggered directly.

## Inputs

- No specific input file required — operates on the whole repo
- `~/.claude/skill-output/$REPO/$BRANCH/pipeline-state.json` (for state update)

## Step 1: Get Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
OUTPUT_DIR=~/.claude/skill-output/$REPO/$BRANCH
TS=$(date +%Y%m%d-%H%M%S)-$$
```

## Step 2: Run Type Check

```bash
pnpm type-check 2>&1 | tee /tmp/typecheck-output-$$.txt
```

## Step 3: Parse Output

Read `/tmp/typecheck-output-$$.txt`. For each error line, extract:

- **File path**: relative path from repo root
- **Line number**: integer
- **Column**: integer
- **Error code**: TypeScript error code in the form `TS####`
- **Error message**: the human-readable description

Then categorize each error into one of these categories:

| Category | Matches when |
|---|---|
| `missing-null-check` | Message contains "possibly undefined", "possibly null", "Object is possibly", "cannot read properties of undefined/null" |
| `type-mismatch` | Message contains "is not assignable to type", "argument of type", "cannot be assigned" |
| `missing-property` | Message contains "property X does not exist", "missing the following properties" |
| `implicit-any` | Message contains "implicitly has an 'any' type", "parameter has implicit any" |
| `unused` | Message contains "declared but never used", "is declared but its value is never read", "'X' is defined but never used" |
| `other` | Everything else |

Group errors by file. Within each file, list errors in line-number order.

## Step 4: Write Report

```bash
REPORT=$OUTPUT_DIR/typecheck-report-$TS.md
```

Write `$REPORT` with this structure:

**If zero errors:**
```
---
skill: run-typecheck
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs: []
---

## Type Check Report

Total errors: 0

All types check out.
```

**If errors exist:**
```
---
skill: run-typecheck
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs: []
---

## Type Check Report

Total errors: {N}

### Errors by File

**{relative/path/to/file.tsx}** ({N} errors)
- Line {L}: [{TS-code}] {error message} [category: {category}]
- Line {L}: [{TS-code}] {error message} [category: {category}]

**{relative/path/to/file.ts}** ({N} errors)
- Line {L}: [{TS-code}] {error message} [category: {category}]

### Summary by Category
- missing-null-check: {count}
- type-mismatch: {count}
- missing-property: {count}
- implicit-any: {count}
- unused: {count} — NOTE: delete these, do not prefix with _
- other: {count}
```

Always write the report file — even when zero errors. `fix-types` (and `pipeline-next`) reads the zero-error case to decide whether to skip the fix step.

## Step 5: Symlink and Update State

```bash
ln -sf $REPORT $OUTPUT_DIR/typecheck-report-latest.md
```

Update `pipeline-state.json` if it exists — set `phases.run-typecheck.status` to `"complete"` and `phases.run-typecheck.output` to `"typecheck-report-latest.md"`. Do not create `pipeline-state.json` if it doesn't exist; skip the update silently.

---

## Shared Patterns

**pipeline-state.json missing**: Proceed normally, skip state update.

**Error parsing failures**: If the TypeScript output format is unexpected (e.g., project references, composite builds with unusual output), do your best to parse what you can and note in the report's frontmatter: `parse_note: "Composite build output — partial parse"`.
