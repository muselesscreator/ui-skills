---
name: plan-ui
description: Pre-implementation planning for UI work. Loads repo learnings, reads relevant code, and produces a focused implementation plan with file placements, patterns to follow, and test impact analysis. Use when planning a UI feature, deciding where files should go, or choosing which patterns to follow before writing code.
version: 1.0.0
triggers:
  explicit:
    - plan ui
    - plan this feature
    - plan this change
    - plan before I implement
  strong_intent:
    - how should I approach this
    - where should I put this
    - what pattern should I follow for
  question_form:
    - how do I implement
    - where does this go
    - what's the right pattern for
confidence_threshold: 75
---

# plan-ui

**Arguments**: $ARGUMENTS — description of the UI task to plan

This skill owns the **planning judgment**: which files the change actually touches, the approach, the patterns to follow, the test impact, and the open questions. The fixed facts around the task — learnings, in-flight branch state, tooling constraints, task classification, user-named files — are gathered upstream by `/analyze-task` and consumed in Step 1. This skill does not re-derive them; it reasons over them and discovers the rest.

**Out of scope — presentation-layer decisions.** Semantic element selection (`div` vs `span` vs `button` vs list/landmark elements), the CSS approach, and `className`/token composition are **not** planning judgments — they are deferred to `/impl-ui`'s presentation pass. The plan may *name* the design-system or styling pattern to follow as a reference (so impl knows which convention applies), but it does **not** resolve element-level markup or styling. If a presentation choice genuinely blocks the structure (e.g. a layout primitive that dictates the component tree), raise it as an Open Question rather than deciding it here.

## Step 1: Load the Task-Context Artifact

```bash
source ~/.claude/skills/lib/skill-env.sh   # sets REPO, BRANCH, OUT, SRC, …
ANALYSIS=$(ls -t "$OUT"/analysis-*.md 2>/dev/null | head -1)
```

**If an analysis artifact exists** (`$ANALYSIS` is non-empty): read it. It supplies — already distilled — the task classification, mentioned files, in-flight conflicts, tooling constraints (TS/ESLint/Prettier), and relevant learnings. Trust it; do not re-query QMD or re-read tooling config. Carry its **Tooling Constraints** and **Gotchas** forward verbatim into the plan, and treat its **In-Flight Conflicts** as already-accounted-for.

**Fallback — no analysis artifact** (standalone `/plan-ui` with no prior `/analyze-task`): invoke `/analyze-task` with `$ARGUMENTS` first, then read the artifact it writes. If that is not possible, do the gathering inline — load learnings (QMD `wiki` collection for work repos, else `~/.claude/repo-learnings/$REPO/`), snapshot the branch diff against `main`, and read TS/ESLint/Prettier config — before continuing. Note in the plan that it ran without a pre-built analysis.

**Seed already-answered questions from resolved decision memos** (a prior `/plan-ui` run on this branch may have raised Open Questions that are now answered):
```bash
~/.claude/skills/lib/decide.sh list resolved
```
Read each listed memo under `$OUT/decisions/` and its `## Resolution` block. Treat these as settled — do not re-raise them as Open Questions in Step 4; instead fold the resolution into the relevant plan section (Approach, Files, Patterns, whichever it bears on), citing the memo id inline (e.g. "per `d002`, resolved: …").

## Step 2: Read Relevant Existing Code

Now do the discovery the analysis deliberately left open — **which files this change actually touches.** Starting from the mentioned files and reference implementations in the artifact, find and read:
- The most relevant existing feature for pattern reference (use reference implementations from `index.md` if relevant)
- The files that will be modified
- Any parent views or layouts that affect where this fits

These reads land in the planning session and are the one deliberate residual to the context-budget effort (Step 3's test reads are delegated; these are not, because the planning judgment needs the source in context). Keep it bounded: read the few files you genuinely need to place the change and pick patterns — not the whole feature tree. If you find yourself opening more than a handful, delegate the survey to a fresh `general-purpose` agent and take back a summary instead.

## Step 3: Summarize Existing Tests for Affected Files

Run the affected-test finder on the files identified in Step 2:

```bash
~/.claude/skills/lib/find-affected-tests.sh apps/app/src/Foo.tsx packages/ui/src/Bar.ts
# (substitute the actual planned file paths)
```

It prints `DIRECT_UNIT` / `INDIRECT_UNIT` and `DIRECT_E2E` / `INDIRECT_E2E`.

**Delegate reading to a fresh subagent — do not read test files inline.** E2E specs and page objects can be 400-600 lines each; loading them directly would bloat the planning context with content that only needs to be summarized. Spawn a fresh read-only analysis agent with the reported file paths and the task below.

This is a global, repo-agnostic skill, so resolve the agent type with a fallback — prefer a repo's tuned `codebase-analyzer` (the incentives repo ships one) and otherwise use `general-purpose` constrained read-only by the task prompt. Detect by `name:` frontmatter (Claude Code resolves by `name:`, not filename, so this tolerates the `codebase-analyzer..md` double-dot in incentives):
```bash
grep -rqlE "^name:[[:space:]]*codebase-analyzer([[:space:]]|$)" .claude/agents/ 2>/dev/null && ANALYZER=codebase-analyzer || ANALYZER=general-purpose
```
Spawn a fresh `$ANALYZER` agent with the reported file paths and this task:

> Read these test files: [DIRECT_UNIT paths], [INDIRECT_UNIT paths], [DIRECT_E2E paths + their associated page objects]. For each unit test file, return: (1) what cases are currently covered, (2) which tests would break given [describe the planned change in 1 sentence], (3) any mocks or fixtures that reference things being changed. For each E2E spec, return: (1) which user flows touch the affected component, (2) which flows would break due to the planned change. Return a compact structured summary — do not include raw file contents or long code excerpts.

If no unit tests were reported for a modified file, record:
```
⚠ No unit tests found for {file} — new tests will need to be written from scratch.
```

If no E2E specs were reported:
```
⚠ No E2E coverage found for this feature area — consider whether a new spec is needed.
```

Carry the agent's summary (not raw file contents) into the Test Plan section.

## Step 4: Produce Implementation Plan

Output a structured plan:

```
## Implementation Plan: {task description}

### Approach
[1-2 sentences on the overall approach]

### Out of Scope (What We're NOT Doing)
- [explicitly excluded work, and why — e.g. a seam left for a later change, or a paradigm deliberately not ported]
- [another exclusion, or omit the section body only if truly nothing is worth calling out — prefer stating at least one]

### Files to Create
- {path} — {purpose}
- {path} — {purpose}

### Files to Modify
- {path} — {what changes and why}

### Patterns to Follow
- [specific pattern from learnings, with reference file]
- [specific pattern from learnings, with reference file]
- [the design-system / styling pattern that applies, named with its reference file — so impl's presentation pass knows the convention. Do NOT spell out element-level markup or class composition here; that is impl-ui's call.]

### Gotchas to Avoid
- [specific gotcha relevant to this task]
- If this plan adds or touches a timing/lifecycle edge that is already tracked elsewhere (an existing timer, latch, or hook), name the single owner explicitly, or raise it as an Open Question instead of adding a parallel tracker.

### Tooling Constraints
**TypeScript:** [strict flags that affect this implementation — e.g., "strictNullChecks: all optional props need explicit undefined handling"]
**ESLint:** [rules that apply to planned code — e.g., "import/order enforced: group third-party before internal", "no-explicit-any: use unknown + type guard instead"]
**Prettier:** [non-default settings if any, or "defaults apply"]

### Test Plan

**Unit tests — updates required:**
- {test file}: {specific test(s) that break} — {what needs to change and why}
- {test file}: extend {test name} to cover {new behavior}
- (or "No existing unit tests affected")

**Unit tests — new coverage needed:**
- {path/to/Component.test.tsx}: cover {behavior/case}
- (or "None — existing coverage is sufficient")

**E2E tests — updates required:**
- {spec file}: {flow that breaks} — {what needs to change}
- (or "No existing E2E tests affected")

**E2E tests — new coverage needed:**
- {path/to/feature.spec.ts}: cover {user flow}
- (or "None — existing coverage is sufficient")

### Open Questions
[Any decisions that require user input before implementation]
```

Keep the plan concrete and short. Reference specific file paths wherever possible. Do not restate the steering docs — reference what the code actually does.

## Step 5: Write Output File

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/plan-$TS.md"   # ← write the plan to this exact path
```

Write the full implementation plan produced in Step 4 to the path echoed above. This file is read by `/impl-ui` when invoked with `use plan` — it picks up the most recent `plan-*.md` in the branch directory.

Use the Write tool when it's available. **If you are running without a Write tool** (e.g. spawned as the read-only `Plan` agent type by `/orch-ui`), persist the same content with a quoted Bash heredoc instead — the quoted delimiter prevents `$`/backtick expansion of the plan body (source in the same block so `$OUT`/`$TS` are set):

```bash
source ~/.claude/skills/lib/skill-env.sh
cat > "$OUT/plan-$TS.md" <<'PLAN_EOF'
<full implementation plan markdown>
PLAN_EOF
```

**Then persist the plan's file list** to `$OUT/plan-files.txt` — one repo-relative path per line, every file the plan creates or modifies, plus any directory the plan creates (with a trailing slash, so files that appear inside it later are recognized as in-scope). Downstream steps use this via `lib/plan-scope-check.sh` to tell a real collision from unrelated parallel work on the same branch, instead of each re-scanning the whole dirty tree:

```bash
source ~/.claude/skills/lib/skill-env.sh
cat > "$OUT/plan-files.txt" <<'FILES_EOF'
client/src/components/deck/
client/src/lib/api.ts
FILES_EOF
```

## Step 6: Publish the Plan Artifact

**Always** present the full plan as an HTML artifact — the plan file plus a tiny inline summary is not enough. The page is produced by a pre-designed template, so this costs almost no context: **do not author any HTML and do not load artifact-design** — run the render script and publish its output unchanged.

```bash
source ~/.claude/skills/lib/skill-env.sh
~/.claude/skills/lib/render-plan-artifact.sh "$(ls -t "$OUT"/plan-*.md | head -1)"
# prints the generated .html path
```

The script wraps the plan markdown into `plan-ui/plan-template.html` (title, repo/branch/date chips, styled sections, Open Questions callout — rendered client-side by the template's inline JS).

Then call the **Artifact tool** with the printed `.html` path:
- `favicon`: `"📐"` (keep this stable across plan artifacts)
- `description`: one sentence — what the plan implements
- title comes from the `<title>` the script injected; don't pass one

Each plan is a new timestamped file, so each `/plan-ui` run mints its own artifact URL — that's intended.

**No Artifact tool available** (e.g. spawned as the read-only `Plan` agent by `/orch-ui`): still run the render script, and put the generated `.html` path prominently in your output so the coordinator or user can publish it with the Artifact tool. Never skip the render.

## Step 7: Final User-Facing Summary

After publishing, print a summary to the conversation. The artifact carries the full plan layout; the inline message exists so pending decisions can be answered in-chat without opening anything.

**Also persist each Open Question as a decision memo.** This is additive — it does not replace the inline listing below; it makes each question durable and resumable across sessions per AUTHORING.md's "Decision memos & per-repo review heuristics" convention.

Dedupe-before-raise:
```bash
source ~/.claude/skills/lib/skill-env.sh
~/.claude/skills/lib/decide.sh list open
```
For each Open Question not already covered by an existing open memo (extend that memo instead of raising a near-duplicate):
```bash
ID=$(~/.claude/skills/lib/decide.sh next-id)
mkdir -p "$OUT/decisions"
cat > "$OUT/decisions/$ID-plan-ui-{slug}.md" <<'MEMO_EOF'
---
id: {ID}
title: {question, one line}
status: open
raised_by: plan-ui
raised_at: {ISO-8601 datetime}
resolution:
---

## Context
{the question's context, verbatim from the plan}

## Options
{lettered options per AUTHORING.md's Interaction contract — A) B) C) …, recommendation first, final ―) none of these — add context}
{For any option that trades off against a prerequisite this memo's own Context names as missing (e.g. an unmeasured value, an untested assumption): add "Risk if chosen without it: {one line}" under that option, so resolving it without meeting the prerequisite requires engaging with the tradeoff, not just picking a letter.}
MEMO_EOF
```

**Rules:**
- **Always list every Open Question inline, in full** — verbatim from the plan, numbered, with any context/options needed to answer. Never write "see the plan for questions" or "open the artifact to review questions."
- Print a compact summary using this shape:

```
Plan artifact: {artifact URL}
Plan file: {relative path to plan file}

**Approach:** {one sentence}

**Scope:** {N files to create, M files to modify}

**Open Questions** ({count}):
1. {full question text, including any options or trade-offs}
2. {full question text, including any options or trade-offs}
...

(or "**Open Questions:** none — ready to implement" if there are zero)
```

If there are open questions, end the message by asking the user to answer them before `/impl-ui` runs. Do not proceed to implementation while questions are unanswered.

**Resolve in this same conversation the moment the user answers.** Per AUTHORING.md's Interaction contract, a memo answered here must be recorded here — never left for the dev-screen UI's Resolve-decision card to catch up. When the user's next reply answers one or more Open Questions (plain chat text, not necessarily one AskUserQuestion per question), immediately, before doing anything else:
```bash
~/.claude/skills/lib/decide.sh resolve {id} <<'EOF'
{the user's chosen answer, one line}
EOF
```
Do this for every memo the reply resolves, then fold each resolution into the plan (same as Step 1's "seed already-answered questions" handling) before continuing to `/impl-ui` or any further work. If the reply only partially answers the open questions, resolve the ones it does answer and re-ask the rest — don't hold all of them open waiting for a single complete reply.
