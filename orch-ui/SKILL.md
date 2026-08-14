---
name: orch-ui
description: Orchestrates a multi-step UI work cycle. Selects the cycle-type (e.g. feature-cycle), CONFIRMS it with you, then runs each step in its own isolated subagent, handing off through files — the coordinating layer over plan/impl/validate/cleanup/commit/wiki skills. Use when asked to run a UI cycle, orchestrate a feature, or on /orch-ui.
version: 1.0.0
triggers:
  explicit:
    - orch-ui
    - run /orch-ui
    - orchestrate this
    - run the feature cycle
    - run a ui cycle
  strong_intent:
    - take this through plan to commit
    - run the whole cycle on this
confidence_threshold: 85
---

# orch-ui — generic UI cycle orchestrator

**Arguments**: $ARGUMENTS (optional) — an initial message / task. May hint which cycle-type to run; the rest is the task description passed to the cycle as `$TASK`.

You are the **orchestrator**. You run a selected cycle's steps **in order**, each step in its **own isolated subagent context**, passing results between steps through files. You stay thin: you never do a step's work yourself, and you never read a step's full artifact — only its status, artifact path, and a short summary.

## Step 0: Select the cycle-type — then CONFIRM before acting

Do this **before touching anything**. Never run a step until the user has confirmed the cycle-type.

1. Enumerate available cycle-types: read each `~/.claude/skills/orch-ui/cycles/*.md` and pull its `name` + `description` from frontmatter (ignore `README.md`).
2. **Guess** from `$ARGUMENTS`:
   - If the first token exactly matches a cycle `name`, take that as the cycle and treat the remainder as `$TASK`.
   - Otherwise, if `$ARGUMENTS` is non-empty, pick the best-matching cycle by description and treat the whole string as `$TASK`.
   - If `$ARGUMENTS` is empty or the match is unclear, make no assumption.
2b. **Normalise `$TASK` to the bare requirement** before substituting it anywhere. Strip a leading skill-invocation preamble — `Invoke the <skill> skill with arguments:`, `/<skill>`, `run <skill> on`, `use <skill> to` — and nothing else; never text that could be a requirement. Steps that treat `$TASK` as the spec (`validate-ui`) otherwise grade the implementation against an instruction to invoke a skill (`RATIONALE.md`). Show the normalised task in the confirmation below so the user can correct it.
3. **Confirm with the user and wait for a reply.** Present the guess and the alternatives — e.g.:

   > Cycle: **feature-cycle** — _<its description>_
   > Task: _<$TASK, or "(none given)">_
   > Steps: analyze → plan → impl → validate → cleanup → commit
   > Proceed? Or pick another cycle / edit the task.

   Use AskUserQuestion if it makes the choice cleaner (options = the available cycle-types). If `$TASK` is empty but the chosen cycle needs one (e.g. `plan` takes `$TASK`), ask for it now.
4. Only after explicit confirmation, continue. If the user changes the cycle or task, re-confirm.

## Step 1: Resolve context

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///; s/\.git//')
[ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
OUT=~/.claude/skill-output/$REPO/$BRANCH
mkdir -p "$OUT"
TS=$(date +%Y%m%d-%H%M%S)
RUNLOG="$OUT/orch-run-$TS.md"
# Claim the branch's output dir for the duration of this cycle. Each step's skill
# now records itself in a per-session runlog when invoked by hand (lib/runlog.sh);
# this sentinel is how it knows not to, since a subagent cannot see this shell's
# env. Without it the same step would be logged twice — once here and once by the
# skill — and forensics would read one cycle as two and double-count every leak.
source ~/.claude/skills/lib/runlog.sh
runlog_cycle_begin
```

## Step 2: Load the chosen cycle definition

Read `~/.claude/skills/orch-ui/cycles/<cycle>.md`. Parse the `steps:` list from its frontmatter. Each step has:
- `id` — short label
- `skill` — the skill to invoke
- `args` — argument string (may contain `$TASK`)
- `scope` — `global` (default; `~/.claude/skills/`, Skill tool) or `repo` (the **triggering shell's current repo** owns it — resolve from there)
- `interactive` — `true` if it needs live back-and-forth (runs in the main session, never isolated)
- `model` — the model tier for this step's subagent: `haiku` (mechanical), `sonnet` (standard), or `opus` (deep reasoning). If absent, omit the override and let the subagent inherit the session model. Ignored for `interactive` steps (those run in the main session).
- `agent_type` — the subagent type to spawn (default `general-purpose`). A read-only planning/analysis step can set `Plan` or `Explore`: those skip CLAUDE.md inheritance and run on a leaner tool set, shaving the per-subagent startup floor. **Constraint:** `Plan`/`Explore` have no Write/Edit tool, so a step using them must run a skill that either returns its result inline (in `FOLLOWUP`, with `ARTIFACT: -`) or persists its artifact via a Bash heredoc — never the Write tool. Ignored for `interactive` steps.
- `stop_on_fail` — `true` (default) or `false`. This is a **cross-runner contract**: any executor of a cycle definition — this skill in-session, or an external runner — must refuse to advance past a step whose `stop_on_fail: true` gate has not passed, including manual step-jump overrides. A cycle advanced past a failed gate is **non-conformant**, not `completed`. `lib/cycle-forensics.py` flags violations as `stop-on-fail-bypassed`.
- `remediate` — optional `{skill, max}`: bounded auto-remediation for this step's failure gate (Step 3e). `skill` is the remediation skill to spawn on `STATUS: FAIL`, `max` the integer round cap. Absent → a FAIL halts the cycle immediately, unchanged. Orthogonal to `STATUS: BLOCKED`, which always goes through decision-memo resolution regardless of whether `remediate` is set.
- `stub` — `true` if not yet implemented (skip it)
- `note` — optional human note

Write the planned step list to `$RUNLOG` and show the user a one-line plan.

## Step 3: Run each step in sequence

For each step, in order:

### a. Skip stubs
If `stub: true` → log `⏭ <id>: skipped (stub)` to `$RUNLOG` and the user, then continue. No subagent.

### b. Resolve the skill
- `scope: global` (default): the skill is `~/.claude/skills/<skill>/`, invoked via the Skill tool.
- `scope: repo`: resolve from the **triggering shell's current repo** — the skill is owned by the repo, not the global set:
  ```bash
  ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
  SKILLFILE=""
  for d in ".agent/skills" ".claude/skills"; do
    [ -f "$ROOT/$d/<skill>/SKILL.md" ] && SKILLFILE="$ROOT/$d/<skill>/SKILL.md" && break
  done
  ```
  If no file is found → log `⏭ <id>: skipped (no <skill> skill in this repo)` and continue. The repo simply doesn't provide that capability — expected, not an error.

### c. Interactive steps (`interactive: true`)
These need the human, so they **cannot be isolated**. Do NOT spawn a subagent. In the main session: announce the step, then read and follow the resolved skill (`$SKILLFILE` for `scope: repo`, or the Skill tool for `scope: global`) directly, conversing with the user. When it concludes, record a one-line result and continue. This is the one deliberate exception to isolation.

### d. Normal steps → one isolated subagent
Substitute `$TASK` into `args`, then spawn ONE subagent with the **Task** tool using `subagent_type` = the step's `agent_type` (default `general-purpose`). If the step has a `model`, pass it as the Task tool's `model` (`haiku`/`sonnet`/`opus`); if absent, omit `model` so the subagent inherits the session model. Before spawning, append `SPAWN: <id> agent_type=<agent_type>` to `$RUNLOG` — this is the launch tally used in Step 4. Give it exactly this prompt:

> You are running one isolated step of the `<cycle>` cycle — repo `<REPO>`, branch `<BRANCH>`.
> `ORCH_CYCLE_STEP: 1` — I record your result in the cycle runlog myself. If the skill you invoke ends with a `runlog_append` step, SKIP it; export `ORCH_CYCLE_STEP=1` in that shell if you run it anyway.
> — If `scope: global`: **Invoke the `<skill>` skill** (Skill tool) with arguments: `<resolved args>`. If you cannot invoke it as a skill, read and follow `~/.claude/skills/<skill>/SKILL.md`.
> — If `scope: repo`: **Read and follow `<SKILLFILE>`** (a repo-local skill) with arguments: `<resolved args>`.
> The skill reads any prior step's output from `~/.claude/skill-output/<REPO>/<BRANCH>/` itself and writes its own artifact there. Do the full work it describes.
> When done, reply with EXACTLY these five lines and nothing else:
> `STATUS: PASS | FAIL | BLOCKED`
> `ARTIFACT: <absolute path to the artifact the skill wrote, or - if none>`
> `SUMMARY: <one sentence>`
> `FOLLOWUP: <what the next step or the human must know, or ->`
> `DECISIONS: <comma-sep decision-memo ids the skill raised via lib/decide.sh, or ->`

`DECISIONS` is additive to the original four-line contract; note any ids raised even on a `PASS`. It matters most with `STATUS: BLOCKED` (Step 3e).

**Existence of a result file is not liveness.** Any runner implementing this contract MUST treat a step or remediation whose backing process is no longer alive and which produced no five-line report as `STATUS: FAIL` — never leave it indefinitely as `running`/`remediating` (`RATIONALE.md`).

Wait for the subagent to finish. Append its five-line result under the step's heading in `$RUNLOG`. Show the user one line — `✅/❌ <id> [<agent_type>]: <SUMMARY>` — then the running launch tally: `~/.claude/skills/lib/spawn-tally.sh "$RUNLOG"`.

### e. Failure gate (applies to b–d)
If a step's result `STATUS` is not `PASS` (or an interactive step is abandoned):
- `STATUS: BLOCKED` → always take the `BLOCKED` handling below, even when `stop_on_fail` is `false`. `stop_on_fail` softens *failures*; it never authorizes sailing past an unanswered decision (AUTHORING.md § Interaction contract). Once the memos are resolved and the step re-run, a still-failing `stop_on_fail: false` step is recorded-and-continued like any other.
- Else `stop_on_fail: false` → record it and continue.
- Otherwise branch on `STATUS`:

  **`STATUS: BLOCKED`** — the subagent raised decision memos instead of guessing and named them on `DECISIONS`. Isolated subagents have no AskUserQuestion, so you are the interactive seat: resolve them now per **AUTHORING.md § Decision memos** (`lib/decide.sh list open`, present each via AskUserQuestion, `resolve <id>` with the answer on stdin). Presenting **ends the turn** — wait for the actual reply.

  Then **re-run the SAME step** — same spawn as 3d, same `args` — and re-enter this gate with its result. Do not advance, and do not restart from Step 0: this is the minimal resume scope, and there is no `/orch-ui resume` mode for re-entering a past `$RUNLOG`. If `list open` is empty despite `BLOCKED`, treat it as an unremediated FAIL and halt.

  **`STATUS: FAIL` with `remediate: {skill, max}` declared** — bounded remediation:
  1. Track the round counter in `$RUNLOG` (`<id>: remediation round N/max`), reading back what's logged before incrementing so a compaction can't lose count.
  2. Append `SPAWN: <id>-remediate agent_type=<agent_type>`, then spawn ONE subagent for `remediate.skill` — same isolation and five-line contract as 3d — substituting `$TASK` into `remediate.args` and passing the failing step's `ARTIFACT` path.
  3. Re-run the gated step to re-verify. Only a fresh `PASS` from the gate counts; the remediation subagent's own say-so never does.
  4. Log the round and show the same one-line-plus-tally format as 3d. Then: `PASS` → continue. `BLOCKED` → the handling above. `FAIL` below `max` → repeat from (2). `FAIL` at `max` → resolve any open memos and re-run the gate once; whatever it reports is terminal — never re-enter the loop with a fresh cap.

  **`STATUS: FAIL` with no `remediate`, or terminal after the above** → **halt the cycle.** Tell the user which step stopped it, its `FOLLOWUP` and artifact path, and that later steps did not run. Spawn no further subagents.

## Step 4: Finish

Print a compact summary table: `step | status | artifact`. Point the user at `$RUNLOG`. Do not dump artifact contents.

Then print the per-run launch tally, and release the sentinel from Step 1:
```bash
~/.claude/skills/lib/spawn-tally.sh "$RUNLOG"
# Release on EVERY exit from this skill, not just this step: a halt at the failure
# gate, an open decision memo, and cap exhaustion all end the cycle too. A
# sentinel left behind suppresses per-skill logging until it ages out, so hand-run
# work in that window goes unrecorded. Staleness-bounded (6h) because this is
# exactly the step a halt skips.
source ~/.claude/skills/lib/runlog.sh
runlog_cycle_end
```

## Rules

- Never run a step before the user confirms the cycle-type (Step 0).
- You never edit code, run a skill yourself, or read a full artifact. One subagent per isolated step — isolation is the whole point.
- Never skip the failure gate. A failed gate step halts the run (unless bounded remediation is declared and still has rounds left, or a `BLOCKED` step's memos still need answers — Step 3e).
- Open decision memos and cap-exhaustion end the turn — the same rule from AUTHORING.md § Interaction contract applies to you as orchestrator: never default, never treat a quiet user as approval, never spawn more subagents "to fill the wait" while a question is outstanding.
- Keep your own messages short: the confirmation, status lines, and the final table.
