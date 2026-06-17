#!/usr/bin/env bash
# find-affected-tests.sh — map a set of changed/planned files to the test files
# they affect, directly and indirectly. Pure filesystem logic (no judgment).
#
# Input: changed file paths, either as args or one-per-line on stdin.
#   printf '%s\n' "$CHANGED" | find-affected-tests.sh
#   find-affected-tests.sh apps/app/src/Foo.tsx packages/ui/src/Bar.ts
#
# Output: four labeled, deduped sections (empty sections print "(none)"):
#   DIRECT_UNIT     test/spec files already in the change set
#   INDIRECT_UNIT   sibling test files for changed sources (not already direct)
#   DIRECT_E2E      .cy.ts/.cy.tsx files already in the change set
#   INDIRECT_E2E    e2e specs that reference a changed source's basename
#
# Used by cleanup-ui Step 5 (dispatch test cleanup) and plan-ui Step 3 (test
# impact). The skill still decides what to do with each list; this only finds them.

if [ "$#" -gt 0 ]; then
  FILES=$(printf '%s\n' "$@")
else
  FILES=$(cat)
fi
FILES=$(printf '%s\n' "$FILES" | sed '/^$/d')

# Changed source files = .ts/.tsx that are not themselves test/spec/cypress files.
sources() {
  printf '%s\n' "$FILES" | grep -E "\.(ts|tsx)$" | grep -vE "\.(test|spec|cy)\.(ts|tsx)$"
}

direct_unit=$(printf '%s\n' "$FILES" | grep -E "\.(test|spec)\.(ts|tsx)$" | sort -u)
direct_e2e=$(printf '%s\n' "$FILES" | grep -E "\.cy\.(ts|tsx)$" | sort -u)

# Indirect unit: sibling test files that exist on disk for each changed source,
# excluding any already counted as direct.
indirect_unit=$(
  sources | while IFS= read -r f; do
    [ -z "$f" ] && continue
    dir=$(dirname "$f")
    base=$(basename "$f" | sed 's/\.[^.]*$//')
    ext="${f##*.}"
    for c in "$dir/$base.test.$ext" "$dir/$base.spec.$ext" \
             "$dir/__tests__/$base.test.$ext" "$dir/__tests__/$base.spec.$ext"; do
      [ -f "$c" ] && printf '%s\n' "$c"
    done
  done | sort -u | grep -vxF "$direct_unit" 2>/dev/null
)

# Indirect e2e: specs that mention a changed source's basename. Search the common
# spec roots; tolerate their absence.
e2e_roots=$(ls -d packages/e2e/tests/specs packages/e2e/cypress/e2e 2>/dev/null)
indirect_e2e=$(
  if [ -n "$e2e_roots" ]; then
    sources | while IFS= read -r f; do
      [ -z "$f" ] && continue
      name=$(basename "$f" | sed 's/\.[^.]*$//')
      grep -rl "$name" $e2e_roots 2>/dev/null
    done | sort -u
  fi
)

section() { printf '%s:\n%s\n\n' "$1" "${2:-(none)}"; }
section DIRECT_UNIT "$direct_unit"
section INDIRECT_UNIT "$indirect_unit"
section DIRECT_E2E "$direct_e2e"
section INDIRECT_E2E "$indirect_e2e"
