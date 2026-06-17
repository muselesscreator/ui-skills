#!/usr/bin/env bash
# cleanup-verify.sh — run cleanup-ui's three final gate checks and report
# pass/fail by exit code (more reliable than the LLM eyeballing `tail -5`).
#
# Checks: type-check, lint (ESLint), lint:prettier. Prettier is a SEPARATE CI
# check from ESLint and is not covered by `pnpm lint` — so it is verified
# explicitly here.
#
# Uses the --filter flags from /tmp/cleanup-ui-filters.txt (written by
# cleanup-scope.sh) to scope prettier to affected packages; falls back to
# full-repo when absent. Full logs are saved under /tmp for diagnosis.
#
# Exit: 0 if all three pass, 1 otherwise.

FILTERS=$(cat /tmp/cleanup-ui-filters.txt 2>/dev/null)

run() {
  local label="$1" log="$2"; shift 2
  if "$@" > "$log" 2>&1; then
    echo "  ✓ $label"
    return 0
  else
    echo "  ✗ $label — see $log"
    return 1
  fi
}

rc=0
echo "Final verification:"
run "type-check" /tmp/cleanup-ui-typecheck.txt pnpm type-check || rc=1
run "lint (eslint)" /tmp/cleanup-ui-lint.txt pnpm lint || rc=1

if [ -n "$FILTERS" ]; then
  # shellcheck disable=SC2086
  run "lint:prettier" /tmp/cleanup-ui-prettier.txt pnpm $FILTERS lint:prettier || rc=1
else
  run "lint:prettier" /tmp/cleanup-ui-prettier.txt pnpm lint:prettier || rc=1
fi

if [ "$rc" -eq 0 ]; then
  echo "All three checks clean."
else
  echo "One or more checks failed — read the noted log(s), fix, and re-run."
fi
exit "$rc"
