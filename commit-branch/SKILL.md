---
name: commit-branch
description: Stages and commits the current branch's changes with a generated Conventional Commits message derived from the actual diff. Commit only — does not push or open a PR. Writes a short commit report. Use as the commit step of a workflow, or whenever you want a clean, well-described commit of the working tree.
version: 1.0.0
---

# commit-branch

**Arguments**: $ARGUMENTS (optional: a commit subject to use verbatim, or a strong hint).

Commit-only. No push, no PR.

## Step 1: Context

```bash
source ~/.claude/skills/lib/skill-env.sh   # sets REPO, BRANCH, BASE, OUT (mkdir -p'd), TS
```

Never reassign `OUT` afterwards. A cycle runner may point `$OUT` at the cycle's own artifacts dir, and overwriting it drops the commit report somewhere the rest of the cycle won't look.

## Step 2: Inspect what will be committed

```bash
git status --short
git diff --stat
```

If the tree is clean (nothing to stage or commit): write a report noting "nothing to commit" and stop — never create an empty commit.

Do not commit noise: if `.cursor/` permission files or other non-code junk are untracked, leave them unstaged. Stage source changes intentionally.

## Step 3: Compose the message

Read the real diff (`git diff` and `git diff --cached`) to write an honest message — do not infer from filenames alone.

- **Subject**: Conventional Commits style, ≤ 72 chars — `type(scope): summary` (types: feat, fix, refactor, test, chore, docs, style, perf).
- **Body**: 1–4 bullet lines on what changed and why, only if they add signal.
- If `$ARGUMENTS` is given, use it as the subject (or strong hint) instead of generating one.
- Do not add footer/advertising lines unless the repo's existing history already uses them.

## Step 4: Stage and commit

```bash
# Stage source changes; exclude local tooling noise. Adjust if this repo
# legitimately tracks .claude/.cursor.
git add -A -- . ':(exclude).cursor' ':(exclude).claude'
git commit -m "<subject>" -m "<body>"
```

Use multiple `-m` (or a HEREDOC) to keep the message intact. **Do not push.**

## Step 5: Report

Write `$OUT/commit-report-$TS.md` with:
- the commit hash (`git rev-parse --short HEAD`)
- the subject line
- files committed (`git show --stat --oneline HEAD`)
- anything intentionally left unstaged

Finish by printing the hash + subject.
