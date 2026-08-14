#!/usr/bin/env bash
# spawn-tally.sh — per-run subagent launch tally from an orch-ui runlog.
#
# Reads the `SPAWN: <id> agent_type=<type>` lines orch-ui appends before each
# spawn and prints a one-line rollup, e.g. `general-purpose: 4, Plan: 1`.
# Per-run only — not cumulative across cycles.
#
# Usage: spawn-tally.sh <runlog.md>

set -euo pipefail

RUNLOG="${1:-}"
[ -z "$RUNLOG" ] && { echo "usage: spawn-tally.sh <runlog.md>" >&2; exit 2; }
[ -f "$RUNLOG" ] || { echo "(no runlog yet)"; exit 0; }

grep '^SPAWN:' "$RUNLOG" 2>/dev/null \
  | sed -E 's/.*agent_type=//' \
  | sort | uniq -c | sort -rn \
  | awk '{ printf "%s%s: %s", (NR>1 ? ", " : ""), $2, $1 } END { print (NR ? "" : "none yet") }'
