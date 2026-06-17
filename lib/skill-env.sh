# skill-env.sh — shared context resolution for UI skills.
# Source it (don't execute) so the vars land in the calling shell:
#   source ~/.claude/skills/lib/skill-env.sh
#
# Sets and exports:
#   ROOT           repo top-level dir (empty if not in a git repo)
#   REPO           repo name (origin basename, falls back to top-level dir name)
#   BRANCH         current branch, slashes → dashes (for use in paths)
#   BASE           default branch (origin/HEAD target, falls back to "main")
#   OUT            skill-output dir for this repo+branch (created via mkdir -p)
#   TS             timestamp-PID stamp for unique output filenames
#   LEARNINGS_DIR  flat-file learnings dir for this repo
#   SRC            "wiki" if the repo has ./wiki/, else "flat"
#
# Replaces the REPO=/BRANCH=/OUT=/TS=/mkdir boilerplate previously duplicated
# across plan-ui, impl-ui, cleanup-ui, validate-ui (and adoptable by the rest).

ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename "$ROOT" 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')

# Default branch: resolve origin/HEAD, fall back to main (fixes hardcoded "main").
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$BASE" ] && BASE=main

OUT=~/.claude/skill-output/$REPO/$BRANCH
TS=$(date +%Y%m%d-%H%M%S)-$$
LEARNINGS_DIR=~/.claude/repo-learnings/$REPO

if [ -n "$ROOT" ] && [ -d "$ROOT/wiki" ]; then SRC=wiki; else SRC=flat; fi

mkdir -p "$OUT"

export ROOT REPO BRANCH BASE OUT TS LEARNINGS_DIR SRC
