#!/usr/bin/env bash
# env-preflight.sh — verify the toolchain is healthy BEFORE cleanup-ui forms any
# diagnosis from type-check/lint output.
#
# Why this exists: a version-mismatched Node/pnpm, or a stale/broken generated
# client (Prisma, GraphQL codegen, etc.), makes broad swaths of a monorepo fail
# type-check/lint for reasons that have nothing to do with the branch being
# cleaned up. An agent that doesn't check this first will misdiagnose the
# resulting noise as "pre-existing errors to fix" and start editing files to
# make them go away — including stripping real type assertions and
# eslint-disable comments that only *look* redundant because the environment
# can't resolve real types. (Written after exactly this happened: a Node
# version pinned in .tool-versions but never `asdf install`ed silently fell
# back to an older Node that couldn't run Prisma v7, cascading into ~20
# packages of false-positive failures and a wayward cleanup run editing 16
# unrelated files across 3 attempts before converging.)
#
# Exit 0: environment healthy, cleanup-ui may proceed as normal.
# Exit 1: environment unhealthy — cleanup-ui MUST stop and report, not fix.
# Failure detail is both printed and appended to $OUT/cleanup-preflight-fail.txt.

. "$(dirname "${BASH_SOURCE[0]}")/skill-env.sh"   # sets ROOT, OUT (mkdir -p'd)

: > "$OUT/cleanup-preflight-fail.txt"
ok=1

fail() {
  echo "✗ $1"
  echo "$1" >> "$OUT/cleanup-preflight-fail.txt"
  ok=0
}

# 1. engines.node vs the Node actually active in this shell.
#    A repo can pin the right version in .tool-versions/package.json and still
#    silently run an older one if it was never installed via asdf/nvm/etc —
#    `node --version` here reflects what's ACTUALLY active, not what's pinned.
if [ -f "$ROOT/package.json" ] && command -v node >/dev/null 2>&1; then
  wanted_node=$(node -e '
    try {
      const engines = require(process.argv[1]).engines || {}
      process.stdout.write((engines.node || "").replace(/[^0-9.]/g, ""))
    } catch (e) {}
  ' "$ROOT/package.json" 2>/dev/null)
  have_node=$(node -e 'process.stdout.write(process.versions.node)' 2>/dev/null)
  if [ -n "$wanted_node" ] && [ -n "$have_node" ]; then
    lowest=$(printf '%s\n%s\n' "$wanted_node" "$have_node" | sort -V | head -1)
    if [ "$lowest" != "$wanted_node" ]; then
      fail "Node version mismatch: repo requires >=$wanted_node (package.json engines.node), active Node is $have_node. This alone can cascade into dozens of unrelated type-check/lint failures — fix the toolchain (install the pinned version + reshim) before cleanup can produce a real signal."
    fi
  fi
fi

# 2. Generated-client freshness. Generic hook: if the ROOT package.json defines
#    a "db:generate" script (Prisma or equivalent codegen), run it and require
#    success. A stale/broken generated client is the other half of the
#    incident this script exists to catch.
if [ -f "$ROOT/package.json" ]; then
  has_db_generate=$(node -e '
    try { process.stdout.write(require(process.argv[1]).scripts?.["db:generate"] ? "1" : "") } catch (e) {}
  ' "$ROOT/package.json" 2>/dev/null)
  if [ "$has_db_generate" = "1" ]; then
    if ! (cd "$ROOT" && pnpm db:generate > "$OUT/cleanup-preflight-dbgen.txt" 2>&1); then
      fail "\`pnpm db:generate\` failed — generated client is stale, missing, or broken (see $OUT/cleanup-preflight-dbgen.txt for the real error). Regenerate before cleanup can produce a real signal; do NOT attempt to work around type errors this causes downstream."
    fi
  fi
fi

if [ "$ok" -eq 1 ]; then
  echo "✓ Environment preflight clean (engines satisfied, generated client OK)."
  exit 0
else
  echo "Environment preflight FAILED — see above / $OUT/cleanup-preflight-fail.txt."
  echo "cleanup-ui must stop here and report BLOCKED — it must not proceed to diagnose or edit files."
  exit 1
fi
