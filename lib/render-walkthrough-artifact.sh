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
#
# Also locates diff-*.patch / files-*.txt siblings of the .md file (newest by
# mtime, written by walkthrough Step 1) and embeds them so the template can
# attach real code per chapter and cross-check file coverage. Diff mode: the
# real patch is embedded as-is. Feature-tour mode (no diff-*.patch found): each
# path in files-*.txt is read fresh from the repo and wrapped as an all-context
# pseudo-diff, so the same client-side parser handles both modes uniformly.
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
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || true

TITLE=$(esc_html "$TITLE")
REPO=$(esc_html "${REPO:-—}")
BRANCH=$(esc_html "${BRANCH:-—}")

MD_DIR="$(cd "$(dirname "$MD")" && pwd)"
DIFF_PATCH=$(ls -t "$MD_DIR"/diff-*.patch 2>/dev/null | head -1) || true
FILES_TXT=$(ls -t "$MD_DIR"/files-*.txt 2>/dev/null | head -1) || true

# Body markdown is everything after the leading "# Title" line.
BODY=$(mktemp)
ESC_BODY=$(mktemp)
DIFF_SRC=$(mktemp)
ESC_DIFF_SRC=$(mktemp)
ESC_FILES=$(mktemp)
trap 'rm -f "$BODY" "$ESC_BODY" "$DIFF_SRC" "$ESC_DIFF_SRC" "$ESC_FILES"' EXIT
awk 'BEGIN{skipped=0} /^# / && skipped==0 {skipped=1; next} {print}' "$MD" > "$BODY"
sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$BODY" > "$ESC_BODY"

if [ -n "$DIFF_PATCH" ] && [ -s "$DIFF_PATCH" ]; then
  # Diff mode: embed the real patch verbatim.
  cp "$DIFF_PATCH" "$DIFF_SRC"
else
  # Feature-tour mode: synthesize an all-context pseudo-diff per file so the
  # same client-side parser (diff --git / @@ hunk / new-line tracking) works
  # for both modes. Every real line is prefixed with one space (context).
  : > "$DIFF_SRC"
  if [ -n "$FILES_TXT" ] && [ -s "$FILES_TXT" ]; then
    while IFS= read -r path; do
      [ -z "$path" ] && continue
      SRC_FILE="$path"
      [ -n "$ROOT" ] && [ -f "$ROOT/$path" ] && SRC_FILE="$ROOT/$path"
      [ -f "$SRC_FILE" ] || continue
      N=$(wc -l < "$SRC_FILE" | tr -d ' ')
      N=${N:-0}
      N=$((N + 1))
      {
        printf 'diff --git a/%s b/%s\n' "$path" "$path"
        printf '@@ -1,%s +1,%s @@\n' "$N" "$N"
        sed 's/^/ /' "$SRC_FILE"
      } >> "$DIFF_SRC"
    done < "$FILES_TXT"
  fi
fi
sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$DIFF_SRC" > "$ESC_DIFF_SRC"

if [ -n "$FILES_TXT" ] && [ -s "$FILES_TXT" ]; then
  sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$FILES_TXT" > "$ESC_FILES"
else
  : > "$ESC_FILES"
fi

awk -v title="$TITLE" -v repo="$REPO" -v branch="$BRANCH" -v date="$DATE" \
    -v bodyfile="$ESC_BODY" -v difffile="$ESC_DIFF_SRC" -v filesfile="$ESC_FILES" '
  $0 == "{{TITLE}}"           { print title;  next }
  $0 == "{{REPO}}"            { print repo;   next }
  $0 == "{{BRANCH}}"          { print branch; next }
  $0 == "{{DATE}}"            { print date;   next }
  $0 == "{{WALKTHROUGH_MD}}"  { while ((getline l < bodyfile) > 0) print l; next }
  $0 == "{{DIFF_SRC}}"        { while ((getline l < difffile) > 0) print l; next }
  $0 == "{{FILE_LIST}}"       { while ((getline l < filesfile) > 0) print l; next }
  { print }
' "$TEMPLATE" > "$OUT_HTML"

echo "$OUT_HTML"
