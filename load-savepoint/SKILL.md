---
name: load-savepoint
description: Loads the most recent savepoint handoff file for the current repo+branch so a fresh agent resumes where the last session left off. The read-side counterpart to /savepoint. Use at the start of a new session, after clearing/compacting context, or when told to pick up prior work.
version: 1.0.0
triggers:
  explicit:
    - load savepoint
    - resume
    - pick up where we left off
    - continue prior work
  strong_intent:
    - load the handoff
    - what was I working on
    - restore context
confidence_threshold: 70
---

# load-savepoint

**Arguments**: $ARGUMENTS — optional. A repo/branch hint, or a specific handoff filename to load instead of the latest.

## Steps

1. **Resolve path:**
   ```bash
   REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///;s/\.git//'); [ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null); [ -z "$REPO" ] && REPO=no-repo
   BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g'); [ -z "$BRANCH" ] && BRANCH=no-branch
   DIR=~/.claude/skill-output/$REPO/$BRANCH
   ```

2. **Find the savepoint** — `$DIR/handoff-latest.md`; if the symlink is missing, the newest `handoff-*.md`:
   ```bash
   ls -t "$DIR"/handoff-latest.md "$DIR"/handoff-*.md 2>/dev/null | head -1
   ```
   If none found, say so in one line (`No savepoint for {repo}/{branch}.`) and stop — don't guess.

3. **Read it** and internalize: goal, state, decisions, next steps, open questions.

4. **Reconcile with reality** (the savepoint may be stale) — one quick check that the branch hasn't moved past it:
   ```bash
   git log --oneline -5 2>/dev/null; git status --short 2>/dev/null
   ```
   If commits or working-tree state contradict the handoff's "State", note the drift.

5. **Report and proceed** — 3–5 lines: the goal, where things stand, and the immediate next step from the handoff (flagging any drift). Then continue that next step unless the user redirects.
