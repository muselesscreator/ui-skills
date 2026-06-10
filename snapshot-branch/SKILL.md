---
name: snapshot-branch
internal: true
description: "Pipeline context skill. Identifies files changed on the current branch, reads each one, and produces a per-file summary describing its role and what's changing. Used by pipe-plan, analyze-test-impact, and analyze-e2e-impact."
version: 1.0.0
---

# snapshot-branch

This is an internal pipeline skill. It is not invoked directly by users — it is called by `pipeline-next` as a fresh `claude -p` process.

**Arguments**: $ARGUMENTS — none expected.

## Inputs

None from `*-latest.md` files. Reads directly from git and source files.

## Step 1: Get Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//') 
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
```

## Step 2: Find Changed Files

Use the first source that returns results, in order:

```bash
# 1. Files changed on this branch vs main (committed changes)
CHANGED=$(git diff --name-only $(git merge-base HEAD main 2>/dev/null) HEAD 2>/dev/null)

# 2. Staged changes (if no committed branch diff)
[ -z "$CHANGED" ] && CHANGED=$(git diff --name-only --cached 2>/dev/null)

# 3. All tracked modifications + new files (excluding .claude and .cursor noise)
[ -z "$CHANGED" ] && CHANGED=$(git status --short 2>/dev/null | grep -v '^?? \.claude\|^?? \.cursor' | awk '{print $2}')
```

If all three return empty, write the output file with a note: "No changed files detected. Repo may be clean or on main."

## Step 3: Filter to Source Files

From the raw changed file list, exclude:
- Lock files: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `*.lock`
- Generated files: `*.generated.ts`, `*.generated.tsx`, `__generated__/`, `dist/`, `build/`, `.next/`
- Documentation: `*.md` files (unless the task is specifically about documentation — use judgment)
- Config files unlikely to affect behavior: `.gitignore`, `.editorconfig`, `*.prettierrc` (keep tsconfig and eslint configs — they affect how code must be written)
- Binary files: images, fonts, etc.

After filtering, group remaining files by package or feature area. Derive the group label from the file path:
- Files in `packages/web/src/features/user-profile/` → group "user-profile"
- Files in `packages/api/src/handlers/` → group "api/handlers"
- Files in `apps/mobile/src/screens/` → group "mobile/screens"
- Files at root → group "root"

## Step 4: Summarize Each Changed Source File

For each file in the filtered list:

1. Read the full file content.
2. Find its git diff if it is committed:
   ```bash
   git diff $(git merge-base HEAD main 2>/dev/null) HEAD -- {file} 2>/dev/null
   # OR for staged:
   git diff --cached -- {file} 2>/dev/null
   ```
3. Identify key imports (what it imports from) and, if feasible, what imports it (a quick grep):
   ```bash
   grep -r "from '.*{basename-without-ext}'" . --include="*.ts" --include="*.tsx" -l 2>/dev/null | grep -v node_modules | head -5
   ```
4. Write a one-paragraph summary covering:
   - What this file does (its role in the system — be specific, not generic)
   - What appears to be changing and why (based on the diff, or "new file" if untracked)
   - What it imports from (key external deps, internal libs, sibling modules)
   - What imports it (up to 5 files — if more, note "and N others")

Keep each paragraph to 4-6 sentences. Do not restate the file path — it is the section header.

## Step 5: Write Output File

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//') 
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write to `~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-$TS.md` with this exact frontmatter header:

```
---
skill: snapshot-branch
repo: {repo}
branch: {branch}
timestamp: {ISO-8601 datetime}
inputs: []
---
```

Then the content in this exact format:

```
## Changed Files Summary

**{package or feature area}**

### {relative/path/to/file.tsx}
{one paragraph: role + what's changing + key imports from + key imports by}

### {relative/path/to/file.ts}
{one paragraph}

**{next package or feature area}**

### {relative/path/to/file.ts}
{one paragraph}

## File List (for downstream skills)
- {relative/path/to/file.tsx}
- {relative/path/to/file.ts}
- {relative/path/to/file.ts}
```

The "File List" section must be a clean, flat list of all changed source files — one per line, no grouping, no extra text. This section is parsed by `analyze-test-impact` and `analyze-e2e-impact` — keep it machine-readable.

If any file read failed (file too large, permission error, deleted file), write a one-line note in place of the paragraph: `[Could not read: {reason}]`. Never fail silently.

If the overall step failed badly (e.g., not a git repo), write the output file with an `## ERROR` section at the top describing what failed, then the partial content.

## Step 6: Create Symlink

```bash
ln -sf code-snapshot-$TS.md ~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-latest.md
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

state.setdefault("phases", {})["snapshot-branch"] = {
    "status": "complete",
    "output": "code-snapshot-latest.md"
}

with open(state_path, "w") as f:
    json.dump(state, f, indent=2)
```
