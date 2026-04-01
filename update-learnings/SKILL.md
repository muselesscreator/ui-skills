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

Read all files in `~/.claude/repo-learnings/$REPO/`. Note the `Last analyzed` date from `index.md`.

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

For each learnings file, compare new findings to stored content:
- Add new patterns discovered
- Remove patterns that no longer appear in the code
- Update gotchas that have been resolved (the `// HACK` comment is gone)
- Add new reference implementations if better examples now exist
- Update `Last analyzed` timestamp in `index.md`

Report what changed:
```
Updated learnings for {repo-name}

Changes:
+ Added: [new pattern or gotcha]
~ Updated: [pattern that changed]
- Removed: [pattern no longer present]

Files updated:
- ui-patterns.md
- gotchas.md
```
