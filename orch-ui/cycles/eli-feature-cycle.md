---
name: eli-feature-cycle
description: Analyze → plan → implement → validate → cleanup → commit → self-review → capture learnings → retro, for a UI feature or ticket in ELI repos. Each step runs in its own isolated subagent (except the interactive self-review step); the retro analyzes the run it just finished and proposes skill improvements.
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
    note: Reads analysis-latest.md, discovers affected files, produces plan-*.md. opus — reasoning-heavy. Plan agent type — read-only architect, skips CLAUDE.md + leaner toolset; plan-ui persists its artifact via a Bash heredoc since Plan has no Write tool. Plan also has no Artifact tool — it still renders plan-*.html via lib/render-plan-artifact.sh and reports the path; the coordinator then publishes that .html with the Artifact tool (favicon "📐", no hand-authored HTML) and relays the artifact URL + open questions to the user.
  - id: impl
    skill: impl-ui
    args: "use plan"
    model: sonnet
    stop_on_fail: true
    note: Picks up the latest plan and implements it. sonnet — standard build; internally delegates the presentation-layer pass (semantic markup, CSS, class composition) to a sonnet subagent — same-tier here, so it buys context isolation rather than a tier drop (the drop applies on a direct opus /impl-ui). Ends with a scoped type-check gate so type errors are caught here, not by the opus validate step. Default agent type (needs Edit/Write, and the Agent tool to fan out the presentation pass).
  - id: validate
    skill: validate-ui
    args: "$TASK"
    model: opus
    stop_on_fail: true
    remediate:
      skill: impl-ui
      args: "fix validation gaps — read the latest validation-report"
      max: 2
    note: Behavioral gate — confirms the build matches the request before cleanup/commit. opus — a wrong pass here is expensive. Reads analysis-latest.md for constraints and, on large diffs, delegates the diff read to a sonnet summarizer instead of loading every changed file into opus context. On FAIL, orch-ui's bounded remediation (SKILL.md Step 3e) spawns impl-ui with the failing validation-report, then re-runs validate-ui to re-verify — up to 2 rounds — before falling back to a decision-memo check and, failing that, halting the cycle.
  - id: cleanup
    skill: cleanup-ui
    args: ""
    model: haiku
    stop_on_fail: true
    note: Lint, type-check, dead-code, and test fixes on the branch diff. haiku — mechanical. Its own Step 6 verify loop carries an internal cap of 3 fix→re-verify rounds (cleanup-ui's own bounded loop, independent of and smaller in scope than orch-ui's step-level `remediate`); cleanup-ui only reports STATUS to this cycle once that internal loop has applied-and-verified or exhausted its own cap and surfaced a cap-exhaustion menu or decision memo.
  - id: commit
    skill: commit-branch
    args: ""
    model: haiku
    stop_on_fail: true
    note: Stage + commit (no push). Message generated from the diff. haiku — mechanical.
  - id: self-review
    skill: pr-review-ui
    args: ""
    interactive: true
    stop_on_fail: false
    note: Runs in the main session, not isolated — no existing skill pushes or opens a PR, so this step does that first, then hands off. Before invoking pr-review-ui, push the branch and `gh pr create --draft`, but only after an explicit human confirmation — per CLAUDE.md, opening a PR always requires an explicit yes, never an automatic step. If the human declines or doesn't confirm, skip the rest of this step (no PR to review) and continue to the wiki steps. Once the PR exists, invoke pr-review-ui (Skill tool) against it — it checks out the PR via `gh pr checkout` — using its own internal per-lens model tiers. stop_on_fail false — advisory: surfaces findings on the PR for the human and any later /pr-review pass to act on, does not block or undo committed work.
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
  - id: retro
    skill: analyze-cycle
    args: "retro"
    model: sonnet
    stop_on_fail: false
    note: Post-mortem on the cycle that just ran — cost/tier fit, retries and loop convergence, contract violations, environmental failures, open memos — written to cycle-analysis-*.md with proposed skill edits. sonnet — the transcript-readers it fans out are sonnet anyway, and its proposals are gated by human approval, so a weak proposal costs a read rather than a bad edit. `retro` in args puts analyze-cycle in retro mode — it NEVER raises a decision memo and never reports BLOCKED (which would halt the cycle at its own finish line via SKILL.md Step 3e), and never applies an edit. stop_on_fail false — a retro problem must not undo committed work. Runs LAST, after the wiki steps, so the ledger it reads covers the whole cycle. Default agent type (needs Write for its artifact and the Agent tool to fan out its readers).
---

# eli-feature-cycle

Run with: `/orch-ui eli-feature-cycle <feature or ticket description>`.

The full implementation loop for a UI feature in an ELI repo. Each step is
isolated in its own subagent; results pass between steps through
`~/.claude/skill-output/$REPO/$BRANCH/`, which the skills read and write
themselves.

After committing, `self-review` runs in the main session (interactive, since no
existing skill pushes or opens a PR): it pushes and opens a draft PR — gated on
an explicit human confirmation before anything is pushed or made externally
visible — then invokes `pr-review-ui` against it so UI-specific feedback
surfaces before a human or CI reviewer sees the PR. `self-review` is
`stop_on_fail: false`: it surfaces findings, it doesn't block or undo committed
work.

This flow adds the repo-local, interactive `wiki-braindump` and isolated
`wiki-ingest` steps after that. Repos without those skills skip the
corresponding steps automatically. Both steps use `stop_on_fail: false`, so a
wiki problem does not undo committed work.

`retro` then closes the cycle by analyzing it — cost and tier fit, steps that
retried or failed to converge, contract violations, environmental failures, open
decision memos — and writes `cycle-analysis-*.md` with **proposed** edits to the
skills and to this cycle definition. Proposals only: nothing is applied, no memo
is raised, and `stop_on_fail: false` keeps a retro problem from undoing committed
work.

It captures the leak record **live**, with no waiting. The evidence window opens at
the end of the *previous* cycle on this branch and stays open to the moment the
retro runs, so it reads: that previous cycle's complete set of hand-fix sessions
and commits, every un-connected session that ran alongside this cycle (including
ones **still open**), rework detected straight from transcript edit-lists rather
than commits, and the uncommitted working tree. Retros therefore **compound** —
each closes the loop on its predecessor while capturing its own live signals. The
only thing a retro can't see is its own post-cycle leak, which hasn't happened
yet; the next retro on this branch reports it.
