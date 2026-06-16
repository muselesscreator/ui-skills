---
name: update-learnings
description: Re-analyzes an OSS/reference repo (or a scoped path) and updates flat-file learnings at ~/.claude/repo-learnings/{repo}/, diffing against current code state. For repos with no ./wiki/ (a work repo's wiki is refreshed via /wiki-ingest instead). Use when learnings are out of date or patterns have changed.
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
[ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)

# Work-repo guard: a repo with a ./wiki/ is refreshed via the wiki workflow, not flat learnings.
if [ -d "$(git rev-parse --show-toplevel 2>/dev/null)/wiki" ]; then
  echo "This repo has a ./wiki/ — refresh it via /wiki-ingest (it detects changed sources via SHA), not /update-learnings."
  exit 0
fi
```

Read `~/.claude/repo-learnings/$REPO/index.md` and note the `Last analyzed` date from its header.

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

For each affected file in `~/.claude/repo-learnings/$REPO/`, compare new findings to stored content using read-merge-write:

```
# 1. Read the current file (e.g. ui-patterns.md, gotchas.md)
# 2. Merge: add new patterns, remove resolved gotchas, update stale content — preserve what's still accurate
# 3. Write the merged content back, bumping `Last analyzed: {date}` in the header
```

Update `index.md`'s `Last analyzed` date last.

Report what changed:
```
Updated learnings for {repo-name}

Changes:
+ Added: [new pattern or gotcha] → [note name]
~ Updated: [pattern that changed] → [note name]
- Removed: [pattern no longer present] → [note name]

Files updated:
- ui-patterns.md
- gotchas.md
```
