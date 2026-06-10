---
name: scan-dead-code
description: "Pipeline cleanup skill. Scans changed files for dead code (unused variables, unused imports, console.logs, empty catches, commented-out code blocks) and removes them. Works from the file list in pipe-impl-report or code-snapshot."
version: 1.0.0
internal: true
---

# scan-dead-code

Pipeline cleanup skill. Called by pipeline-next — not triggered directly.

## Inputs

- `~/.claude/skill-output/$REPO/$BRANCH/pipe-impl-report-latest.md` (primary source file list)
- `~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-latest.md` (fallback source file list)
- `~/.claude/skill-output/$REPO/$BRANCH/learnings-context-latest.md` (optional — check for project logger)
- `~/.claude/skill-output/$REPO/$BRANCH/pipeline-state.json` (for state update)

## Step 1: Get Repo, Branch, and File List

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
OUTPUT_DIR=~/.claude/skill-output/$REPO/$BRANCH
TS=$(date +%Y%m%d-%H%M%S)-$$
```

Read `$OUTPUT_DIR/pipe-impl-report-latest.md`. Parse the "Source files changed" list from the "Scope for Cleanup Skills" section.

If `pipe-impl-report-latest.md` does not exist, fall back to `$OUTPUT_DIR/code-snapshot-latest.md` and extract the file paths listed there.

If neither file exists: write an ERROR report (see Shared Patterns) and exit.

Filter to source files only — skip test files (`.test.ts`, `.test.tsx`, `.spec.ts`, `.spec.tsx`, `.cy.ts`, `.cy.tsx`). Dead code in test files is cleaned by `cleanup-unit-tests` and `cleanup-e2e-tests`.

If `learnings-context-latest.md` exists, read it briefly to identify whether the project uses a custom logger (e.g. `logger.info`, `log.warn`, `createLogger`). This tells you what `console.*` calls should be replaced with.

## Step 2: Scan and Clean Each File

For each source file in the list, read the full file and check for each of the following dead code patterns:

---

**Unused imports**

Imports not referenced anywhere in the file body. This includes:
- Named imports: `import { Foo } from './foo'` where `Foo` never appears in the file
- Default imports: `import Foo from './foo'` where `Foo` never appears
- Namespace imports: `import * as Foo from './foo'` where `Foo` never appears
- Type-only imports that the file doesn't use

Remove the unused import lines entirely. If a named import has both used and unused members, remove only the unused members: `import { Foo, Bar }` → `import { Foo }` (if `Bar` is unused).

---

**Unused variables**

Variables that are declared but never read. This applies to `const`, `let`, `var` declarations and destructured values.

NEVER prefix unused variables with `_` to suppress warnings. Delete them entirely. Underscore prefixes leave dead code in the codebase and create the false impression that the variable is intentionally unused-but-kept, which misleads future readers and causes confusion.

The one legitimate exception for `_` prefix is function parameters that must exist for interface or callback compatibility (e.g. `(req, _res, next) => ...` where the signature is mandated). If you encounter this, leave it and do not flag it.

---

**console.log / console.warn / console.error**

These should use the project's logger instead of writing directly to stdout/stderr.

- If the project has an identified logger (from `learnings-context-latest.md` or visible in the file's own imports): replace `console.log(...)` with the equivalent logger call
- If no project logger can be identified: flag it in the report under "Flagged" — do not remove it (removing a log without a replacement is worse than leaving it)
- Exception: `console.error` in top-level error boundaries or CLI scripts may be intentional — use judgment and flag rather than remove if context is ambiguous

---

**Commented-out code blocks**

Multi-line blocks that have been commented out. Characteristics:
- Multiple consecutive lines starting with `//` or wrapped in `/* */`
- The content looks like executable code (imports, variable declarations, function calls, JSX)
- Not an explanatory comment or documentation

Remove if clearly dead (the original code has been replaced and the commented version serves no reference purpose). Do not remove if:
- The comment contains a TODO or FIXME referencing an active issue
- The comment appears to be a reference implementation or debugging aid with a clear label
- Context makes it ambiguous whether it is intentional

For ambiguous cases: flag in the report under "Flagged" rather than auto-removing.

---

**Empty catch blocks**

`catch` blocks with no body or only a comment:

```typescript
try {
  ...
} catch (e) {}
// or
} catch (e) {
  // TODO
}
```

If the catch is genuinely intentional (e.g. optional feature check that is expected to fail): add a comment explaining why the error is swallowed: `// intentional: feature not available in all environments`

If the intent is unclear: add a TODO comment at minimum: `// TODO: handle or log this error`

Do not leave a completely empty catch block.

---

**TODO comments older than the current branch**

For each `// TODO` or `// FIXME` comment found, check if it predates the branch:

```bash
git log --oneline --since="$(git log --format=%ci $(git merge-base HEAD main) | head -1)" -- {file} | head -5
```

If a TODO was present before the branch started (i.e., it appears in the base commit for this file), it is pre-existing — leave it alone.

If a TODO was added on the current branch, leave it — it is active work.

Only flag TODOs that appear older than the branch if they are clearly stale (e.g. reference a ticket that is already closed, or describe work that has already been done elsewhere in the file).

---

## Step 3: Write Report

```bash
REPORT=$OUTPUT_DIR/dead-code-report-$TS.md
```

Write `$REPORT` with this structure:

```
---
skill: scan-dead-code
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs:
  - pipe-impl-report-latest.md (or code-snapshot-latest.md)
---

## Dead Code Report

### Removed
- `{relative/path/to/file.tsx}`: {description of what was removed} (e.g. "removed 2 unused imports: Foo, Bar; removed console.log on line 42")
- `{relative/path/to/file.ts}`: {description}
(If nothing was auto-removed: write "None found")

### Flagged (not auto-removed)
- `{relative/path/to/file.tsx}:{line}`: {what it is and why it wasn't auto-removed}
(If none: write "None")
```

## Step 4: Symlink and Update State

```bash
ln -sf $REPORT $OUTPUT_DIR/dead-code-report-latest.md
```

Update `pipeline-state.json` if it exists — set `phases.scan-dead-code.status` to `"complete"` and `phases.scan-dead-code.output` to `"dead-code-report-latest.md"`. Do not create `pipeline-state.json` if it doesn't exist; skip the update silently.

---

## Shared Patterns

**Missing input files**: If both `pipe-impl-report-latest.md` and `code-snapshot-latest.md` are missing, write:
```
---
skill: scan-dead-code
...
---

## ERROR: Missing Input

Required input not found: pipe-impl-report-latest.md and code-snapshot-latest.md
These files are produced by: pipe-impl (or snapshot-branch)

Run one of those skills first, then re-run scan-dead-code.
```
Symlink as `dead-code-report-latest.md` and exit.

**pipeline-state.json missing**: Proceed normally, skip state update.

**The `_` prefix rule**: NEVER prefix unused variables with `_` to suppress lint or TypeScript warnings. This is explicitly prohibited. The only accepted resolution for an unused variable is to delete it. If you find existing `_`-prefixed variables that are genuinely unused (not interface-mandated parameters), remove them and record the removal in the report.
