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

This skill owns the **planning judgment**: which files the change touches, the approach, the patterns to follow, the test impact, the open questions. `/analyze-task` gathers the fixed facts upstream and Step 1 consumes them — reason over those, don't re-derive them.

**Out of scope — presentation-layer decisions.** Semantic element selection, the CSS approach, and `className`/token composition belong to `/impl-ui`'s presentation pass (`RATIONALE.md`). Name the design-system or styling pattern to follow and its reference file; do not resolve element-level markup. If a presentation choice genuinely dictates the component tree, raise it as an Open Question.

## Step 1: Load the Task-Context Artifact

```bash
source ~/.claude/skills/lib/skill-env.sh   # sets REPO, BRANCH, OUT, SRC, …
ANALYSIS=$(ls -t "$OUT"/analysis-*.md 2>/dev/null | head -1)
```

**If `$ANALYSIS` is non-empty**: read it. It already supplies the task classification, mentioned files, in-flight conflicts, tooling constraints, and relevant learnings — trust it rather than re-querying QMD or re-reading tooling config. Carry its **Tooling Constraints** and **Gotchas** into the plan verbatim; treat its **In-Flight Conflicts** as accounted for.

**No artifact** (standalone run): invoke `/analyze-task` with `$ARGUMENTS` and read what it writes. Failing that, gather inline — learnings (QMD `wiki`, else `~/.claude/repo-learnings/$REPO/`), the branch diff against `main`, TS/ESLint/Prettier config — and note that it ran without one.

**Seed settled questions.** Read every memo `~/.claude/skills/lib/decide.sh list resolved` names, under `$OUT/decisions/`. Fold each `## Resolution` into the section it bears on, citing the id inline ("per `d002`, resolved: …"), and do not re-raise it in Step 4.

## Step 2: Read Relevant Existing Code

Discover what the analysis deliberately left open — **which files this change actually touches.** From the artifact's mentioned files and reference implementations, find and read:
- The most relevant existing feature, for pattern reference
- The files that will be modified
- Any parent view or layout that affects where this fits

These reads are the one deliberate residual to the context budget; the planning judgment needs the source in context. Read only what you need to place the change and pick patterns — past a handful of files, delegate the survey to a fresh `general-purpose` agent and take back a summary.

## Step 3: Summarize Existing Tests for Affected Files

Run the affected-test finder on the files identified in Step 2:

```bash
~/.claude/skills/lib/find-affected-tests.sh apps/app/src/Foo.tsx packages/ui/src/Bar.ts
# (substitute the actual planned file paths)
```

It prints `DIRECT_UNIT` / `INDIRECT_UNIT` and `DIRECT_E2E` / `INDIRECT_E2E`.

**Delegate the reading — never read test files inline.** E2E specs and page objects run 400-600 lines each and only need summarizing. Resolve the agent type, then spawn one fresh read-only agent:

```bash
ANALYZER=$(~/.claude/skills/lib/resolve-agent.sh codebase-analyzer)
```

Give it this task:

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

Keep the plan concrete and short, with specific file paths. Reference what the code does, not the steering docs.

## Step 5: Write Output File

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/plan-$TS.md"   # ← write the plan to this exact path
```

Write the Step 4 plan to the path echoed above; `/impl-ui` picks up the most recent `plan-*.md` when invoked with `use plan`.

Use the Write tool if you have one. **Without it** (the read-only `Plan` agent under `/orch-ui`), use a quoted heredoc — the quoted delimiter stops `$`/backtick expansion of the plan body; source in the same block so `$OUT`/`$TS` are set:

```bash
source ~/.claude/skills/lib/skill-env.sh
cat > "$OUT/plan-$TS.md" <<'PLAN_EOF'
<full implementation plan markdown>
PLAN_EOF
```

**Then persist the plan's file list** to `$OUT/plan-files.txt` — one repo-relative path per line for every file created or modified, plus any directory created (trailing slash, so files appearing in it later count as in-scope). `lib/plan-scope-check.sh` reads this downstream:

```bash
source ~/.claude/skills/lib/skill-env.sh
cat > "$OUT/plan-files.txt" <<'FILES_EOF'
client/src/components/deck/
client/src/lib/api.ts
FILES_EOF
```

## Step 6: Publish the Plan Artifact

**Always** publish the full plan as an HTML artifact. A template produces the page: **author no HTML, do not load artifact-design** (`RATIONALE.md`) — run the script, publish its output unchanged.

```bash
source ~/.claude/skills/lib/skill-env.sh
~/.claude/skills/lib/render-plan-artifact.sh "$(ls -t "$OUT"/plan-*.md | head -1)"
# prints the generated .html path
```

Call the **Artifact tool** with the printed `.html` path — `favicon: "📐"` (stable across plan artifacts), `description`: one sentence on what the plan implements, no `title` (the script injected one). Each run mints its own URL; that's intended.

**No Artifact tool** (the read-only `Plan` agent under `/orch-ui`): render anyway and put the `.html` path prominently in your output for the coordinator to publish. Never skip the render.

## Step 7: Final User-Facing Summary

Print a summary to the conversation. The artifact carries the layout; the inline message exists so pending decisions can be answered in chat without opening it.

**Also persist each Open Question as a decision memo**, additive to the inline listing, per **AUTHORING.md § Decision memos** (lifecycle, ids, dedupe-before-raise); `raised_by: plan-ui`. One plan-specific addition: where an option trades off against a prerequisite the memo's Context names as missing, add `Risk if chosen without it: {one line}` under it — so resolving takes engaging with the tradeoff, not picking a letter.

**Rules:**
- **List every Open Question inline, in full** — verbatim, numbered, with the context needed to answer it. Never "see the plan for questions."
- Print a compact summary in this shape:

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

End by asking the user to answer any open questions before `/impl-ui` runs, and do not proceed while they are unanswered.

**Resolve in this conversation the moment the user answers** (`RATIONALE.md`). A reply that answers a question — plain chat text, not necessarily one AskUserQuestion per question — is recorded before anything else:
```bash
~/.claude/skills/lib/decide.sh resolve {id} <<'EOF'
{the user's chosen answer, one line}
EOF
```
Then fold each resolution into the plan, as in Step 1's seeding. A partial reply resolves the questions it answers and re-asks the rest; never hold them as a batch waiting for one complete reply.

```bash
# Record this run in the session runlog, so a skill invoked BY HAND is still a
# cycle /analyze-cycle can resolve. Silently no-ops when a cycle runner already
# logs this step. Guards + rationale: lib/runlog.sh. Re-sourcing skill-env.sh
# re-stamps $TS, so pass the plan path you actually wrote.
source ~/.claude/skills/lib/skill-env.sh
source ~/.claude/skills/lib/runlog.sh
runlog_append plan "PASS|FAIL|BLOCKED" "<plan path just written, or ->" \
  "<one-sentence summary>" "<open questions the human must answer, or ->" "<decision memo ids, or ->"
```
