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

## Prose tiering & size budgets

Instruction density is tiered the same way the model is. A capable model reads a SKILL.md as *reasoning material*: prohibitions it must check every action against, rationale it must reconcile with the instruction beside it, procedure it would have derived correctly on its own. Density that helps haiku costs opus deliberation. Match the prose to the tier the step actually runs at:

- **haiku step** — prescriptive. Exact commands, checklists, literal output strings. Leave nothing to derive.
- **sonnet step** — structure plus an output template; summarize procedure instead of dictating it.
- **opus step** — goal, inputs (artifact paths), output contract, hard boundaries. No procedure, no worked subagent prompts, no rationale.

Three rules follow, and they apply to every edit to a skill body:

1. **Rule, not story.** A rule earned from a past failure is stated as an imperative. The incident that produced it goes in the skill's `RATIONALE.md` (below) — never in SKILL.md, where a narrative reads as a problem to reason about rather than a line to follow.
2. **Compute it, don't reason it.** Anything deterministic — counting, precedence, tallies, path resolution, tool detection — goes in `lib/` and is invoked. Prose describing a computation makes the model re-derive it every run.
3. **State a contract once.** The canonical text for the Interaction contract, Iteration caps, and Decision memos is *this file*. A skill names the section and adds only its own specifics (its option set, its cap value). Four near-identical restatements cost more than one, because the model reconciles the differences between them. **Exception: haiku steps keep the procedure inline** — a haiku step sent to another file to learn the memo lifecycle is worse off than one handed the four commands. Dedupe applies to opus and sonnet bodies.

**Budgets** — measured in *prose words*: everything outside frontmatter, fenced blocks, table rows, and blockquotes. Fenced templates and tables are cheap (they constrain output); flowing prose is what invites deliberation.

| Tier | Prose-word budget |
|---|---|
| opus step | 900 |
| sonnet step | 1500 |
| haiku step | 2100 |
| `orch-ui` (protocol doc, not a step body) | 1600 |

Check with `python3 ~/.claude/skills/lib/skill-size.py` — it resolves each skill's tier from the cycle definitions (strictest tier any cycle runs it at), prints the table, and exits 1 if anything is over. A skill no cycle references is unbudgeted. Over budget is a signal to move rationale out or cut a restatement — never to compress by deleting a rule.

## Rationale files (`RATIONALE.md`)

Every incident that justified a rule stays on disk — in `<skill>/RATIONALE.md`, beside the skill, keyed to the rule it produced. Nothing is deleted; it moves off the runtime path. Only `SKILL.md` is loaded when a skill runs, so a rationale file costs nothing per-step and stays available to a human, to `/analyze-cycle`, and to whoever next proposes changing the rule.

Format: one `### <the rule, quoted from SKILL.md>` heading per entry, then what happened, where (repo/branch/cycle), and what it cost. `RATIONALE.md` answers "why is this odd clause here?" — which was the only job the narrative ever did inside SKILL.md.

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
- **`skill-size.py`** — prose-budget check for the whole suite: resolves each skill's tier from the cycle definitions, prints `skill · tier · prose words · budget · status`, exits 1 if any skill is over. `--json` for machine use. See Prose tiering & size budgets above.
- **`validation-verdict.sh`** — given a validate-ui report body, counts gaps (`✗`/`⚠` under Requirements Check / Implicit Requirements / Test Coverage) and unrequested changes, applies the verdict precedence, and prints the report frontmatter. `--human-only-gaps N` is honored only when `N` equals the total gap count, which is how "no automation surface for any remaining gap" becomes `blocked: true` deterministically instead of a prose carve-out an opus step re-derives.
- **`spawn-tally.sh`** — given an orch-ui runlog, prints the per-run subagent launch rollup (`general-purpose: 4, Plan: 1`) from its `SPAWN:` lines.
- **`decide.sh`** — decision-memo plumbing: `next-id` (scans `$DECISIONS_HOME/`, prints next `d{NNN}`), `list [open|resolved|pushed_back]` (prints `id · title · status` per memo from frontmatter), `resolve <id>` / `pushback <id>` (stdin → appended block + frontmatter status stamp). Owns only ids and status transitions — memo *bodies* are authored by the calling skill via Write/heredoc. See Decision memos below.

When extracting more such logic, keep it a faithful port (don't change behavior in the same pass), make it runnable standalone, and pass cross-step state through `/tmp` files since each SKILL.md bash block is a fresh shell.

## Decision memos & per-repo review heuristics

**Decision memos** replace free-text "open questions" with a local, file-based, trackable channel — a lean re-implementation of the incentives `decide` paradigm, HQ-free.

- Location: `$DECISIONS_HOME/d{NNN}-{skill}-{slug}.md` — always the branch root (`~/.claude/skill-output/$REPO/$BRANCH/decisions/`), never cycle-redirected. `DECISIONS_HOME` exists so id allocation has one fixed scan target; writing memos to `$OUT/decisions/` instead orphans them per-cycle and makes `next-id` reuse ids (see `RATIONALE.md`).
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
