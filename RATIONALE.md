# Suite rationale — why the odd clauses exist

Incident record for rules in `AUTHORING.md` itself. Per-skill rationale lives in
`<skill>/RATIONALE.md`. Nothing here is loaded at runtime; this is the answer to
"why is this weird constraint in the policy?" — and the evidence `/analyze-cycle`
should read before proposing that a rule be relaxed.

See `AUTHORING.md` § Rationale files for the format and the reason for the split.

## Index of per-skill rationale files

- `orch-ui/RATIONALE.md` — task normalisation, step liveness
- `plan-ui/RATIONALE.md` — immediate memo resolution
- `impl-ui/RATIONALE.md` — plan-scoped collision checks
- `validate-ui/RATIONALE.md` — concurrent-work findings, human-only gaps
- `cleanup-ui/RATIONALE.md` — change-set scope discipline

---

### `DECISIONS_HOME` is always the branch root, never cycle-redirected

`$OUT` moves under a cycle directory when `DEVSCREEN_CYCLE_OUTPUT_DIR` is set. Memos
written to `$OUT/decisions/` therefore orphan themselves per cycle, and
`decide.sh next-id` — which allocates by scanning the directory — starts over at
`d001` for each new cycle.

**Where:** `dev-screen` / `home-cleanup`. Two different memos were both allocated
`d004`, then `d005`, across cycles on the same branch; resolving one appeared to
resolve the other. `DECISIONS_HOME` exists so id allocation has exactly one fixed
scan target regardless of where artifacts are being written.

### A pause always ends the turn (deliberate divergence from the incentives source)

The incentives `build-feature`/`decide` paradigms allow an agent to do other work
while blocked on an open decision. This suite does not port that behavior.

**Why:** Ben's global working preference — "silence is never consent." A quiet human
is a blocked task, not an authorized one, so continuing on other work while a
question is outstanding is the failure mode, not a productivity gain. This is a
choice, not an incomplete port; do not "fix" it by adding parallel work at a pause.

### Loop counters and residuals persist on disk

Also a deliberate improvement over the incentives source, which holds loop counters
in orchestrator context only. Context can compact mid-loop; a counter that lived
only in context resets silently and the cap stops meaning anything.
