---
name: feature-cycle
description: Plan → implement → validate → cleanup → commit → capture learnings, for a UI feature or ticket. Each step runs in its own isolated subagent.
steps:
  - id: plan
    skill: plan-ui
    args: "$TASK"
    stop_on_fail: true
    note: Produces plan-*.md. $TASK = the feature/ticket description.
  - id: impl
    skill: impl-ui
    args: "use plan"
    stop_on_fail: true
    note: Picks up the latest plan and implements it.
  - id: validate
    skill: validate-ui
    args: "$TASK"
    stop_on_fail: true
    note: Behavioral gate — confirms the build matches the request before cleanup/commit.
  - id: cleanup
    skill: cleanup-ui
    args: ""
    stop_on_fail: true
    note: Lint, type-check, dead-code, and test fixes on the branch diff.
  - id: commit
    skill: commit-branch
    args: ""
    stop_on_fail: true
    note: Stage + commit (no push). Message generated from the diff.
  - id: braindump
    skill: wiki-braindump
    args: ""
    scope: repo
    interactive: true
    stop_on_fail: false
    note: Repo-local + interactive. Free-form capture for the wiki; runs in the main session. Auto-skipped if the repo has no wiki-braindump skill.
  - id: ingest
    skill: wiki-ingest
    args: ""
    scope: repo
    stop_on_fail: false
    note: Repo-local. SHA-syncs the repo ./wiki/ against the branch's changed sources. Auto-skipped if the repo has no wiki-ingest skill.
---

# feature-cycle

Run with: `/orch-ui feature-cycle <feature or ticket description>` — or just
`/orch-ui <description>` and confirm the guessed cycle-type when prompted.

The full implementation loop for a UI feature. Each step is isolated in its own
subagent; results pass between steps through `~/.claude/skill-output/$REPO/$BRANCH/`,
which the skills read and write themselves.

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
