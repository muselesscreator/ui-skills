#!/usr/bin/env bash
# decide.sh — decision-memo plumbing: ids and status transitions ONLY.
#
# Memo bodies (context, lettered options, recommendation) are authored by
# skills themselves via Write/heredoc. This script never writes memo prose —
# it only assigns sequential ids, lists memos by status, and stamps status
# transitions (+ appends the resulting feedback block from stdin).
#
# Usage:
#   decide.sh next-id                 # prints next free d{NNN}, "d001" on empty/missing dir
#   decide.sh list [open|resolved|pushed_back]   # id · title · status per memo; no arg = all
#   decide.sh resolve <id>    < stdin  # stamps status: resolved, appends "## Resolution"
#   decide.sh pushback <id>   < stdin  # stamps status: pushed_back, appends "## Push-back feedback"
#
# Memo location (parallel-worktree safe — branch-scoped, one canonical dir):
#   $DECISIONS_HOME/d{NNN}-{skill}-{slug}.md
#     = ~/.claude/skill-output/$REPO/$BRANCH/decisions/
#
# Deliberately NOT $OUT/decisions: skill-env.sh redirects $OUT to a cycle dir when
# a runner sets DEVSCREEN_CYCLE_OUTPUT_DIR, and next-id allocates ids by scanning
# its dir. Two dirs therefore means two different questions sharing one id — which
# is exactly what happened on dev-screen/home-cleanup, where d002 and d003 named
# different questions with different resolutions depending on which dir you read.
#
# Frontmatter fields memos are expected to carry (written by the skill that
# raises the memo, before this script ever touches the file):
#   id, title, status, raised_by, raised_at, resolution
# `resolution` stays empty until `resolve` fills it with a one-line summary
# drawn from stdin; the full text always lands in the appended body block.
#
# Lifecycle: open → resolved | pushed_back → refined (new/edited memo) | withdrawn (file deleted).

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SELF_DIR/skill-env.sh"   # sets OUT (mkdir -p'd), among others

DECISIONS_DIR="$DECISIONS_HOME"
mkdir -p "$DECISIONS_DIR"

usage() {
  cat <<'EOF'
Usage:
  decide.sh next-id
  decide.sh list [open|resolved|pushed_back]
  decide.sh resolve <id>    (resolution text on stdin)
  decide.sh pushback <id>   (feedback text on stdin)
EOF
}

# fm_field <file> <field> — print a frontmatter field's value (first match,
# scoped to the block between the first two "---" lines only).
fm_field() {
  local file="$1" field="$2"
  awk -v f="$field" '
    /^---[[:space:]]*$/ { c++; next }
    c==1 && $0 ~ "^"f":" { sub("^"f":[[:space:]]*", ""); print; exit }
  ' "$file"
}

cmd_next_id() {
  local max=0 base n
  shopt -s nullglob
  for f in "$DECISIONS_DIR"/d[0-9][0-9][0-9]-*.md; do
    base=$(basename "$f")
    n=$(printf '%s' "$base" | sed -E 's/^d([0-9]{3})-.*/\1/')
    n=$((10#$n))
    [ "$n" -gt "$max" ] && max=$n
  done
  shopt -u nullglob
  printf 'd%03d\n' $((max + 1))
}

cmd_list() {
  local filter="${1:-}" id title status
  shopt -s nullglob
  local files=("$DECISIONS_DIR"/d[0-9][0-9][0-9]-*.md)
  shopt -u nullglob
  if [ ${#files[@]} -eq 0 ]; then
    echo "(no decision memos)"
    return 0
  fi
  for f in "${files[@]}"; do
    id=$(fm_field "$f" id)
    title=$(fm_field "$f" title)
    status=$(fm_field "$f" status)
    if [ -n "$filter" ] && [ "$status" != "$filter" ]; then continue; fi
    printf '%s · %s · %s\n' "${id:-?}" "${title:-untitled}" "${status:-open}"
  done
}

# find_memo <id> — id may be given as "d001" or "001"; prints the matching
# memo path or fails if none/multiple exist.
find_memo() {
  local raw="$1" id
  id="${raw#d}"
  while [ ${#id} -lt 3 ]; do id="0$id"; done
  shopt -s nullglob
  local matches=("$DECISIONS_DIR"/d"$id"-*.md)
  shopt -u nullglob
  [ ${#matches[@]} -eq 1 ] || return 1
  printf '%s\n' "${matches[0]}"
}

stamp_field() {
  local file="$1" field="$2" value="$3" tmp
  tmp=$(mktemp)
  awk -v fld="$field" -v val="$value" '
    /^---[[:space:]]*$/ { c++; print; next }
    c==1 && $0 ~ "^"fld":" { print fld ": " val; next }
    { print }
  ' "$file" > "$tmp"
  mv "$tmp" "$file"
}

cmd_resolve() {
  local id="${1:-}"
  [ -n "$id" ] || { echo "resolve: missing <id>" >&2; return 1; }
  local file
  file=$(find_memo "$id") || { echo "resolve: no memo found for '$id'" >&2; return 1; }
  local body
  body=$(cat)
  local summary
  summary=$(printf '%s\n' "$body" | grep -m 1 '.')
  [ -n "$summary" ] || summary="(see Resolution below)"
  summary=$(printf '%s' "$summary" | cut -c1-100)
  stamp_field "$file" "status" "resolved"
  stamp_field "$file" "resolution" "$summary"
  printf '\n## Resolution\n\n%s\n' "$body" >> "$file"
  echo "Resolved $id → $(basename "$file")"
}

cmd_pushback() {
  local id="${1:-}"
  [ -n "$id" ] || { echo "pushback: missing <id>" >&2; return 1; }
  local file
  file=$(find_memo "$id") || { echo "pushback: no memo found for '$id'" >&2; return 1; }
  local body
  body=$(cat)
  stamp_field "$file" "status" "pushed_back"
  printf '\n## Push-back feedback\n\n%s\n' "$body" >> "$file"
  echo "Pushed back $id → $(basename "$file")"
}

case "${1:-}" in
  next-id) cmd_next_id ;;
  list) cmd_list "${2:-}" ;;
  resolve) cmd_resolve "${2:-}" ;;
  pushback) cmd_pushback "${2:-}" ;;
  *) usage; exit 1 ;;
esac
