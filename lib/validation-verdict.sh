#!/usr/bin/env bash
# validation-verdict.sh — deterministic verdict + frontmatter for a validate-ui report.
#
# The arithmetic used to live as a prose paragraph in validate-ui/SKILL.md, which
# meant the most expensive model in the suite re-derived a counting rule on every
# run. It is a computation; it belongs here.
#
# Usage:
#   validation-verdict.sh <report-body.md> [--human-only-gaps N]
#   cat body.md | validation-verdict.sh - [--human-only-gaps N]
#
# Counts, from the report BODY (the sections validate-ui writes):
#   gaps        = ✗ and ⚠ lines under "Requirements Check", "Implicit Requirements",
#                 and "Test Coverage"
#   unrequested = entries under "Unrequested Changes"
#
# Verdict precedence: GAPS FOUND > OUT OF SCOPE CHANGES > COMPLETE.
# --human-only-gaps N: N of the counted gaps have no automation surface in this
#   environment. Honored ONLY when N equals the total gap count (a single fixable
#   ✗ means the normal GAPS FOUND rule still applies); then the verdict becomes
#   HUMAN VERIFICATION REQUIRED and blocked=true, so orch-ui routes it to the
#   human via BLOCKED instead of spending a remediation round on it.
#
# Prints the frontmatter block on stdout. Exit 0 always (a verdict is not an error).

set -euo pipefail

SRC="${1:-}"
[ -z "$SRC" ] && { echo "usage: validation-verdict.sh <report-body.md|-> [--human-only-gaps N]" >&2; exit 2; }
shift || true

HUMAN_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --human-only-gaps) HUMAN_ONLY="${2:-0}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ "$SRC" = "-" ]; then BODY=$(cat); else BODY=$(cat "$SRC"); fi

count() {
  printf '%s\n' "$BODY" | awk -v want="$1" '
    /^#{1,6} / {
      sec = $0
      sub(/^#+ +/, "", sec)
      inwant = (index(sec, "Requirements Check") || index(sec, "Implicit Requirements") || index(sec, "Test Coverage")) ? "gaps" : ""
      if (index(sec, "Unrequested Changes")) inwant = "unrequested"
      next
    }
    inwant != want { next }
    want == "gaps"        && /^[[:space:]]*[✗⚠]/ { n++ }
    want == "unrequested" && /^[[:space:]]*[-*⚠]/ { n++ }
    END { print n+0 }
  '
}

GAPS=$(count gaps)
UNREQ=$(count unrequested)

BLOCKED=false
if [ "$GAPS" -gt 0 ] && [ "$HUMAN_ONLY" -eq "$GAPS" ]; then
  VERDICT="HUMAN VERIFICATION REQUIRED"
  BLOCKED=true
elif [ "$GAPS" -gt 0 ]; then
  VERDICT="GAPS FOUND"
elif [ "$UNREQ" -gt 0 ]; then
  VERDICT="OUT OF SCOPE CHANGES"
else
  VERDICT="COMPLETE"
fi

cat <<EOF
---
verdict: $VERDICT
gaps: $GAPS
unrequested: $UNREQ
human_only_gaps: $HUMAN_ONLY
blocked: $BLOCKED
---
EOF
