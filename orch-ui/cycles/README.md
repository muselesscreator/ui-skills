# Cycles for `/orch-ui`

`/orch-ui [task]` selects a **cycle-type** (guessing from your message, then
confirming with you), and runs that cycle's steps in `<cycle>.md` **in order**,
each step in its own **isolated subagent context**. The orchestrator
(`~/.claude/skills/orch-ui/SKILL.md`) stays thin — it holds only each step's
status, artifact path, and a one-line summary. Steps hand off through
`~/.claude/skill-output/$REPO/$BRANCH/`, which the skills read and write themselves.

## Mental model

- **`/orch-ui`** = the intentional trigger you type. Runs inline, stays thin, and
  confirms the cycle-type before doing anything.
- **Subagent** (one per step) = the context isolation. Each step starts fresh and
  returns only a 4-line result. (The exception: `interactive` steps run in the
  main session because they need you.)
- **Skill** = the reusable work unit a step invokes. Skills stay usable standalone.

This is why "commands instead of skills" alone doesn't isolate context — commands
and skills both run inline. Subagents are what isolate; `/orch-ui` just sequences
them.

## Defining a cycle-type

Create `~/.claude/skills/orch-ui/cycles/<name>.md` with a `name` + `description` in frontmatter
(used when `/orch-ui` lists and guesses cycle-types) and a `steps:` list:

```yaml
steps:
  - id: plan            # short label
    skill: plan-ui      # skill the step invokes
    args: "$TASK"       # arg string; $TASK = the task text you pass / confirm
    scope: global       # global (~/.claude/skills, Skill tool) | repo (the triggering repo's own skills)
    interactive: false  # true → runs in the main session (needs the human), not isolated
    stop_on_fail: true  # default true — non-PASS halts the run
    stub: false         # true → step is skipped (not yet implemented)
    note: ...            # human note (ignored by the orchestrator)
```

- `$TASK` is the task text you pass to `/orch-ui` (or confirm at the prompt).
- A step whose skill picks up prior output (e.g. `impl-ui` with `"use plan"`) needs
  no explicit wiring — the skills already resolve the latest artifact themselves.
- **`scope: repo`** resolves the skill from the triggering shell's current repo —
  `<repo>/.agent/skills/<skill>/SKILL.md` then `<repo>/.claude/skills/<skill>/SKILL.md`.
  If the repo doesn't have it, the step is skipped. Use this for repo-owned tooling
  (e.g. a repo's own `wiki-ingest`, `commit`, or `create-pr`).
- **`interactive: true`** runs the step in the main session instead of an isolated
  subagent — for steps that need live back-and-forth (e.g. a voice braindump).
- Set `stub: true` for steps whose skill isn't built yet; `/orch-ui` skips them.
- Set `stop_on_fail: false` for non-gating steps that shouldn't halt the run.

## Cycle-types

- **feature-cycle** — plan → impl → validate (gate) → cleanup → commit →
  braindump (repo-local, interactive) → ingest (repo-local). The UI feature/ticket loop.
