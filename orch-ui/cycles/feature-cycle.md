---
name: feature-cycle
description: Analyze → plan → implement → validate → cleanup → commit → capture learnings, for a UI feature or ticket. Each step runs in its own isolated subagent.
steps:
  - id: analyze
    skill: analyze-task
    args: "$TASK"
    model: sonnet
    stop_on_fail: true
    note: Gathers fixed facts (learnings, in-flight branch state, tooling constraints, task classification, named files) into analysis-*.md. $TASK = the feature/ticket description. sonnet — reading + distillation, not deep reasoning. Default agent type (needs Write for its artifact).
  - id: plan
    skill: plan-ui
    args: "$TASK"
    model: opus
    agent_type: Plan
    stop_on_fail: true
    note: Reads analysis-latest.md, discovers affected files, produces plan-*.md. opus — reasoning-heavy. Plan agent type — read-only architect, skips CLAUDE.md + leaner toolset; plan-ui persists its artifact via a Bash heredoc since Plan has no Write tool.
  - id: impl
    skill: impl-ui
    args: "use plan"
    model: sonnet
    stop_on_fail: true
    note: Picks up the latest plan and implements it. sonnet — standard build; internally delegates the presentation-layer pass (semantic markup, CSS, class composition) to a sonnet subagent — same-tier here, so it buys context isolation rather than a tier drop (the drop applies on a direct opus /impl-ui). Default agent type (needs Edit/Write, and the Agent tool to fan out the presentation pass).
  - id: validate
    skill: validate-ui
    args: "$TASK"
    model: opus
    stop_on_fail: true
    note: Behavioral gate — confirms the build matches the request before cleanup/commit. opus — a wrong pass here is expensive.
  - id: cleanup
    skill: cleanup-ui
    args: ""
    model: haiku
    stop_on_fail: true
    note: Lint, type-check, dead-code, and test fixes on the branch diff. haiku — mechanical.
  - id: commit
    skill: commit-branch
    args: ""
    model: haiku
    stop_on_fail: true
    note: Stage + commit (no push). Message generated from the diff. haiku — mechanical.
  - id: braindump
    skill: wiki-braindump
    args: ""
    scope: repo
    interactive: true
    stop_on_fail: false
    note: Repo-local + interactive. Free-form capture for the wiki; runs in the main session. Auto-skipped if the repo has no wiki-braindump skill. (No model — runs in the main session.)
  - id: ingest
    skill: wiki-ingest
    args: ""
    scope: repo
    model: sonnet
    stop_on_fail: false
    note: Repo-local. SHA-syncs the repo ./wiki/ against the branch's changed sources. Auto-skipped if the repo has no wiki-ingest skill. sonnet — structured but light.
---

# feature-cycle

Run with: `/orch-ui feature-cycle <feature or ticket description>` — or just
`/orch-ui <description>` and confirm the guessed cycle-type when prompted.

The full implementation loop for a UI feature. Each step is isolated in its own
subagent; results pass between steps through `~/.claude/skill-output/$REPO/$BRANCH/`,
which the skills read and write themselves.

`analyze` and `plan` are deliberately split. `analyze` gathers the **fixed facts**
around the task — learnings, in-flight branch state, tooling constraints, task
classification, and the files the task explicitly names — and distills them into
`analysis-*.md`. `plan` then reasons over that artifact: it discovers which files
the change *actually* touches (a planning judgment, not metadata) and produces the
plan. The seam is **mentioned vs. affected** files. The payoff: `analyze` runs on
sonnet while `plan` gets opus, the plan reasons over a clean digest rather than a
context full of raw file dumps, and the `analysis-*.md` artifact is reusable by
later steps instead of being re-derived each time.

`validate` is the behavioral gate: if the implementation doesn't match `$TASK`,
the run halts before cleanup/commit so you can decide what to do next.

The two `wiki-*` steps are **repo-local** (`scope: repo`): `/orch-ui` resolves them
from the triggering repo's own skill set (`.agent/skills/` or `.claude/skills/`),
not the global `~/.claude/skills/`. If the current repo has no such skill, that
step is skipped automatically — so the cycle runs cleanly in any repo, and uses
the repo's real wiki tooling where it exists (e.g. moscow's `.agent/skills/`).

`braindump` is `interactive: true`: moscow's `wiki-braindump` is a free-form
(often voice-driven) capture conversation that makes no edits, so it runs in the
main session rather than an isolated subagent. `ingest` then SHA-syncs the
`./wiki/` against the branch's changed sources as a normal isolated step.
Both are `stop_on_fail: false` — a wiki hiccup won't undo your committed work.
