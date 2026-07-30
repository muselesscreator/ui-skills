#!/bin/sh
# render-plan-artifact.sh — wrap a plan-*.md into the static plan artifact page.
# Usage:
#   ~/.claude/skills/lib/render-plan-artifact.sh <plan.md> [out.html]
# Injects the plan markdown verbatim into plan-ui/plan-template.html (the
# template's inline JS renders it client-side), fills the title / repo /
# branch / date chips, and prints the generated .html path. Deterministic —
# the calling model never authors HTML.
set -e

PLAN="$1"
[ -n "$PLAN" ] && [ -f "$PLAN" ] || { echo "render-plan-artifact: plan file not found: $PLAN" >&2; exit 1; }
OUT_HTML="${2:-${PLAN%.md}.html}"
TEMPLATE="$(cd "$(dirname "$0")" && pwd)/../plan-ui/plan-template.html"
[ -f "$TEMPLATE" ] || { echo "render-plan-artifact: template not found: $TEMPLATE" >&2; exit 1; }

esc_html() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

TITLE=$(grep -m1 '^## ' "$PLAN" | sed -e 's/^## *//' -e 's/^Implementation Plan: *//') || true
[ -z "$TITLE" ] && TITLE="Implementation Plan"
REPO=$(git remote get-url origin 2>/dev/null | sed -e 's/.*\///' -e 's/\.git$//') || true
[ -z "$REPO" ] && { REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null) || true; }
BRANCH=$(git branch --show-current 2>/dev/null) || true
DATE=$(date '+%Y-%m-%d %H:%M')

TITLE=$(esc_html "$TITLE")
REPO=$(esc_html "${REPO:-—}")
BRANCH=$(esc_html "${BRANCH:-—}")

ESC_PLAN=$(mktemp)
trap 'rm -f "$ESC_PLAN"' EXIT
sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$PLAN" > "$ESC_PLAN"

awk -v title="$TITLE" -v repo="$REPO" -v branch="$BRANCH" -v date="$DATE" -v planfile="$ESC_PLAN" '
  $0 == "{{TITLE}}"   { print title;  next }
  $0 == "{{REPO}}"    { print repo;   next }
  $0 == "{{BRANCH}}"  { print branch; next }
  $0 == "{{DATE}}"    { print date;   next }
  $0 == "{{PLAN_MD}}" { while ((getline l < planfile) > 0) print l; next }
  { print }
' "$TEMPLATE" > "$OUT_HTML"

echo "$OUT_HTML"
