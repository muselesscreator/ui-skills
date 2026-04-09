---
name: update-learnings
description: Re-analyzes the current repo (or a scoped path) and updates stored learnings at ~/.claude/repo-learnings/{repo}/. Diffs against current code state. Use when learnings are out of date, patterns have changed, or after significant refactoring.
version: 1.0.0
triggers:
  explicit:
    - update learnings
    - refresh repo learnings
    - re-analyze repo
  strong_intent:
    - learnings are out of date
    - patterns have changed
    - update what you know about this codebase
confidence_threshold: 80
---

# update-learnings

**Arguments**: $ARGUMENTS (optional: path to scope)

Re-run the learn-repo analysis and update only what has changed. Does not wipe and rewrite — diffs the current findings against stored learnings and updates sections that are stale.

## Step 1: Identify Repo and Load Existing Learnings

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
```

Read `index.md` from the Obsidian vault first:
```
mcp__obsidian__read-note: vault="obsidian-vault", filename="index.md", folder="repo-learnings/{repo-name}"
```

Note the `last-updated` date from frontmatter.

**Fallback:** If vault not available, read `~/.claude/repo-learnings/$REPO/index.md` and note the `Last analyzed` date.

## Step 2: Get Changed Files Since Last Analysis

```bash
# Files changed since the last-analyzed date
git log --since="{last-analyzed-date}" --name-only --pretty=format: | sort -u | grep -v '^$'
```

If no argument was given: analyze changes across the whole repo.
If a path argument was given: scope to that path.

## Step 3: Re-run Targeted Analysis

Run the same analysis as `learn-repo` but focused on:
1. The files that changed since last analysis
2. The areas those changes touch (if a component changed, re-analyze its feature area)

## Step 4: Diff and Update

For each affected note in the vault, compare new findings to stored content using the read-merge-edit pattern:

```
# 1. Read current note
mcp__obsidian__read-note: vault="obsidian-vault", filename="{note}.md", folder="repo-learnings/{repo-name}/{subfolder}"

# 2. Merge: add new patterns, remove resolved gotchas, update stale content

# 3. Write back with updated last-updated date in frontmatter
mcp__obsidian__edit-note: vault="obsidian-vault", filename="{note}.md", folder="repo-learnings/{repo-name}/{subfolder}", content="{full merged content}"
```

After updating vault notes, also update corresponding flat files in `~/.claude/repo-learnings/$REPO/` to keep fallback in sync.

Report what changed:
```
Updated learnings for {repo-name}

Changes:
+ Added: [new pattern or gotcha] → [note name]
~ Updated: [pattern that changed] → [note name]
- Removed: [pattern no longer present] → [note name]

Notes updated:
- ui-patterns/state-management.md
- gotchas/component-antipatterns.md
```
