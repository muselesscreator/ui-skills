# Skill-authoring policy (Ben, global skills)

Rules for authoring the global skills in this repo. The policies here are the ones skills actually depend on at runtime: how a skill tiers model/effort per subagent, the shared interaction/iteration conventions (menus, caps, decision memos, review heuristics), and the hygiene invariant that keeps a global skill path from dragging in repo-specific bulk.

Knowledge **placement** (personal → project → canonical), promotion, and learnings storage live in `~/.claude/knowledge-layers.md` — read that when deciding *where a fact goes*, not when authoring a skill.

## Model & effort tiering (token budgeting)

Repo-agnostic policy for **how skills choose a model/effort per subagent**, so token spend matches the work. When a skill spawns an isolated or parallel subagent, pick a tier deliberately instead of defaulting to the session model.

- **haiku** — mechanical / deterministic, low judgment: lint-fix, dead-code removal, type-error fixes, commit message from a diff, file moves, status parsing.
- **sonnet** — standard implementation & review: building a feature, writing tests, most review specialists, structured-but-light synthesis.
- **opus** — deep reasoning where a wrong answer is expensive: planning, architecture, the behavioral validation gate, security/correctness review, cross-cutting synthesis.

Mechanics & caveats:
- The **Task/Agent tool only accepts `model`** (sonnet/opus/haiku/fable) — *not* effort. So in skills, `model` is the per-subagent lever; effort stays session-level.
- **Per-subagent effort** is only controllable when a skill is authored as a **Workflow** script (`agent()` takes `model` *and* `effort`). Reach for that only when effort tuning demonstrably matters — it's a real rewrite.
- A skill that fans out (parallel specialists, or one subagent per step) is where tiering pays off most; single-context skills can ride the session model.

## Interaction contract

The suite's one interaction shape for any moment a skill needs a human choice — cap-exhaustion menus, open decision memos, cycle-type confirmation (`orch-ui` Step 0), and any destructive action (delete, force-push, overwrite a shared/public contract).

**Menu shape**: lettered options `A) B) C)` (recommendation first, per the AskUserQuestion convention), plus a final catch-all `―) none of these — add context`. Use AskUserQuestion when interactive; an isolated subagent cannot — its path is to write a decision memo (see Decision memos below) and report `STATUS: BLOCKED` instead.

**Cap-exhaustion menu** (every capped fix loop presents this on exhaustion — see Iteration caps):
- A) keep iterating, *re-bounded* — grants a fresh bounded budget, never an unlimited one
- B) accept the residual and proceed
- C) stop for human review

**Pause / no-pause table**:

| Pauses (ends the turn) | Never pauses |
|---|---|
| An open decision memo | A bounded fix loop still under its cap |
| A cap-exhaustion checkpoint | Re-verification after a fix (the gate re-run itself) |
| Cycle-type confirmation (`orch-ui` Step 0) | |
| A destructive action (delete, force-push, overwrite a shared/public contract) | |

**Rider — Ben's hard rule (CLAUDE.md: "silence is never consent")**: at any pause the turn **ends**. No defaults, no picking Option A because the human "is probably away," no proceeding on a flag noted as "for later human review." A quiet human is a blocked task, not an authorized one.

⚠ **Deliberate divergence from the incentives source**: incentives' `build-feature`/`decide` paradigms permit doing other work while blocked on an open decision. This suite does **not** port that behavior — a pause always ends the turn here. This is a deliberate choice (per Ben's global working preferences), not an oversight or a partial port.

## Iteration caps

Every automatic fix loop (`cleanup-ui`'s verify loop, `orch-ui`'s remediation loop, any future capped loop) carries an **integer cap** fixed at authoring time — never left open-ended.

- **The only clean exit is applied-and-verified.** A fix must actually be applied, then the deterministic gate (lint/type-check/test/`cleanup-verify.sh`/etc.) must be **re-run** and show clean. Presenting findings, or the model's own confidence that a fix "should work," is never sufficient on its own — only a fresh gate re-run counts.
- **On cap exhaustion**, present the cap-exhaustion menu (Interaction contract, above) with the exact residual (which check(s) still fail) — never a generic "cap reached."
- **Counters and last-pass residuals persist on disk** — `$RUNLOG` for orchestrated loops; a `$OUT`-scoped counter file surfaced in the skill's report for single-skill loops (e.g. cleanup-ui's `$OUT/cleanup-verify-attempts.txt`) — never held only in agent context, so they survive compaction. This is a deliberate improvement over the incentives source, which keeps loop counters in orchestrator context only.

## Shared helper scripts (`lib/`)

Deterministic plumbing lives in `~/.claude/skills/lib/` as scripts skills call, not as bash re-emitted in every SKILL.md. Reuse these before inlining git/test boilerplate:

- **`skill-env.sh`** — `source` it to set `REPO BRANCH BASE OUT TS SRC LEARNINGS_DIR ROOT DECISIONS_HOME` and `mkdir -p "$OUT"`. Replaces the repo/branch/timestamp/output-dir block. When a step writes a report via the Write tool, follow the `source` with `echo "$OUT/<name>-$TS.md"` so the literal path is visible to the tool (shell vars don't survive to a separate Write call).
- **`find-affected-tests.sh`** — given changed/planned files (args or stdin), prints `DIRECT_UNIT/INDIRECT_UNIT/DIRECT_E2E/INDIRECT_E2E`. Used by cleanup-ui Step 5 and plan-ui Step 3.
- **`cleanup-scope.sh`** — resolves changed files + affected-package `pnpm --filter` flags; writes `$OUT/cleanup-scope-changed.txt` and `$OUT/cleanup-scope-filters.txt` (repo+branch scoped — parallel worktrees don't collide).
- **`cleanup-verify.sh`** — runs type-check / lint / lint:prettier, pass-fail by exit code.
- **`render-plan-artifact.sh`** — wraps a `plan-*.md` into `plan-ui/plan-template.html` (self-contained page with an inline markdown renderer; fills title + repo/branch/date chips) and prints the `.html` path for the Artifact tool. Used by plan-ui Step 6. The model never authors plan HTML — extend the template, not the skill prose, if the page needs to change.
- **`cycle-forensics.py`** — post-mortem extraction for a completed cycle: `list` (enumerate cycle runs), `report <id|latest|dir|runlog.md>` (step ledger with every attempt, cost rollups, artifact inventory, decision memos, session map incl. **unlinked** branch sessions, branch commits + rework files, mechanical flags), `history` (per-skill aggregates across cycles — the systemic-vs-one-off evidence), `sessions` (session map as JSON). Handles both surfaces: dev-screen cycle dirs (`$OUT/cycles/<id>/manifest.json` + per-attempt `request/result/usage/log` files, real USD) and in-session `/orch-ui` runlogs (`$OUT/orch-run-*.md`, no cost data). **It reports USD, never computes it** — no price table is embedded, since a stale constant is worse than an honest token count. Used by `analyze-cycle`.
- **`decide.sh`** — decision-memo plumbing: `next-id` (scans `$DECISIONS_HOME/`, prints next `d{NNN}`), `list [open|resolved|pushed_back]` (prints `id · title · status` per memo from frontmatter), `resolve <id>` / `pushback <id>` (stdin → appended block + frontmatter status stamp). Owns only ids and status transitions — memo *bodies* are authored by the calling skill via Write/heredoc. See Decision memos below.

When extracting more such logic, keep it a faithful port (don't change behavior in the same pass), make it runnable standalone, and pass cross-step state through `/tmp` files since each SKILL.md bash block is a fresh shell.

## Decision memos & per-repo review heuristics

**Decision memos** replace free-text "open questions" with a local, file-based, trackable channel — a lean re-implementation of the incentives `decide` paradigm, HQ-free.

- Location: `$DECISIONS_HOME/d{NNN}-{skill}-{slug}.md` — always the branch root (`~/.claude/skill-output/$REPO/$BRANCH/decisions/`), never cycle-redirected. `$OUT` moves under a cycle dir when `DEVSCREEN_CYCLE_OUTPUT_DIR` is set, so memos written to `$OUT/decisions/` orphan themselves per-cycle and `next-id` reuses ids (the d004/d005 incident on dev-screen/home-cleanup); `DECISIONS_HOME` exists so id allocation has one fixed scan target.
- A memo is one markdown file: frontmatter (`id, title, status, raised_by, raised_at, resolution`) + body (context, lettered options with trade-offs, recommendation first — per the Interaction contract's menu shape). `resolution` stays empty until resolved.
- Lifecycle: `open → resolved` (human answered) or `open → pushed_back → refined (new/edited memo) | withdrawn (file deleted)` — never PATCHed into limbo.
- Plumbing lives in `lib/decide.sh` (above) — the script owns only ids and status transitions; memo *bodies* are authored by the raising skill via Write/heredoc.
- **Dedupe-before-raise**: run `lib/decide.sh list open` before raising a memo; extend an existing memo rather than raising a near-duplicate.
- Interactive sessions answer via AskUserQuestion immediately (the memo still records the outcome — it doubles as a decision log). Isolated subagents cannot use AskUserQuestion (main-session-only) — their path is: write the memo, report `STATUS: BLOCKED` + `DECISIONS: <ids>`, and let the orchestrator/user answer.

**Per-repo review heuristics** — a repo's review conventions (beyond the generic UI/security/etc. lenses) live in a per-repo file, sliced per-lens into review agents the same way `pr-review-ui` Step 6 already injects its conventions file (by path, never embedded in prompts). Lookup order (first hit wins):
1. Repo-local `.claude/review-heuristics.md`
2. A wiki note via QMD
3. `~/.claude/repo-learnings/$REPO/review-heuristics.md`

Global skills ship only the lookup/injection mechanism — never heuristic *content*. Seeding a repo's `review-heuristics.md` is that repo's job, not this suite's.

## Global-skill hygiene (invariant)

A global skill path (`~/.claude/skills`) must never load a heavy *project* skill body (e.g. `prepare-branch`, `local-review`) to borrow its capability — that drags repo-specific bulk onto a repo-agnostic path. None do today; keep it that way. If a global path genuinely needs a project capability, write a lean global re-implementation of just that slice, don't reach into the project skill.
