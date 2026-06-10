---
name: load-learnings
internal: true
description: "Pipeline context skill. Loads Obsidian vault learnings for the current repo scoped to task keywords, distills them into a single bounded context file for use by pipe-plan and pipe-impl."
version: 1.0.0
---

# load-learnings

This is an internal pipeline skill. It is not invoked directly by users — it is called by `pipeline-next` as a fresh `claude -p` process.

**Arguments**: $ARGUMENTS — task keywords, comma-separated (e.g., "components,data-fetching,user-profile")

## Inputs

None from `*-latest.md` files. Reads directly from:
- `~/.claude/skill-output/$REPO/$BRANCH/pipeline-state.json` (for task description fallback)
- Obsidian vault: `repo-learnings/{repo}/`
- Flat file fallback: `~/.claude/repo-learnings/$REPO/`

## Step 1: Get Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//') 
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
STATE_FILE=~/.claude/skill-output/$REPO/$BRANCH/pipeline-state.json
```

If $ARGUMENTS is empty, read `pipeline-state.json` to get the task description and derive keywords from it. If pipeline-state.json also does not exist, use the repo name as the only keyword.

## Step 2: Load from Obsidian Vault

Use these MCP calls. All vault calls use `vault="obsidian-vault"` and `path="repo-learnings/{repo}"`.

**Always load (regardless of keywords):**

```
mcp__obsidian__read-note: vault="obsidian-vault", filename="index.md", folder="repo-learnings/{repo}"
mcp__obsidian__search-vault: vault="obsidian-vault", query="tag:topic/gotcha", path="repo-learnings/{repo}/gotchas"
→ Read all returned notes
mcp__obsidian__read-note: vault="obsidian-vault", filename="file-structure.md", folder="repo-learnings/{repo}"
```

**Load based on keywords in $ARGUMENTS:**

- If any keyword contains "component", "form", or "design":
  ```
  mcp__obsidian__search-vault: vault="obsidian-vault", query="tag:topic/components", path="repo-learnings/{repo}/ui-patterns"
  → Read all returned notes
  ```

- If any keyword contains "data", "fetch", "api", or "hook":
  ```
  mcp__obsidian__search-vault: vault="obsidian-vault", query="tag:topic/data-fetching", path="repo-learnings/{repo}/ui-patterns"
  → Read all returned notes
  ```

- If any keyword contains "state", "store", or "zustand":
  ```
  mcp__obsidian__search-vault: vault="obsidian-vault", query="tag:topic/state-management", path="repo-learnings/{repo}/ui-patterns"
  → Read all returned notes
  ```

**One content search (always):**

```
mcp__obsidian__search-vault: vault="obsidian-vault", query="{first meaningful noun from $ARGUMENTS}", path="repo-learnings/{repo}"
→ Read any notes returned that were not already loaded above
```

**Fallback:** If ANY vault search or read returns 0 results or an error, attempt the equivalent flat file read from `~/.claude/repo-learnings/$REPO/`. For example: `index.md` → `~/.claude/repo-learnings/$REPO/index.md`, gotchas → `~/.claude/repo-learnings/$REPO/gotchas/`.

If both vault and flat files return nothing, note it at the top of the output:
```
⚠ No learnings found for {repo}. Run /learn-repo first for best results.
Proceeding without learnings context.
```

## Step 3: Distill All Loaded Content

Distill everything loaded in Step 2 into a maximum of 200 lines total. Do not copy content verbatim — synthesize and trim. The output must be machine-parseable by downstream skills (pipe-plan, pipe-impl), not just human-readable.

Structure the distilled content exactly as follows:

```
## Reference Implementations
{From index.md. List only files most relevant to the task keywords. Format: `path/to/file.tsx` — one-line purpose. Max 10 entries.}

## Patterns
{Concrete, actionable patterns from ui-patterns notes. 1-2 sentences each. Highlight any patterns specific to the loaded keywords. No verbatim copying — synthesize.}

## File Placement
{From file-structure.md. Distilled rules: where feature files go, where hooks go, where types go. Keep to the rules that affect the task.}

## Gotchas
{One line each. All gotchas loaded — do not trim these. They are small and always relevant.}

## Standards
{From standards notes if loaded. Key ESLint rules that reject common patterns (no-explicit-any, import order groups). TS strict flags that affect UI work (strictNullChecks implications, noUncheckedIndexedAccess). Keep to rules that actively block implementation.}
```

If a section has no content (e.g., no standards notes were found), write the section header with `(none loaded)` so downstream skills know it was checked.

## Step 4: Write Output File

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//') 
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write to `~/.claude/skill-output/$REPO/$BRANCH/learnings-context-$TS.md` with this exact frontmatter header at the top:

```
---
skill: load-learnings
repo: {repo}
branch: {branch}
timestamp: {ISO-8601 datetime}
inputs: []
---
```

Then the distilled content from Step 3.

If any step failed (vault unreachable, no files readable), write the output file anyway with an `## ERROR` section at the top before the distilled content, describing what failed. Never fail silently.

## Step 5: Create Symlink

```bash
ln -sf learnings-context-$TS.md ~/.claude/skill-output/$REPO/$BRANCH/learnings-context-latest.md
```

## Step 6: Update pipeline-state.json

Use python3 to update pipeline-state.json. Handle the case where the file does not exist (running standalone) by skipping this step gracefully.

```python
import json, os, sys

state_path = os.path.expanduser(f"~/.claude/skill-output/{repo}/{branch}/pipeline-state.json")
if not os.path.exists(state_path):
    sys.exit(0)  # Standalone run — skip state update

with open(state_path) as f:
    state = json.load(f)

state.setdefault("phases", {})["load-learnings"] = {
    "status": "complete",
    "output": "learnings-context-latest.md"
}

with open(state_path, "w") as f:
    json.dump(state, f, indent=2)
```
