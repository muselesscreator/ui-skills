---
name: impl-ui
description: Implements a UI feature or change. Loads repo learnings and any existing plan, implements the change checking standards inline, then triggers test writing. Use when building a new UI feature, modifying an existing component, or executing a /plan-ui output.
version: 1.0.0
triggers:
  explicit:
    - implement ui
    - build this feature
    - implement this change
    - impl ui
  strong_intent:
    - go ahead and build it
    - implement what we planned
    - write the code for
confidence_threshold: 75
---

# impl-ui

**Arguments**: $ARGUMENTS — task description or "use plan" to pick up from /plan-ui output

## Step 1: Load Context

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
```

Load learnings from the Obsidian vault:

```
# Always load index (reference implementations)
mcp__obsidian__read-note: vault="obsidian-vault", filename="index.md", folder="repo-learnings/{repo-name}"

# Always load gotchas
mcp__obsidian__search-vault: vault="obsidian-vault", query="tag:topic/gotcha", path="repo-learnings/{repo-name}/gotchas"
→ Read all returned notes

# Always load file placement
mcp__obsidian__read-note: vault="obsidian-vault", filename="file-structure.md", folder="repo-learnings/{repo-name}"
```

If a plan file is being used, extract the "Patterns to Follow" section and search for each pattern specifically:
```
mcp__obsidian__search-vault: vault="obsidian-vault", query="{pattern keyword}", path="repo-learnings/{repo-name}"
→ Read the specific notes returned
```

**Fallback:** If vault search returns 0 results, read flat files from `~/.claude/repo-learnings/$REPO/`.

If $ARGUMENTS contains "use plan": find the most recent plan file with `ls -t ~/.claude/skill-output/$REPO/$BRANCH/plan-*.md 2>/dev/null | head -1` and read it as the implementation spec.
If $ARGUMENTS contains a file path: read that file as the implementation spec.
Otherwise: treat $ARGUMENTS as the task description and derive the approach from learnings + live code reading.

## Step 2: Identify Reference Implementation

From `index.md`, pick the most relevant reference implementation for this task type. Read it. This is the pattern to follow.

## Step 3: Implement

Build the change. At each meaningful decision point, check against:
- The loaded ui-patterns: am I following the established data layer pattern?
- The loaded file-structure: am I placing files at the right level?
- The loaded gotchas: am I about to do something the codebase has flagged as a trap?
- The loaded standards: am I naming things consistently?

Do not deviate from established patterns without flagging it:
```
⚠ Deviation from pattern: [description]
Reason: [why this case is different]
Proceeding? [yes/no — ask if non-obvious]
```

## Step 4: Post-Implementation Check

After writing all files:

1. **Self-review against standards:**
   - No `any` or unchecked type assertions
   - No hardcoded user-facing strings (check for i18n conventions if present)
   - No business logic in presentational components
   - No direct calls to server layer from component (should go through data hooks)
   - Imports ordered correctly per project conventions

2. **Test gap check** — based on what was written:
   - List what new unit tests are needed
   - List what new E2E tests are needed
   - List what existing tests are likely affected

3. **Report:**
```
## Implementation Complete

Files created:
- {path}

Files modified:
- {path}

Standards check:
✓ Type safety
✓ Pattern compliance
✓ Import conventions
⚠ {any deviation noted}

Test work needed:
- Unit: {list}
- E2E: {list}

Next steps:
- Run /write-unit-tests {path} to write unit tests
- Run /write-e2e-tests "{flow description}" to write E2E tests
- Run /cleanup-ui to lint/type-check
- Run /validate-ui "{original task description}" to confirm behavioral correctness
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/impl-report-$TS.md` so the next agent can read what was built, what tests are needed, and what to run next.

## Step 5: Update Repo Learnings

After implementation, capture anything new or surprising. Write back to the Obsidian vault using the edit-note pattern: read the note first, merge new content, then write the updated note.

**`gotchas/` — add to the relevant note if:**
- You hit a trap that wasn't already documented
- You found a `// HACK`, `// NOTE`, or `// FIXME` comment while reading code that isn't captured yet
- A deviation from pattern was necessary and the reason is non-obvious

**`ui-patterns/` — add to the relevant note if:**
- You established a new pattern that didn't exist before
- You discovered an existing pattern that wasn't documented

**`standards/` — add to the relevant note if:**
- A tooling constraint caused a non-obvious fix

**`file-structure.md` — update if:**
- You created files in a location that wasn't previously described

Write pattern:
```
# 1. Read current note content
mcp__obsidian__read-note: vault="obsidian-vault", filename="{note}.md", folder="repo-learnings/{repo-name}/{subfolder}"

# 2. Merge new findings into content, update last-updated date in frontmatter

# 3. Write back
mcp__obsidian__edit-note: vault="obsidian-vault", filename="{note}.md", folder="repo-learnings/{repo-name}/{subfolder}", content="{full updated content}"
```

**Fallback:** If vault not available, append to `~/.claude/repo-learnings/$REPO/{filename}.md` directly.

Format new gotcha entries as:
```markdown
### {short title}
{1-2 sentence description of the trap or pattern}
**Where:** {file or feature area}
**Fix/approach:** {what to do instead}
```

If there is nothing new to add:
```
✓ No learnings updates — implementation followed established patterns.
```
