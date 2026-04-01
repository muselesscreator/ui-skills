---
name: clean-branch
description: Strips .cursor permission files and other non-code noise from the current branch before rebasing. Stages the cleanup so it doesn't interfere with the rebase. Use when preparing to rebase or when cursor files are causing merge conflicts.
version: 1.0.0
triggers:
  explicit:
    - clean branch
    - clean before rebase
    - strip cursor files
    - remove cursor permissions
  strong_intent:
    - about to rebase
    - rebase keeps conflicting
    - cursor files are causing conflicts
confidence_threshold: 85
---

# clean-branch

**Arguments**: $ARGUMENTS (optional: additional file patterns to strip)

## Step 1: Find Noise Files

```bash
# Find .cursor permission files on this branch
git diff --name-only $(git merge-base HEAD main)..HEAD | grep -E "\.cursor/"

# Find other common non-code noise
git diff --name-only $(git merge-base HEAD main)..HEAD | grep -E "\.(DS_Store|cursorrules)$"
```

Also check $ARGUMENTS for any additional patterns the user wants stripped.

## Step 2: Confirm Before Removing

Show the list of files that will be removed from the branch diff:

```
The following files will be removed from this branch's changes:

{list of files}

These changes will be staged as a cleanup commit. Proceed? (yes/no)
```

Wait for confirmation before proceeding.

## Step 3: Remove and Commit

```bash
# Restore each noise file to its state on main (effectively removing the branch's changes to it)
git checkout $(git merge-base HEAD main) -- {file1} {file2} ...

# Stage the cleanup
git add {file1} {file2} ...

# Commit
git commit -m "chore: strip .cursor permission noise before rebase"
```

## Step 4: Verify

```bash
# Confirm noise files are no longer in the branch diff
git diff --name-only $(git merge-base HEAD main)..HEAD | grep -E "\.cursor/"
```

## Step 5: Report

```
✅ Branch cleaned

Removed from branch diff:
- {file}
- {file}

Committed as: "chore: strip .cursor permission noise before rebase"

Branch is ready to rebase.
```

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write this report to `~/.claude/skill-output/$REPO/$BRANCH/clean-branch-report-$TS.md`.
