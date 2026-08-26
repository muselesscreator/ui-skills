---
name: savepoint
description: Summarizes the current conversation into a handoff file so a fresh agent can resume with cleared context. Captures goal, state, decisions, key files, next steps, open questions. Use when context is long, before clearing/compacting, or when handing off to another session.
version: 1.0.0
triggers:
  explicit:
    - savepoint
    - save a savepoint
    - write a handoff
    - hand off
  strong_intent:
    - clear context
    - my context is getting long
    - summarize where we are
    - pick this up in a fresh session
confidence_threshold: 70
---

# savepoint

**Arguments**: $ARGUMENTS — optional focus note to bias the summary. If empty, summarize the whole conversation.

Write a handoff for a fresh agent with the codebase but **zero memory of this session**. No "as we discussed", no dangling pronouns — every line stands alone. Read-and-write only: no edits, lint, or commits.

Designed to run **proactively around 150k tokens of context use** (per Anthropic's context guidance), *before* auto-compact fires. The intended follow-up is `/clear` (not `/compact`) → [[load-savepoint]] in a fresh session: that resets context to near-zero and pulls back only this dense file, whereas `/compact` leaves a verbose summary resident in context for the rest of the session. Auto-compact remains the safety net if you blow past 150k without running this.

## Steps

1. **Resolve path:**
   ```bash
   REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///;s/\.git//'); [ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null); [ -z "$REPO" ] && REPO=no-repo
   BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g'); [ -z "$BRANCH" ] && BRANCH=no-branch
   ```

2. **Quick state check** (catch drift between memory and reality — don't re-read files you already know):
   ```bash
   git status --short 2>/dev/null; git log --oneline "$(git merge-base HEAD main 2>/dev/null)"..HEAD 2>/dev/null
   ```

3. **Write** `~/.claude/skill-output/$REPO/$BRANCH/handoff-$TS.md` (`TS=$(date +%Y%m%d-%H%M%S)-$$`; `mkdir -p` the dir first) with frontmatter (`skill: savepoint`, `repo`, `branch`, `timestamp`, `focus`) then this body — drop empty sections, favor density:

   ```
   # Handoff: {task title}

   ## Goal
   {1–2 sentences: current aim.}

   ## Constraints (verbatim)
   {Standing user rules and security-relevant instructions, copied WORD-FOR-WORD — never paraphrased. Files/data not to touch, operations forbidden, credential/secret handling, "always/never" directives the user stated this session. Drop the section only if there are genuinely none.}

   ## State
   {Done / in progress / not started. What's verified vs assumed (e.g. tests not run).}

   ## Decisions
   - **{decision}** — {why}. {rejected alternative, if load-bearing}. {dead ends tried, so they aren't repeated}

   ## Key Files
   - `{path:line}` — {role; what changed or still needs doing}
   {Also capture code that exists ONLY in this conversation — a proposed diff or snippet not yet written to disk. The fresh agent can re-read the repo, but cannot recover un-written work.}

   ## Next Steps
   1. {concrete, ordered, executable}

   ## Open Questions / Gotchas
   - {blocker, pending user decision, or trap discovered this session}

   ## Resume
   {One line: which file/command to start with.}
   ```

4. **Point latest + report:**
   ```bash
   ln -sf handoff-$TS.md ~/.claude/skill-output/$REPO/$BRANCH/handoff-latest.md
   ```
   Reply with the path and the resume line: `Read ~/.claude/skill-output/{repo}/{branch}/handoff-latest.md and continue.` Don't clear context yourself — that's the user's call.
