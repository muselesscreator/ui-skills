#!/bin/sh
# render-walkthrough-artifact.sh — wrap a walkthrough-*.md into the static
# walkthrough timeline artifact page.
# Usage:
#   ~/.claude/skills/lib/render-walkthrough-artifact.sh <walkthrough.md> [out.html]
# Extracts the leading "# Title" line for the header, injects the remaining
# markdown verbatim into walkthrough/walkthrough-template.html (the template's
# inline JS renders it client-side into a TL;DR box, a cast-of-changes table,
# and a numbered timeline), fills the repo/branch/date chips, and prints the
# generated .html path. Deterministic — the calling model never authors HTML.
set -e

MD="$1"
[ -n "$MD" ] && [ -f "$MD" ] || { echo "render-walkthrough-artifact: file not found: $MD" >&2; exit 1; }
OUT_HTML="${2:-${MD%.md}.html}"
TEMPLATE="$(cd "$(dirname "$0")" && pwd)/../walkthrough/walkthrough-template.html"
[ -f "$TEMPLATE" ] || { echo "render-walkthrough-artifact: template not found: $TEMPLATE" >&2; exit 1; }

esc_html() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

TITLE=$(grep -m1 '^# ' "$MD" | sed -e 's/^# *//') || true
[ -z "$TITLE" ] && TITLE="Code Walkthrough"
REPO=$(git remote get-url origin 2>/dev/null | sed -e 's/.*\///' -e 's/\.git$//') || true
[ -z "$REPO" ] && { REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null) || true; }
BRANCH=$(git branch --show-current 2>/dev/null) || true
DATE=$(date '+%Y-%m-%d %H:%M')

TITLE=$(esc_html "$TITLE")
REPO=$(esc_html "${REPO:-—}")
BRANCH=$(esc_html "${BRANCH:-—}")

# Body markdown is everything after the leading "# Title" line.
BODY=$(mktemp)
ESC_BODY=$(mktemp)
trap 'rm -f "$BODY" "$ESC_BODY"' EXIT
awk 'BEGIN{skipped=0} /^# / && skipped==0 {skipped=1; next} {print}' "$MD" > "$BODY"
sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$BODY" > "$ESC_BODY"

awk -v title="$TITLE" -v repo="$REPO" -v branch="$BRANCH" -v date="$DATE" -v bodyfile="$ESC_BODY" '
  $0 == "{{TITLE}}"           { print title;  next }
  $0 == "{{REPO}}"            { print repo;   next }
  $0 == "{{BRANCH}}"          { print branch; next }
  $0 == "{{DATE}}"            { print date;   next }
  $0 == "{{WALKTHROUGH_MD}}"  { while ((getline l < bodyfile) > 0) print l; next }
  { print }
' "$TEMPLATE" > "$OUT_HTML"

echo "$OUT_HTML"
