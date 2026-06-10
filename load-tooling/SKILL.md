---
name: load-tooling
internal: true
description: "Pipeline context skill. Reads TypeScript, ESLint, and Prettier config from the repo once per branch and writes a distilled tooling constraints file. Downstream skills read this instead of re-parsing config files."
version: 1.0.0
---

# load-tooling

This is an internal pipeline skill. It is not invoked directly by users — it is called by `pipeline-next` as a fresh `claude -p` process.

**Arguments**: $ARGUMENTS — none expected. Reads directly from the repo.

**Note**: `pipeline-next` skips this skill if `tooling-context-latest.md` already exists and no tsconfig/eslint files have changed since it was written.

## Inputs

None from `*-latest.md` files. Reads config files directly from the repo.

## Step 1: Get Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//') 
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
```

## Step 2: Find and Read TypeScript Config

```bash
find . -name "tsconfig*.json" -not -path "*/node_modules/*" | head -10
```

Read the root `tsconfig.json` and any app-level tsconfig (e.g., `tsconfig.app.json`, `apps/*/tsconfig.json`). Prefer app-level over root when they differ.

Extract and enumerate exactly which strict flags are active. Do not just note `"strict": true` — list what it enables:
- `strictNullChecks` — requires explicit null/undefined handling
- `noImplicitAny` — variables must have a type
- `strictFunctionTypes` — stricter function type checking
- `strictBindCallApply` — type-checks `.bind`, `.call`, `.apply`
- `strictPropertyInitialization` — class properties must be initialized
- `noImplicitThis` — `this` must be typed
- `alwaysStrict` — emits `"use strict"`

Also extract:
- `paths` aliases (list each alias and what it maps to, e.g., `@/components → ./src/components`)
- `lib` and `target` if they constrain API usage (e.g., `"lib": ["ES2020"]` means no ES2022+ APIs)
- Any flags in `compilerOptions` that are commonly triggered during feature work: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`, `noFallthroughCasesInSwitch`

## Step 3: Find and Read ESLint Config

```bash
find . -maxdepth 3 \( -name ".eslintrc*" -o -name "eslint.config.*" \) | grep -v node_modules | head -5
```

Read all returned config files. Extract:

**Import ordering rules** — identify the exact group order enforced by `import/order` or `perfectionist/sort-imports` or similar. List the groups in order (e.g., `builtin → external → internal → parent → sibling → index`).

**Rules set to "error" that commonly affect UI feature work:**
- `@typescript-eslint/no-explicit-any` — what it rejects, what to use instead
- `@typescript-eslint/no-non-null-assertion` — forbids `!` non-null assertions
- `no-restricted-imports` — list any restricted paths or patterns
- `jsx-a11y/*` rules — any accessibility rules that block common patterns
- `react-hooks/exhaustive-deps` — if enforced
- `import/no-cycle` or cycle detection rules if present
- Any repo-specific custom rules

**Scan source files for common eslint-disable comments** — these indicate rules that are hard to satisfy in practice:
```bash
grep -r "eslint-disable" . --include="*.ts" --include="*.tsx" -l 2>/dev/null | grep -v node_modules | head -10
```
Read a sample of these files. Note which rules get disabled and in what context — this signals where the rules are painful and worth calling out.

If no ESLint config is found: write "No ESLint config found."

## Step 4: Find and Read Prettier Config

```bash
find . -maxdepth 3 \( -name ".prettierrc*" -o -name "prettier.config.*" \) | grep -v node_modules | head -3
```

Read the config if found. Note only non-default settings (e.g., `printWidth: 100`, `singleQuote: true`, `trailingComma: "all"`, `tabWidth: 4`).

If no config is found: write "Prettier defaults apply."

## Step 5: Write Output File

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//') 
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write to `~/.claude/skill-output/$REPO/$BRANCH/tooling-context-$TS.md` with this exact frontmatter header:

```
---
skill: load-tooling
repo: {repo}
branch: {branch}
timestamp: {ISO-8601 datetime}
inputs: []
---
```

Then the structured content in this exact format:

```
## TypeScript
Strict flags active: [comma-separated list, e.g., strictNullChecks, noImplicitAny, strictFunctionTypes]
Path aliases: [list each alias → target, or "none"]
Target/lib constraints: [e.g., "target: ES2020 — no ES2022+ APIs" or "none"]
Additional flags: [noUncheckedIndexedAccess, exactOptionalPropertyTypes, etc. if active — or "none"]

## ESLint
Import order: [ordered group list, e.g., builtin → external → internal (@/) → parent → sibling]
Error rules affecting UI work:
- no-explicit-any: [what it rejects, what to use instead]
- no-non-null-assertion: [yes/no — describe impact]
- no-restricted-imports: [list restricted paths/patterns or "none"]
- jsx-a11y: [relevant rules or "not enforced"]
- react-hooks/exhaustive-deps: [enforced/not enforced]
- Commonly disabled rules: [rules seen in eslint-disable comments with context]

## Prettier
[non-default settings listed, or "Defaults apply"]
```

If any step failed (config file unreadable, parse error), write the output file anyway with an `## ERROR` section at the top describing what failed. Never fail silently.

## Step 6: Create Symlink

```bash
ln -sf tooling-context-$TS.md ~/.claude/skill-output/$REPO/$BRANCH/tooling-context-latest.md
```

## Step 7: Update pipeline-state.json

Use python3 to update pipeline-state.json. Handle the case where the file does not exist (running standalone) by skipping gracefully.

```python
import json, os, sys

state_path = os.path.expanduser(f"~/.claude/skill-output/{repo}/{branch}/pipeline-state.json")
if not os.path.exists(state_path):
    sys.exit(0)  # Standalone run — skip state update

with open(state_path) as f:
    state = json.load(f)

state.setdefault("phases", {})["load-tooling"] = {
    "status": "complete",
    "output": "tooling-context-latest.md"
}

with open(state_path, "w") as f:
    json.dump(state, f, indent=2)
```
