#!/usr/bin/env bash
# cleanup-scope.sh — resolve the set of files cleanup-ui should act on, plus the
# pnpm --filter flags for the packages they live in.
#
# Usage:
#   cleanup-scope.sh            # resolve from branch state
#   cleanup-scope.sh <path>     # restrict the resolved set to files under <path>
#
# Resolution order (first non-empty wins), mirroring cleanup-ui Step 1:
#   1. committed changes ahead of the default branch
#   2. staged changes
#   3. unstaged + untracked (excluding .claude/.cursor/thoughts/specs noise)
#
# Side effects (read by later cleanup-ui steps, surviving across shells):
#   /tmp/cleanup-ui-changed.txt   changed files, one per line
#   /tmp/cleanup-ui-filters.txt   pnpm --filter flags, space-separated (may be empty)
#
# Stdout: a human-readable summary (changed count, package list, filter flags).

BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$BASE" ] && BASE=main

CHANGED=$(git diff --name-only "$(git merge-base HEAD "$BASE")" HEAD 2>/dev/null)
[ -z "$CHANGED" ] && CHANGED=$(git diff --name-only --cached)
[ -z "$CHANGED" ] && CHANGED=$(git status --short \
  | grep -v '^?? \.claude\|^?? \.cursor\|^?? thoughts/\|^?? specs/' \
  | awk '{print $2}')

# Optional path scoping.
if [ -n "$1" ]; then
  CHANGED=$(printf '%s\n' "$CHANGED" | grep -F "$1")
fi
CHANGED=$(printf '%s\n' "$CHANGED" | sed '/^$/d')
printf '%s\n' "$CHANGED" > /tmp/cleanup-ui-changed.txt

# Affected package dirs: strip /src/... ; keep paths that have a package.json.
pkg_dirs=$(printf '%s\n' "$CHANGED" | sed 's|/src/.*||' | sort -u)

# Map each package dir to its package.json "name" → pnpm --filter flag.
read_name() {
  local pj="$1/package.json"
  [ -f "$pj" ] || return 1
  if command -v node >/dev/null 2>&1; then
    node -e 'const fs=require("fs");try{process.stdout.write(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).name||"")}catch(e){}' "$pj"
  else
    grep -m1 '"name"' "$pj" | sed -E 's/.*"name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'
  fi
}

filters=""
resolved=""
while IFS= read -r d; do
  [ -z "$d" ] && continue
  name=$(read_name "$d")
  [ -n "$name" ] && { filters="$filters --filter $name"; resolved="$resolved  $d → $name"$'\n'; }
done <<< "$pkg_dirs"
filters=$(printf '%s' "$filters" | sed 's/^ *//')
printf '%s' "$filters" > /tmp/cleanup-ui-filters.txt

echo "Changed files: $(printf '%s\n' "$CHANGED" | grep -c . ) (→ /tmp/cleanup-ui-changed.txt)"
echo "Affected packages:"
printf '%s' "${resolved:-  (none)
}"
echo "Filter flags: ${filters:-(none — use full-repo fallback)}"
