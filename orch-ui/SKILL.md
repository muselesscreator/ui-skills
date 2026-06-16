---
name: orch-ui
description: Orchestrates a multi-step UI work cycle. On invocation it selects the cycle-type (e.g. feature-cycle) — guessing from your message if one is given — CONFIRMS the choice with you, then runs each step in its own isolated subagent, handing off through files. The thin coordinating layer over plan/impl/validate/cleanup/commit/wiki skills so you don't manually clear and re-trigger each step. Use when the user asks to run a UI cycle, orchestrate a feature, or types /orch-ui.
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
3. **Confirm with the user and wait for a reply.** Present the guess and the alternatives — e.g.:

   > Cycle: **feature-cycle** — _<its description>_
   > Task: _<$TASK, or "(none given)">_
   > Steps: analyze → plan → impl → validate → cleanup → commit → braindump → ingest
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
- `stop_on_fail` — `true` (default) or `false`
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
Substitute `$TASK` into `args`, then spawn ONE subagent with the **Task** tool using `subagent_type` = the step's `agent_type` (default `general-purpose`). If the step has a `model`, pass it as the Task tool's `model` (`haiku`/`sonnet`/`opus`); if absent, omit `model` so the subagent inherits the session model. Give it exactly this prompt:

> You are running one isolated step of the `<cycle>` cycle — repo `<REPO>`, branch `<BRANCH>`.
> — If `scope: global`: **Invoke the `<skill>` skill** (Skill tool) with arguments: `<resolved args>`. If you cannot invoke it as a skill, read and follow `~/.claude/skills/<skill>/SKILL.md`.
> — If `scope: repo`: **Read and follow `<SKILLFILE>`** (a repo-local skill) with arguments: `<resolved args>`.
> The skill reads any prior step's output from `~/.claude/skill-output/<REPO>/<BRANCH>/` itself and writes its own artifact there. Do the full work it describes.
> When done, reply with EXACTLY these four lines and nothing else:
> `STATUS: PASS | FAIL | BLOCKED`
> `ARTIFACT: <absolute path to the artifact the skill wrote, or - if none>`
> `SUMMARY: <one sentence>`
> `FOLLOWUP: <what the next step or the human must know, or ->`

Wait for the subagent to finish. Append its four-line result under the step's heading in `$RUNLOG`. Show the user one line: `✅/❌ <id>: <SUMMARY>`.

### e. Failure gate (applies to b–d)
If a step's result `STATUS` is not `PASS` (or an interactive step is abandoned):
- If `stop_on_fail` is `false` → record it and continue.
- Otherwise → **halt the cycle.** Tell the user which step stopped it, the `FOLLOWUP`, and the artifact path, and that later steps did not run. Spawn no further subagents.

## Step 4: Finish

Print a compact summary table: `step | status | artifact`. Point the user at `$RUNLOG`. Do not dump artifact contents.

## Rules

- Never run a step before the user confirms the cycle-type (Step 0).
- You never edit code, run a skill yourself, or read a full artifact. One subagent per isolated step — isolation is the whole point.
- Never skip the failure gate. A failed gate step halts the run.
- Keep your own messages short: the confirmation, status lines, and the final table.
