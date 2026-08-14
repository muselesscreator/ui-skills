---
name: impl-ui
description: Implements a UI feature or change as a thin orchestrator. Reads any existing plan, writes a compact implementation brief to disk, then spawns fresh disposable workers to do the file-reading and implementation (one per logical file group, a sonnet presentation pass, and a read-only standards/test-gap check) so the calling session stays lean. Use when building a new UI feature, modifying an existing component, or executing a /plan-ui output.
version: 1.2.0
triggers:
  explicit:
    - implement ui
    - build this feature
    - implement this change
    - impl ui
  strong_intent:
    - go ahead and build it
    - implement what we planned
    - write the code for
confidence_threshold: 75
---

# impl-ui

**Arguments**: $ARGUMENTS — task description or "use plan" to pick up from /plan-ui output

**Context-budget constraint — this skill runs in the calling session.** Every token read here lands in the user's context window and stays. The orchestrator (this skill) must never read the files that implementation workers write. It passes file paths; workers do the reading. The goal is a lean orchestrator (~10k context added) that spawns disposable fresh workers (~30-50k each, then gone).

**Agent types.** Resolve once in Step 1 and reuse for every spawn — this is a global skill, so it prefers a repo's tuned agents and falls back when absent (AUTHORING.md § Global-skill hygiene):
```bash
BUILDER=$(~/.claude/skills/lib/resolve-agent.sh builder)
ANALYZER=$(~/.claude/skills/lib/resolve-agent.sh codebase-analyzer)
```
- `$BUILDER` — writers, need Edit/Write. On the `general-purpose` fallback, pass `model: sonnet`.
- `$ANALYZER` — read-only, constrained by its task prompt; the orchestrator writes any report. Never substitute `Explore`, which reads excerpts rather than whole files.

## Step 1: Read Plan + Write Implementation Brief

```bash
source ~/.claude/skills/lib/skill-env.sh
```

If $ARGUMENTS contains "use plan": find the most recent plan file:
```bash
ls -t "$OUT"/plan-*.md 2>/dev/null | head -1
```
Read it. If $ARGUMENTS contains a file path: read that file. Otherwise: treat $ARGUMENTS as the task description — gather the bare minimum needed to write the brief (task description, intended files, known patterns/gotchas).

**Refuse to start if the plan's decisions are still open.** Before anything else:
```bash
~/.claude/skills/lib/decide.sh list open
```
If this plan's memos appear, **stop here** — no brief, no workers. Surface their ids and titles and end the turn (AUTHORING.md § Interaction contract).

**Check for collisions against the plan's own files — not the whole dirty tree.**

```bash
~/.claude/skills/lib/plan-scope-check.sh   # exit 1 + paths = real collision; exit 0 = clear
```

Escalate **only** on a non-empty result, quoting exactly those paths. A dirty tree that doesn't intersect the plan is unrelated parallel work on a shared branch — proceed, and don't mention it as a blocker. On a real collision, raise one memo offering commit-the-in-flight-work-first vs implement-on-top, then pause. Never run your own unscoped `git status` to second-guess this (`RATIONALE.md`).

**Honor resolved decisions — do not default to the plan's recommendation.** If the plan carries memos, read what was actually decided:
```bash
~/.claude/skills/lib/decide.sh list resolved
```
Read each resolved memo's `## Resolution` block and parse the **actual answer chosen** — a human may have picked an option other than the plan's stated recommendation. Carry the chosen option into the brief (Approach, Files, or Patterns, whichever it bears on) instead of the plan's original recommendation, citing the memo id. Never silently fall back to "the plan said X" when a memo shows the human picked Y.

**Task-context artifact.** Check for `$OUT/analysis-latest.md` (written by `/analyze-task`; ≤150 lines, cheap to read). If present, read it and carry its **Tooling Constraints**, **Gotchas**, and **Relevant Learnings** into the brief — do not re-derive them. When a plan exists it already carries these forward, so the artifact is a cross-check; when there is no plan it is the primary source. Only run `/analyze-task` fresh if neither a plan nor an analysis artifact exists.

**Do not query the wiki or read reference implementation files at this stage.** That work is delegated to implementation workers who start fresh — they load only what their specific files need. Loading wiki content here would bloat the orchestrator's context for the entire session.

Immediately write an **implementation brief** to disk:

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/impl-brief-$TS.md"   # ← write the brief to this exact path
```

Brief format (target: ≤ 300 lines; every worker will read this file cold):

```markdown
## Implementation Brief: {task description}

### Approach
{1-2 sentences on the overall strategy}

### Files
| Path | Action | Group |
|------|--------|-------|
| {path} | create | {A/B/C} |
| {path} | modify | {A/B/C} |

Groups: split by logical boundary — new files vs. modifications, or by layer (data/types vs. components vs. barrel/exports). Assign each file to exactly one group. A group = one worker agent.

### Patterns to Follow
- {pattern name}: reference file at `{path}` — worker should read this file to understand the convention
- {CSS/styling pattern}: reference at `{path}`
- {data-layer pattern}: reference at `{path}`

### Gotchas
- {gotcha from plan or prior knowledge}

### Tooling Constraints
**TypeScript:** {strict flags that apply}
**ESLint:** {rules that matter for planned code}
**Prettier:** {non-defaults or "defaults apply"}

### Cross-Group Dependencies
{If group A creates a file that group B imports, name the export/type here so workers can anticipate it without waiting. If none, write "none".}
```

## Step 2: Spawn Implementation Workers

For each group in the brief, spawn one **fresh** `$BUILDER` agent (never a fork; `model: sonnet` on the fallback). Pass each agent:
- The path to the implementation brief (they read it from disk)
- The list of files in their group
- No file contents — they read their reference files themselves

Worker prompt template:
```
You are implementing part of a UI feature. Read the implementation brief at {brief_path} for context, approach, patterns, and gotchas.

Your group owns these files: {file list for this group}

For each pattern named in the brief's "Patterns to Follow" section that applies to your files, read the reference file at the path listed there to understand the convention before implementing. Query wiki (collections: ["wiki"]) if you need more detail on a named pattern.

Implement your files. At each meaningful deviation from the loaded patterns, note it inline:
  ⚠ Deviation: {description} — Reason: {why}

If you hit a genuine ambiguity the brief doesn't resolve (an architectural fork, not a style choice) — don't guess. Dedupe-check `~/.claude/skills/lib/decide.sh list open` first; if nothing covers it, get an id (`~/.claude/skills/lib/decide.sh next-id`) and write a memo to `$OUT/decisions/d{NNN}-impl-ui-{slug}.md` (frontmatter `id, title, status: open, raised_by: impl-ui, raised_at, resolution:`, then context + lettered options, recommendation first — per AUTHORING.md's Interaction contract). You have no AskUserQuestion here — leave the memo open, skip only the blocked file, keep implementing the rest of your group, and name the memo id in your summary.

Standards to check as you go:
- No `any` or unchecked type assertions
- No hardcoded user-facing strings (use i18n if the repo does)
- No business logic in presentational components
- No direct server-layer calls from components (go through data hooks)
- Imports ordered per project conventions

When done, return a compact summary: files written, patterns followed, any deviations noted, and any decision memo ids raised (or "none").
```

Wait for all workers to complete before proceeding.

**Decision gate — resolve here.** After workers finish:
```bash
~/.claude/skills/lib/decide.sh list open
```
`impl-ui` runs in the calling interactive session, so a worker-raised memo is resolved right here rather than left open for a later surface (`RATIONALE.md`) — present each via AskUserQuestion and `decide.sh resolve {id}` with the answer on stdin, per **AUTHORING.md § Decision memos**. Then fold the resolution into a short addendum to the brief and respawn only the worker(s) that had blocked files, before Step 3.

**If no Agent tool is available** (spawned under a restricted agent type): run Step 2 inline — implement all files sequentially in this context, loading only the brief and per-file reference code. Note in the Step 5 report that it ran inline. Any ambiguity is then a direct AskUserQuestion (no worker to relay through) — ask and `decide.sh resolve` immediately, same as the decision gate above.

## Step 3: Presentation-Layer Pass

Spawn one fresh `$BUILDER` agent (`model: sonnet`). Pass it:
- The implementation brief path (for conventions — the brief names the CSS/styling pattern and its reference file)
- The list of all files written by Step 2 workers

Prompt:
```
You are refining the presentation layer of already-implemented components.
Files: {paths from Step 2}
Read the implementation brief at {brief_path} — the "Patterns to Follow" section names the CSS/styling convention and its reference file. Read that reference file for the exact pattern. Follow it; do not invent your own.
Edit ONLY:
  - semantic element choice (div/span/button/ul/nav — prefer the most semantic, accessible element)
  - styling via the established pattern above
  - className / design-token composition
Do NOT change: data hooks, state, prop contracts, business logic, file structure.
If a presentation choice is a genuine ambiguity the brief's reference pattern doesn't resolve, don't invent a convention — raise a decision memo the same way (dedupe-check `decide.sh list open`, write to `$OUT/decisions/`, leave it open, name the id in your report).
Report the files you edited, any element/styling choice that was non-obvious, and any decision memo ids raised (or "none").
```

Sonnet, not haiku: presentation markup is standard implementation work, but accessibility semantics carry real judgment (AUTHORING.md § Model & effort tiering).

Run Step 2's decision gate on this worker's result before Step 4.

## Step 4: Fast Type Gate

Catch type errors **now**, before the behavioral-validation pass (`RATIONALE.md`).

Resolve the affected packages' filter flags, then run a scoped type-check:

```bash
~/.claude/skills/lib/cleanup-scope.sh
source ~/.claude/skills/lib/skill-env.sh
FILTERS=$(cat "$OUT/cleanup-scope-filters.txt" 2>/dev/null)
if [ -n "$FILTERS" ]; then pnpm $FILTERS type-check
else pnpm type-check; fi
```

- **Errors in files this implementation wrote or modified**: fix them before reporting. If the fix is mechanical (wrong import path, missing export, typo'd prop), fix inline. If it needs real rework, respawn the owning group's `$BUILDER` worker with the error list. Re-run the check until the implementation's own files are clean.
- **Pre-existing errors in untouched files**: do not fix here — that's `/cleanup-ui` work. Note them in the Step 5 report.

This is a **type gate only**. Lint, Prettier, dead code, and test fixes stay in `/cleanup-ui`; do not expand into them here.

## Step 5: Post-Implementation Report

Spawn a fresh `$ANALYZER` agent (read-only; the fallback `general-purpose` is constrained to read-and-report by the task below). Pass it the list of files written (paths only — the agent reads them). Task:

> Read these files: {list}. Check: (1) any `any` or unchecked type assertions, (2) hardcoded user-facing strings, (3) business logic in presentational components, (4) direct server-layer calls from components, (5) import ordering. Also list: what new unit tests are needed, what new E2E tests are needed, what existing tests are likely affected. Return a structured report.

Write the agent's findings to the impl-report path:

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/impl-report-$TS.md"   # ← write the report to this exact path
```

Print a final summary to the conversation:

```
## Implementation Complete

Files created:
- {path}

Files modified:
- {path}

Type gate: ✓ clean / ⚠ pre-existing errors noted (not from this change)
Standards check: {from check agent}

Test work needed:
- Unit: {list}
- E2E: {list}

Next steps:
- Run /write-unit-tests {path} to write unit tests
- Run /write-e2e-tests "{flow description}" to write E2E tests
- Run /cleanup-ui to lint/type-check
- Run /validate-ui "{original task description}" to confirm behavioral correctness
```

## Step 6: Surface New Learnings

This is a low-context step — do it inline (no subagent needed). Based on what the worker summaries and check report surfaced:

- **Work repo (has `./wiki/`)** — if any worker noted an undocumented trap, a `// HACK`/`// NOTE`/`// FIXME`, an undocumented pattern, or a non-obvious tooling fix, trigger `/wiki-braindump` to capture it. Do not hand-edit the wiki.

- **OSS/reference repo (no wiki)** — append new entries to the relevant flat file under `~/.claude/repo-learnings/$REPO/` (`gotchas.md`, `ui-patterns.md`, `standards.md`, `file-structure.md`), bumping `Last analyzed`.

If there is nothing new to add:
```
✓ No learnings updates — implementation followed established patterns.
```

```bash
# Record this run in the session runlog, so a skill invoked BY HAND is still a
# cycle /analyze-cycle can resolve. Silently no-ops when a cycle runner already
# logs this step. Guards + rationale: lib/runlog.sh. Re-sourcing skill-env.sh
# re-stamps $TS, so pass the impl-report path you actually wrote.
source ~/.claude/skills/lib/skill-env.sh
source ~/.claude/skills/lib/runlog.sh
runlog_append impl "PASS|FAIL|BLOCKED" "<impl-report path just written, or ->" \
  "<one-sentence summary>" "<test gaps or follow-ups, or ->" "<decision memo ids, or ->"
```
