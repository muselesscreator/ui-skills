#!/usr/bin/env bash
# plan-scope-check.sh — does uncommitted work collide with THIS plan's files?
#
# The problem it solves: plan-ui, impl-ui and validate-ui each used to run their own
# unscoped `git status` and block on any dirty tree. On a shared branch that means the
# same verdict gets rediscovered from scratch at three model tiers, and unrelated
# parallel work reads as a collision. (dev-screen/home-cleanup, cycle 6895c16d: five
# blocking rounds across three steps, d001-d005, most of them disjoint from the split.)
#
# Usage:
#   plan-scope-check.sh [plan-files.txt]     # defaults to $OUT/plan-files.txt
#
# Reads the plan's own file list (one repo-relative path per line, written by plan-ui)
# and prints ONLY the dirty paths that actually intersect it. Empty output = no
# collision = do not block, however dirty the rest of the tree is.
#
# Exit codes:
#   0  no collision (or no plan file list to compare against — nothing to enforce)
#   1  collision: intersecting paths on stdout, one per line
#   2  usage/environment error
#
# Directory-prefix matching is deliberate: a plan that creates `components/cycle/`
# owns new files that appear inside it, even though those exact paths cannot be in a
# list written before they existed. That case is real — a concurrent session created
# UsageSummary.tsx inside the split's own new directory and triggered d005.

set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SELF_DIR/skill-env.sh"   # sets ROOT, OUT, ...

PLAN_FILES="${1:-$OUT/plan-files.txt}"

if [ -z "${ROOT:-}" ]; then
  echo "plan-scope-check: not inside a git repo" >&2
  exit 2
fi

# No list to compare against: this is not a collision, it is an absent plan. Callers
# fall back to their own judgment rather than treating silence as "all clear".
if [ ! -s "$PLAN_FILES" ]; then
  echo "plan-scope-check: no plan file list at $PLAN_FILES — nothing to compare" >&2
  exit 0
fi

# Dirty paths, repo-relative. Handles renames ("R  old -> new") by taking the last
# field, and quoted paths with spaces by stripping surrounding quotes.
dirty=$(git -C "$ROOT" status --porcelain \
  | sed -E 's/^.{3}//; s/^.* -> //; s/^"(.*)"$/\1/' \
  | sed '/^$/d' | sort -u)

[ -n "$dirty" ] || exit 0

# Normalize the plan list the same way: strip comments, blanks, leading ./
planned=$(sed -E 's/[[:space:]]+#.*$//; s/^\.\///' "$PLAN_FILES" \
  | sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' | sort -u)

[ -n "$planned" ] || exit 0

hits=$(
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    while IFS= read -r p; do
      [ -n "$p" ] || continue
      # exact path match, or the dirty path sits inside a planned directory
      # (whether the plan listed that directory with or without a trailing slash)
      if [[ "$d" == "$p" ]] \
         || [[ "$p" == */ && "$d" == "$p"* ]] \
         || [[ "$d" == "${p%/}"/* ]]; then
        printf '%s\n' "$d"
        break
      fi
    done <<< "$planned"
  done <<< "$dirty" | sort -u
)

if [ -n "$hits" ]; then
  printf '%s\n' "$hits"
  exit 1
fi
exit 0
