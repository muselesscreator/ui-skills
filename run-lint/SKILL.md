---
name: run-lint
description: "Pipeline cleanup skill. Determines scope from pipe-impl-report or code-snapshot, runs pnpm lint:fix scoped to affected packages, and writes a structured report of auto-fixed issues and items needing manual attention."
version: 1.0.0
internal: true
---

# run-lint

Pipeline cleanup skill. Called by pipeline-next — not triggered directly.

## Inputs

- `~/.claude/skill-output/$REPO/$BRANCH/pipe-impl-report-latest.md` (primary scope source)
- `~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-latest.md` (fallback scope source)
- `~/.claude/skill-output/$REPO/$BRANCH/pipeline-state.json` (for state update)

## Step 1: Get Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
OUTPUT_DIR=~/.claude/skill-output/$REPO/$BRANCH
```

## Step 2: Determine Scope

Read `$OUTPUT_DIR/pipe-impl-report-latest.md`. Look for a "Scope for Cleanup Skills" section and parse the "Packages changed" list from it.

If `pipe-impl-report-latest.md` does not exist, fall back to `$OUTPUT_DIR/code-snapshot-latest.md`. Extract package directories from the changed file paths listed in that file:

```bash
# Extract unique top-level package directories from changed file paths
# e.g. "apps/app/src/foo.ts" → "apps/app"
# e.g. "packages/ui/src/Button.tsx" → "packages/ui"
grep -E '^\s*-\s+\S+\.(ts|tsx|js|jsx)' code-snapshot-latest.md \
  | sed 's|.*- ||' | sed 's|/src/.*||' | sed 's|/[^/]*\.[^/]*$||' | sort -u
```

If neither file exists: write an output file with an ERROR section (see Shared Patterns) and exit.

## Step 3: Build Scoped Filter Flags

For each changed package path (e.g. `apps/app/`), determine the corresponding pnpm workspace package name by reading the `package.json` in that directory. Map to `--filter` flags:

```bash
# Example: apps/app/ → pnpm --filter @eli/app lint:fix
# Read package.json name field for each package directory
```

If the package name cannot be determined, or if packages span too many workspaces to make filtering worthwhile, run without filter (full repo lint).

## Step 4: Run Lint Fix

Run lint fix ONLY after all manual edits from prior steps are complete — never mid-edit:

```bash
TS=$(date +%Y%m%d-%H%M%S)-$$
pnpm lint:fix 2>&1 | tee /tmp/lint-output-$$.txt
```

If `--filter` flags were resolved: prepend them, e.g.:
```bash
pnpm --filter @eli/app --filter @eli/ui lint:fix 2>&1 | tee /tmp/lint-output-$$.txt
```

## Step 5: Parse Output

Read `/tmp/lint-output-$$.txt`. Separate results into three buckets:

**Auto-fixed**: Issues that `lint:fix` resolved automatically. These appear in the output as "fixed" or as problems that disappear when lint is re-run. Count them.

**Needs manual attention**: Errors that `lint:fix` could not auto-resolve. These remain in the output as `error`-level violations with file:line locations.

**Informational**: Rule violations set to `warn` level that were not auto-fixable. List these but do not treat them as blocking.

## Step 6: Write Report

```bash
TS=$(date +%Y%m%d-%H%M%S)-$$
REPORT=$OUTPUT_DIR/lint-report-$TS.md
```

Write `$REPORT` with this structure:

```
---
skill: run-lint
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs:
  - pipe-impl-report-latest.md (or code-snapshot-latest.md)
---

## Lint Report

Scope: {list of packages linted, or "full repo"}

### Auto-Fixed
{N} issues auto-fixed by lint:fix
{List key items if notable (e.g. "import order corrections in 3 files"), or write "Standard formatting corrections"}

### Needs Manual Attention
- `{file}:{line}`: {rule-name} — {what it requires}
(If none: write "None")

### Informational (warnings not auto-fixable)
- {item description}
(If none: write "None")
```

## Step 7: Symlink and Update State

```bash
ln -sf $REPORT $OUTPUT_DIR/lint-report-latest.md
```

Update `pipeline-state.json` if it exists — set `phases.run-lint.status` to `"complete"` and `phases.run-lint.output` to `"lint-report-latest.md"`. Do not create `pipeline-state.json` if it doesn't exist; skip the update silently.

---

## Shared Patterns

**Missing input files**: If required input files are missing, write an output file at `$OUTPUT_DIR/lint-report-$TS.md` with:
```
---
skill: run-lint
...
---

## ERROR: Missing Input

Required input not found: {filename}
This file is produced by: {skill name}

Run that skill first, then re-run run-lint.
```
Then symlink as `lint-report-latest.md` and exit.

**pipeline-state.json missing**: Proceed normally, skip state update.
