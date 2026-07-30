---
name: feature-cycle
description: Analyze → plan → implement → validate → cleanup → commit → retro, for a UI feature or ticket. Each step runs in its own isolated subagent; the retro analyzes the run it just finished and proposes skill improvements.
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
  - id: retro
    skill: analyze-cycle
    args: "retro"
    model: sonnet
    stop_on_fail: false
    note: Post-mortem on the cycle that just ran — cost/tier fit, retries and loop convergence, contract violations, environmental failures, open memos — written to cycle-analysis-*.md with proposed skill edits. sonnet — the transcript-readers it fans out are sonnet anyway, and its proposals are gated by human approval, so a weak proposal costs a read rather than a bad edit. `retro` in args puts analyze-cycle in retro mode — it NEVER raises a decision memo and never reports BLOCKED (which would halt the cycle at its own finish line via SKILL.md Step 3e), and never applies an edit. stop_on_fail false — a retro problem must not undo committed work. Runs LAST, after commit, so the ledger it reads is complete. Default agent type (needs Write for its artifact and the Agent tool to fan out its readers).
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
the run halts before cleanup/commit so you can decide what to do next — except
now a `FAIL` first gets bounded remediation (see its `remediate:` entry above):
orch-ui spawns `impl-ui` against the failing validation-report and re-runs
`validate-ui` to re-check, up to 2 rounds, before treating it as a hard failure.
Judgment-call findings validate-ui can't resolve on its own (e.g. "unrequested
change — intentional?") come back as decision memos rather than inline prose
when validate-ui runs isolated here. A gap that no code change can close — a
mandated manual/visual/in-browser pass in an environment with no automation for
it — comes back as `BLOCKED` with a memo, never `FAIL`, so remediation isn't spent
re-deriving a verdict a human has to settle.

**`stop_on_fail` is a cross-runner contract.** Any executor of this cycle
definition — `/orch-ui` in-session or an external runner — must refuse to advance
past a step whose `stop_on_fail: true` gate has not passed, including manual
step-jump overrides. A cycle advanced past a failed gate is **non-conformant**,
not `completed`; `lib/cycle-forensics.py` flags it as `stop-on-fail-bypassed`.
This matters most for `cleanup`: skipping it ships unlinted, un-dead-code-checked
work under a `completed` cycle, which is exactly what happened on
`dev-screen/home-cleanup` (cycle `6895c16d`, commit `f33860d`).

`retro` runs last, after `commit`, and analyzes the cycle that just ran: where
the money went, which steps retried or failed to converge, which runs broke the
five-line contract, and what was environmental rather than a skill defect. It
writes `cycle-analysis-*.md` with **proposed** edits to the skills and to this
cycle definition — proposals only. Nothing is applied, no memo is raised, and
`stop_on_fail: false` means a retro problem can never undo committed work.

It captures the leak record **live**, with no waiting. The evidence window opens at
the end of the *previous* cycle on this branch and stays open to the moment the
retro runs, so it reads: that previous cycle's complete set of hand-fix sessions
and commits, every un-connected session that ran alongside this cycle (including
ones **still open**), rework detected straight from transcript edit-lists rather
than commits, and the uncommitted working tree. Retros therefore **compound** —
each closes the loop on its predecessor while capturing its own live signals. The
only thing a retro can't see is its own post-cycle leak, which hasn't happened
yet; the next retro on this branch reports it.

**A `BLOCKED` step (any step, not just `validate`) halts the cycle awaiting
answers, not a hard failure.** The subagent raised one or more decision memos
via `lib/decide.sh` instead of guessing — isolated subagents have no
AskUserQuestion, so the orchestrator lists the open memos, presents each to you,
and writes your answers back with `lib/decide.sh resolve`. Once every memo
raised is resolved, the cycle **re-runs that same step** (not the whole cycle)
and continues from there. This is the *only* resume behavior this cycle
supports — a halted/BLOCKED step picking back up within the same run once its
memos are answered. There is no `/orch-ui resume` mode for re-entering a past
run from `$RUNLOG` in a fresh session; if the session is gone, re-invoke the
cycle from Step 0.

