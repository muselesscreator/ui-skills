#!/usr/bin/env bash
# resolve-agent.sh — resolve a repo-tuned subagent type, falling back when absent.
#
# Global skills must work in any repo (AUTHORING.md § Global-skill hygiene), so
# they prefer a repo's tuned agent (`builder`, `codebase-analyzer`) and fall back
# to a repo-agnostic default. Detection is by `name:` frontmatter, because Claude
# Code resolves agent types by `name:` and not by filename — which keeps this
# working for oddly-named files (e.g. `codebase-analyzer..md` in incentives).
#
# Usage:
#   resolve-agent.sh builder                    # -> builder | general-purpose
#   resolve-agent.sh codebase-analyzer Explore   # -> codebase-analyzer | Explore
#
# Prints the agent type to spawn.

set -euo pipefail

PREF="${1:?usage: resolve-agent.sh <preferred> [fallback]}"
FALLBACK="${2:-general-purpose}"

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo .)

if grep -rqlE "^name:[[:space:]]*${PREF}([[:space:]]|\$)" "$ROOT/.claude/agents/" 2>/dev/null; then
  echo "$PREF"
else
  echo "$FALLBACK"
fi
