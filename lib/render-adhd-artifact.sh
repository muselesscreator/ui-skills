#!/bin/sh
# render-adhd-artifact.sh — wrap a restyled adhd-format markdown file into the
# reading-page artifact.
# Usage:
#   ~/.claude/skills/lib/render-adhd-artifact.sh <restyled.md> <source-label> [fidelity-report.txt] [out.html]
# Takes the leading "# Title" line (a trailing {+} is dropped) for the page
# title, moves a leading YAML frontmatter block (a --- ... --- block before the
# title, with only blank lines or ::: blocks above it) into a collapsed "Note
# metadata" panel in the page header, injects the remaining markdown verbatim
# into adhd-format/template.html
# (the template's inline JS renders sections, ::: blocks, progress and reading
# settings client-side), fills the source label and fidelity chip from the
# adhd-fidelity.py report, inlines the embedded OpenDyslexic font CSS,
# resolves [[wiki-links]] via adhd-links.py (using source-path.txt beside the
# markdown, when Step 1 wrote one), and prints the generated .html path. Deterministic — the calling model never
# authors HTML.
set -e

MD="$1"
LABEL="$2"
REPORT="$3"
[ -n "$MD" ] && [ -f "$MD" ] || { echo "render-adhd-artifact: file not found: $MD" >&2; exit 1; }
OUT_HTML="${4:-${MD%.md}.html}"
DIR="$(cd "$(dirname "$0")" && pwd)/../adhd-format"
TEMPLATE="$DIR/template.html"
FONT_CSS="$DIR/opendyslexic.css"
[ -f "$TEMPLATE" ] || { echo "render-adhd-artifact: template not found: $TEMPLATE" >&2; exit 1; }

esc_html() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

BODY=$(mktemp)
ESC_BODY=$(mktemp)
LINKS=$(mktemp)
FM=$(mktemp)
TITLE_F=$(mktemp)
FM_HTML=$(mktemp)
trap 'rm -f "$BODY" "$ESC_BODY" "$LINKS" "$FM" "$TITLE_F" "$FM_HTML"' EXIT

# One pass: split off the frontmatter and the title line; everything else is
# the body. Frontmatter only counts before any body content, so a --- rule
# later in the document is never mistaken for it.
awk -v fmfile="$FM" -v titlefile="$TITLE_F" '
  BEGIN { fm = 0; titled = 0; blk = 0; content = 0 }
  fm == 1 { if ($0 == "---") { fm = 2; next } if ($0 !~ /^[[:space:]]*$/) print > fmfile; next }
  !titled && !blk && !content && fm == 0 && $0 == "---" { fm = 1; next }
  {
    if (!blk && $0 ~ /^:::[a-z]+[[:space:]]*$/) blk = 1
    else if (blk && $0 ~ /^:::[[:space:]]*$/) { blk = 0; print; next }
    if (!titled && !blk && $0 ~ /^# /) { titled = 1; print > titlefile; next }
    if (!blk && $0 !~ /^[[:space:]]*$/) content = 1
    print
  }
' "$MD" > "$BODY"

TITLE=$(sed -e 's/^# *//' -e 's/[[:space:]]*{+}[[:space:]]*$//' "$TITLE_F")
[ -z "$TITLE" ] && TITLE="Reading copy"
[ -z "$LABEL" ] && LABEL="Restyled document"

FIDELITY=""
if [ -n "$REPORT" ] && [ -f "$REPORT" ]; then
  if grep -q '^FIDELITY: PASS' "$REPORT"; then
    N=$(sed -n 's/^source units: \([0-9]*\).*/\1/p' "$REPORT" | head -1)
    FIDELITY="Wording verified: ${N:-all} of ${N:-all} sentences unchanged"
  else
    FIDELITY="Wording check did not pass — see the fidelity report"
  fi
fi

TITLE=$(esc_html "$TITLE")
LABEL=$(esc_html "$LABEL")
FIDELITY=$(esc_html "$FIDELITY")

sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$BODY" > "$ESC_BODY"
[ -f "$FONT_CSS" ] || FONT_CSS=/dev/null

if [ -s "$FM" ]; then
  {
    echo '<details class="frontmatter"><summary>Note metadata</summary><pre>'
    sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$FM"
    echo '</pre></details>'
  } > "$FM_HTML"
fi

SRC_PATH=""
[ -f "$(dirname "$MD")/source-path.txt" ] && SRC_PATH=$(head -1 "$(dirname "$MD")/source-path.txt")
python3 "$(dirname "$0")/adhd-links.py" "$MD" "$SRC_PATH" > "$LINKS" 2>/dev/null || echo '{}' > "$LINKS"

awk -v title="$TITLE" -v label="$LABEL" -v fidelity="$FIDELITY" \
    -v bodyfile="$ESC_BODY" -v fontfile="$FONT_CSS" -v linksfile="$LINKS" -v fmhtml="$FM_HTML" '
  $0 == "{{TITLE}}"     { print title;    next }
  $0 == "{{SOURCE}}"    { print label;    next }
  $0 == "{{FIDELITY}}"  { print fidelity; next }
  $0 == "{{FONT_CSS}}"  { while ((getline l < fontfile) > 0) print l; next }
  $0 == "{{DOC_MD}}"    { while ((getline l < bodyfile) > 0) print l; next }
  $0 == "{{WIKI_LINKS}}" { while ((getline l < linksfile) > 0) print l; next }
  $0 == "{{FRONTMATTER}}" { while ((getline l < fmhtml) > 0) print l; next }
  { print }
' "$TEMPLATE" > "$OUT_HTML"

echo "$OUT_HTML"
