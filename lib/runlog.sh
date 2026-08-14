# runlog.sh — per-session runlog so MANUALLY invoked skills are trackable.
#
# A cycle only became analyzable if it was run through dev-screen (manifest +
# per-run .request/.result/.usage.json) or through /orch-ui in-session (which
# writes its own $OUT/orch-run-$TS.md). A skill invoked directly — /plan-ui,
# /impl-ui by hand — left only its artifact, so cycle-forensics.py had no cycle
# to resolve and /analyze-cycle could not run on it at all. This closes that gap.
#
# Source it (don't execute), after skill-env.sh:
#   source ~/.claude/skills/lib/skill-env.sh
#   source ~/.claude/skills/lib/runlog.sh
#   runlog_append <step-id> <STATUS> <ARTIFACT> <SUMMARY> [FOLLOWUP] [DECISIONS]
#
# One runlog per Claude session ($CLAUDE_CODE_SESSION_ID), named
# orch-run-<stamp>-<sid8>.md. Work spanning several sessions therefore reads as
# several cycles — the deliberate trade for an unambiguous boundary that needs
# no staleness heuristic and no cross-session state.
#
# Emits the two-token header and `### <id> — <STATUS>` heading that
# parse_runlog's original regexes require, so a runlog written here is readable
# by that parser whether or not the tolerance fix is present.

RUNLOG_SENTINEL_MAX_AGE_SECONDS=${RUNLOG_SENTINEL_MAX_AGE_SECONDS:-21600}  # 6h

# Why this run must NOT write a runlog, or empty if it should. Three guards,
# because double-logging is worse than not logging: forensics would see the same
# work as two cycles and double-count every leak.
runlog_suppressed_because() {
  # 1. dev-screen owns this step: run files are the source of truth, and
  #    skill-env.sh has already redirected $OUT into the cycle dir.
  if [ -n "${DEVSCREEN_CYCLE_OUTPUT_DIR:-}" ]; then
    echo "dev-screen cycle step (DEVSCREEN_CYCLE_OUTPUT_DIR set)"; return
  fi
  # 2. Explicit opt-out, for any runner implementing the cycle-step contract.
  if [ "${ORCH_CYCLE_STEP:-}" = "1" ]; then
    echo "cycle step (ORCH_CYCLE_STEP=1)"; return
  fi
  # 3. /orch-ui is sequencing in this branch's output dir and logs its own steps.
  #    A subagent cannot see the orchestrator's env (each Bash call is a fresh
  #    shell), so the handoff is this file. Staleness-bounded so an orch-ui that
  #    died mid-cycle cannot suppress manual logging forever.
  local sentinel="$OUT/.orch-active"
  if [ -f "$sentinel" ]; then
    local now age
    now=$(date +%s)
    age=$(( now - $(runlog__mtime "$sentinel") ))
    if [ "$age" -lt "$RUNLOG_SENTINEL_MAX_AGE_SECONDS" ]; then
      echo "/orch-ui cycle active ($sentinel)"; return
    fi
  fi
}

runlog__mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

runlog_path() {
  [ -n "${OUT:-}" ] || return 1
  local sid8 existing
  sid8=$(printf '%s' "${CLAUDE_CODE_SESSION_ID:-nosid}" | cut -c1-8)
  # find, not a glob: zsh's nomatch prints its own error before the command runs,
  # so a redirect on `ls` cannot silence an unmatched pattern.
  existing=$(find "$OUT" -maxdepth 1 -name "orch-run-*-$sid8.md" 2>/dev/null | sort | head -1)
  if [ -n "$existing" ]; then echo "$existing"; return 0; fi
  echo "$OUT/orch-run-$(date +%Y%m%d-%H%M%S)-$sid8.md"
}

# Next free heading id, so a skill invoked twice in one session doesn't collide
# (impl, impl-2, impl-3 …) — mirrors the attempt numbering forensics expects.
runlog__next_id() {
  local file="$1" id="$2" n=2
  [ -f "$file" ] || { echo "$id"; return; }
  grep -qE "^### $id( |—|$)" "$file" || { echo "$id"; return; }
  while grep -qE "^### $id-$n( |—|$)" "$file"; do n=$((n + 1)); done
  echo "$id-$n"
}

runlog_append() {
  # Not `status`: it is a read-only special variable in zsh, and these helpers are
  # sourced by skills running under the user's shell as well as bash.
  local id="$1" verdict="$2" artifact="${3:--}" summary="${4:-}" followup="${5:--}" decisions="${6:--}"
  local why file
  why=$(runlog_suppressed_because)
  if [ -n "$why" ]; then
    echo "runlog: skipped — $why"
    return 0
  fi
  if [ -z "${OUT:-}" ]; then
    echo "runlog: skipped — \$OUT unset (source skill-env.sh first)" >&2
    return 0
  fi
  file=$(runlog_path) || return 0

  if [ ! -f "$file" ]; then
    {
      printf '# orch-ui run — manual — %s/%s\n\n' "${REPO:-unknown}" "${BRANCH:-unknown}"
      printf -- '- Repo: %s\n' "${REPO:-unknown}"
      # The REAL branch name, not skill-env's dashed $BRANCH path key: forensics
      # matches this against transcript branches and uses it as a git ref
      # (origin/main..<branch>), and both fail on the dashed form.
      printf -- '- Branch: %s\n' "$(git -C "${ROOT:-.}" branch --show-current 2>/dev/null || echo "${BRANCH:-unknown}")"
      # The worktree is what lets forensics find this branch's transcripts and
      # commits — i.e. the whole leak/rework analysis. A runlog has no manifest to
      # read it from, and repo+branch cannot be inverted back to a path, so record
      # it here while we are standing in it.
      printf -- '- Worktree: %s\n' "${ROOT:-$(pwd)}"
      printf -- '- Session: %s\n' "${CLAUDE_CODE_SESSION_ID:-unknown}"
      printf -- '- Started: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf -- '- Source: manual — each skill appends its own result as it is invoked\n\n'
      printf '**Task:** %s\n\n' "${RUNLOG_TASK:-manual session on ${BRANCH:-unknown}}"
      printf '## Step results\n'
    } > "$file"
  fi

  id=$(runlog__next_id "$file" "$id")
  {
    printf '\n### %s — %s\n' "$id" "$verdict"
    printf 'STATUS: %s\n' "$verdict"
    printf 'ARTIFACT: %s\n' "$artifact"
    printf 'SUMMARY: %s\n' "$summary"
    printf 'FOLLOWUP: %s\n' "$followup"
    printf 'DECISIONS: %s\n' "$decisions"
    printf -- '- at: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >> "$file"

  echo "runlog: $file (step $id)"
}

# /orch-ui calls these so its in-session steps suppress per-skill logging.
runlog_cycle_begin() { [ -n "${OUT:-}" ] && : > "$OUT/.orch-active"; }
runlog_cycle_end() { [ -n "${OUT:-}" ] && rm -f "$OUT/.orch-active"; }
