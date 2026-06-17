# Skill-authoring policy (Ben, global skills)

Rules for authoring the global skills in this repo. The two policies here are the ones skills actually depend on at runtime: how a skill tiers model/effort per subagent, and the hygiene invariant that keeps a global skill path from dragging in repo-specific bulk.

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

## Shared helper scripts (`lib/`)

Deterministic plumbing lives in `~/.claude/skills/lib/` as scripts skills call, not as bash re-emitted in every SKILL.md. Reuse these before inlining git/test boilerplate:

- **`skill-env.sh`** — `source` it to set `REPO BRANCH BASE OUT TS SRC LEARNINGS_DIR ROOT` and `mkdir -p "$OUT"`. Replaces the repo/branch/timestamp/output-dir block. When a step writes a report via the Write tool, follow the `source` with `echo "$OUT/<name>-$TS.md"` so the literal path is visible to the tool (shell vars don't survive to a separate Write call).
- **`find-affected-tests.sh`** — given changed/planned files (args or stdin), prints `DIRECT_UNIT/INDIRECT_UNIT/DIRECT_E2E/INDIRECT_E2E`. Used by cleanup-ui Step 5 and plan-ui Step 3.
- **`cleanup-scope.sh`** — resolves changed files + affected-package `pnpm --filter` flags; writes `/tmp/cleanup-ui-changed.txt` and `/tmp/cleanup-ui-filters.txt`.
- **`cleanup-verify.sh`** — runs type-check / lint / lint:prettier, pass-fail by exit code.

When extracting more such logic, keep it a faithful port (don't change behavior in the same pass), make it runnable standalone, and pass cross-step state through `/tmp` files since each SKILL.md bash block is a fresh shell.

## Global-skill hygiene (invariant)

A global skill path (`~/.claude/skills`) must never load a heavy *project* skill body (e.g. `prepare-branch`, `local-review`) to borrow its capability — that drags repo-specific bulk onto a repo-agnostic path. None do today; keep it that way. If a global path genuinely needs a project capability, write a lean global re-implementation of just that slice, don't reach into the project skill.
