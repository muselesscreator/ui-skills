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
2b. **Normalise `$TASK` to the bare requirement** before substituting it anywhere. Strip any leading skill-invocation preamble — `Invoke the <skill> skill with arguments:`, `/<skill>`, `run <skill> on`, `use <skill> to`. Steps that treat `$TASK` as the requirements spec (`validate-ui`) will otherwise grade the implementation against an instruction to invoke a skill: on `dev-screen/home-cleanup` all three of analyze/plan/validate received `args` beginning "Invoke the analyze-task skill with arguments: …". Strip only a leading preamble, never text that could be a requirement, and show the normalised task in the confirmation below so the user can correct it.
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
> — If `scope: global`: **Invoke the `<skill>` skill** (Skill tool) with arguments: `<resolved args>`. If you cannot invoke it as a skill, read and follow `~/.claude/skills/<skill>/SKILL.md`.
> — If `scope: repo`: **Read and follow `<SKILLFILE>`** (a repo-local skill) with arguments: `<resolved args>`.
> The skill reads any prior step's output from `~/.claude/skill-output/<REPO>/<BRANCH>/` itself and writes its own artifact there. Do the full work it describes.
> When done, reply with EXACTLY these five lines and nothing else:
> `STATUS: PASS | FAIL | BLOCKED`
> `ARTIFACT: <absolute path to the artifact the skill wrote, or - if none>`
> `SUMMARY: <one sentence>`
> `FOLLOWUP: <what the next step or the human must know, or ->`
> `DECISIONS: <comma-sep decision-memo ids the skill raised via lib/decide.sh, or ->`

The `DECISIONS` line is additive to the original four-line contract — existing cycles that don't care about it still parse unchanged. It matters most paired with `STATUS: BLOCKED` (the skill couldn't proceed and is waiting on an answer — see Step 3e), but note any ids raised in passing even on a `PASS`.

Any runner implementing this contract MUST treat a step or remediation whose backing process is no longer alive and which produced no five-line report as `STATUS: FAIL` — never leave it indefinitely as `running`/`remediating`. **Existence of a result file is not liveness.** On `dev-screen/home-cleanup` a remediation wrapper died on an unrelated crash while its headless session kept running for ~20 more minutes and did emit a valid `STATUS: PASS` that nothing captured; the step showed "Remediating" until a human spent 84 turns hand-patching `manifest.json`.

Wait for the subagent to finish. Append its five-line result under the step's heading in `$RUNLOG`. Show the user one line: `✅/❌ <id> [<agent_type>]: <SUMMARY>`, followed by the running launch tally so far this run: `grep '^SPAWN:' "$RUNLOG" | sed -E 's/.*agent_type=//' | sort | uniq -c | sort -rn` (e.g. `Launches so far — general-purpose: 2, Plan: 1`).

### e. Failure gate (applies to b–d)
If a step's result `STATUS` is not `PASS` (or an interactive step is abandoned):
- If `STATUS` is `BLOCKED` → always take the `BLOCKED` handling below, even when `stop_on_fail` is `false`. An open decision memo is a hard stop everywhere (AUTHORING.md § Interaction contract; Ben's silence-is-never-consent rule) — `stop_on_fail` softens *failures*, it never authorizes sailing past an unanswered decision. Once the memos are resolved and the step re-run, a still-failing `stop_on_fail: false` step is then recorded-and-continued like any other non-critical failure.
- Else if `stop_on_fail` is `false` → record it and continue (a wiki hiccup here shouldn't stop the run).
- Otherwise, branch on `STATUS`:

  **`STATUS: BLOCKED`** — the subagent raised one or more decision memos (via `lib/decide.sh`) instead of guessing, and its `DECISIONS` line names them. Isolated subagents never have AskUserQuestion (see Gotchas) — the orchestrator is the interactive seat, so it resolves them now:
  1. Run `lib/decide.sh list open` (scoped to `$OUT`).
  2. If it lists any open memos: read each memo file and present it to the user via AskUserQuestion — recommendation first, lettered options, per AUTHORING.md § Interaction contract. **This ends the turn.** No defaults, no proceeding because the user "hasn't answered yet" (Ben's hard rule) — wait for the actual reply.
  3. For each answer, write the resolution with `lib/decide.sh resolve <id>` (pipe the chosen option/text on stdin).
  4. Once every listed memo is resolved, **re-run the SAME step** (same spawn as 3d, same `args`) and re-enter this gate with its new result. Do not advance to the next step yet and do not restart the cycle from Step 0 — this is the MINIMAL resume scope: same run, same step, no `/orch-ui resume` mode for re-entering a past `$RUNLOG` in a new session.
  5. If `list open` comes back empty despite `STATUS: BLOCKED` (nothing left to resolve), fall through to the halt below — treat it like an unremediated FAIL.

  **`STATUS: FAIL`, and the step's cycle entry declares `remediate: {skill, max}`** — bounded remediation before giving up:
  1. Track a round counter for this step in `$RUNLOG` (e.g. `<id>: remediation round N/max`) — read back whatever is already logged before incrementing, so a mid-run compaction never loses count.
  2. Before spawning, append `SPAWN: <id>-remediate agent_type=<agent_type>` to `$RUNLOG` (same `agent_type` as the gated step, unless `remediate` specifies its own). Spawn ONE subagent, same isolation and five-line contract as 3d, for `remediate.skill`, substituting `$TASK` into `remediate.args` and passing it the failing step's `ARTIFACT` path so it knows what to fix (e.g. validate's remediation reads "fix validation gaps — read the latest validation-report").
  3. Re-run the gated step itself (same skill/args as the original 3d spawn) to re-verify. Never accept the remediation subagent's own say-so — only a fresh `PASS` from the gate step counts as fixed.
  4. Append the round and its outcome to `$RUNLOG`, and show the user the same one-line-plus-tally format as 3d (`✅/❌ <id>-remediate [<agent_type>]: <SUMMARY>`, then the running launch tally).
     - `PASS` → continue the cycle normally.
     - `BLOCKED` → jump to the `BLOCKED` handling above.
     - `FAIL` and the round counter is still below `max` → repeat from (2).
     - `FAIL` and the round counter has reached `max` (cap exhaustion) → run `lib/decide.sh list open`; if it lists open memos, resolve them (steps 2–4 of the `BLOCKED` handling above) and re-run the gate step once more — whatever it reports next is terminal, do not re-enter the remediation loop with a fresh cap. If there are no open memos at cap, fall through to the halt below.

  **`STATUS: FAIL` with no `remediate` declared, or terminal after the above** → **halt the cycle.** Tell the user which step stopped it, the `FOLLOWUP`, and the artifact path, and that later steps did not run. Spawn no further subagents.

## Step 4: Finish

Print a compact summary table: `step | status | artifact`. Point the user at `$RUNLOG`. Do not dump artifact contents.

Then tally subagent launches by type from the `SPAWN:` lines logged during Step 3:
```bash
grep '^SPAWN:' "$RUNLOG" | sed -E 's/.*agent_type=//' | sort | uniq -c | sort -rn
```
Print this as a one-line-per-type list, e.g. `general-purpose: 4, Plan: 1`. This count is per-run only (not cumulative across cycles).

## Rules

- Never run a step before the user confirms the cycle-type (Step 0).
- You never edit code, run a skill yourself, or read a full artifact. One subagent per isolated step — isolation is the whole point.
- Never skip the failure gate. A failed gate step halts the run (unless bounded remediation is declared and still has rounds left, or a `BLOCKED` step's memos still need answers — Step 3e).
- Open decision memos and cap-exhaustion end the turn — the same rule from AUTHORING.md § Interaction contract applies to you as orchestrator: never default, never treat a quiet user as approval, never spawn more subagents "to fill the wait" while a question is outstanding.
- Keep your own messages short: the confirmation, status lines, and the final table.
