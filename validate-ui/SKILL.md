---
name: validate-ui
description: Behavioral validation of a UI implementation against its stated requirements. Checks whether the feature does what was asked, identifies gaps, and flags unrequested changes. Use when verifying a completed feature matches its spec, checking for scope creep, or reviewing before opening a PR.
version: 1.2.0
triggers:
  explicit:
    - validate ui
    - validate this feature
    - does this match the spec
    - check against requirements
  strong_intent:
    - does this do what was asked
    - review the implementation against the ticket
    - are there any gaps
    - check for scope creep
  question_form:
    - does this match what was requested
    - what's missing from this implementation
    - did I implement everything
confidence_threshold: 75
---

# validate-ui

**Arguments**: $ARGUMENTS — the original feature request, task description, or ticket URL

## Step 1: Get the Spec

Parse $ARGUMENTS to find the original requirements:
- If a Linear/GitHub ticket URL: fetch its content
- If a text description: use it directly
- If "use plan": read the most recent /plan-ui output

Extract:
- What the feature is supposed to do
- What the user-facing behavior should be
- Any specific acceptance criteria stated

## Step 1.5: Load the Task-Context Artifact (if present)

```bash
source ~/.claude/skills/lib/skill-env.sh   # sets BASE (default branch), OUT, TS
[ -f "$OUT/analysis-latest.md" ] && echo "context: $(readlink "$OUT/analysis-latest.md")"
```

If `$OUT/analysis-latest.md` exists (written by `/analyze-task`), read it — it is ≤150 lines and distilled. Trust its **Task Classification** and **Tooling Constraints**; use its **Mentioned Files** to anchor which parts of the diff matter most, and its **Gotchas** as candidate implicit requirements (loading/error/empty-state conventions the repo expects). Do not re-derive these facts. If absent, skip silently.

## Step 2: Get the Implementation

```bash
source ~/.claude/skills/lib/skill-env.sh   # sets BASE (default branch), OUT, TS
# What changed on this branch — names + total size
git diff --name-only "$(git merge-base HEAD "$BASE")"..HEAD
git diff --stat "$(git merge-base HEAD "$BASE")"..HEAD | tail -1
```

**Scope the tree check to the plan's files.** Validation reads the committed diff above. For *uncommitted* work, use the script instead of scanning the tree:

```bash
~/.claude/skills/lib/plan-scope-check.sh   # exit 1 + paths = real collision; exit 0 = clear
```

Only a non-empty result is in scope; quote exactly those paths. Unrelated concurrent work on a shared branch is not a validation finding and not grounds for a memo (`RATIONALE.md`).

**Size gate — do not read a large diff inline.** This skill runs on opus in the feature cycle; it is the most expensive context in the suite to bloat, and reading every changed file breaks the context budget the rest of the pipeline protects.

- **Small change** (≤ ~10 changed files AND ≤ ~600 diff lines): read the changed files inline and understand what was actually built.
- **Large change**: spawn one fresh read-only agent (`Explore` if available, else `general-purpose` with `model: sonnet`, constrained by its prompt to read-and-report). Pass it the spec's requirement list (from Step 1) and the changed-file list. Its task:
  > For each changed file, summarize what user-facing behavior it adds or changes (behavior, not code quality). Then map each requirement to the file(s) and line(s) that appear to implement it, and list any requirement you found no implementation for. Return the summary as structured text, ≤150 lines.

  Write the agent's summary to `$OUT/validation-changes-$TS.md`, then work from that summary — selectively open only the specific files needed to verify a requirement the summary leaves uncertain, rather than the whole diff.

## Step 3: Behavioral Comparison

Compare spec against implementation **from the user's perspective** — not from a code quality lens. Ask:

1. **Does it do what was asked?**
   - For each stated requirement: is it implemented?
   - Are there implicit requirements (loading states, error states, empty states) that are expected but not stated?

2. **Are there gaps?**
   - Requirements that are partially implemented
   - Happy path works but edge cases are missing
   - Feature works but is not accessible (missing ARIA, keyboard navigation). If the change adds an icon-only or colour-carried state, resolve the token to its hex, compute the ratio against every background it renders on, and check the 3:1 WCAG 1.4.11 floor. Prefer the token an existing sibling component already uses for the same state over a fresh choice — an accessible name does not discharge this.

3. **Are there unrequested changes?**
   - Changes to files not related to the feature
   - Behavior changes in existing functionality. **A file being named in the plan does not make its behaviour changes requested.** For every function the diff modifies rather than adds, diff it against `$BASE` and count its call sites (`git grep -c`); a changed shared helper is an unrequested change to every caller the request never mentioned. Name the call-site count in the finding.
   - New dependencies or global state changes that weren't requested
   - Refactors that weren't asked for (even if they look like improvements)

   Each one is a judgment call, not a fact — raise it as a decision memo rather than settling it unilaterally or leaving it as unresolved prose. Follow **AUTHORING.md § Decision memos** for the lifecycle, id allocation, and dedupe-before-raise. This skill's specifics: `raised_by: validate-ui`, options `A) keep — intentional` / `B) revert` / `C) split into a separate change`. Spawned as an `/orch-ui` subagent you have no AskUserQuestion — leave the memo open, cite the id, and report `BLOCKED`.

## Step 4: Check for Tests

Are the required tests present?
- Unit tests for the new logic
- E2E tests for the new flow
- Existing tests updated for changed behavior

## Step 5: Output Validation Report

Write the body in the shape below, then generate the machine-consumable frontmatter with the script — the verdict, the counts, and the human-only-gap rule are arithmetic, not judgment:

```bash
~/.claude/skills/lib/validation-verdict.sh <body-file> [--human-only-gaps N]
```

Your judgment is *which* findings earn a mark. A `✗`/`⚠` is for missing or partial coverage of a new or substantially-changed stateful component or hook central to this feature — not a blanket "no E2E for the whole app". Pass `--human-only-gaps N` = how many marks are mandated manual/visual/in-browser checks with no automation surface in this environment (no browser automation, no E2E runner, no component test runner — verify it, don't assume). The script honors that only when *every* remaining gap is one, and then emits `blocked: true`: report `STATUS: BLOCKED` citing the memo id, never `FAIL`, so `orch-ui` routes it to the human instead of spending a remediation round on it (`RATIONALE.md`).

Body shape (the frontmatter above it comes from the script):

```
## Validation Report: {feature name}

**Verdict: {the verdict the script emitted}**

### Requirements Check

✓ {requirement}: implemented at {file:line}
✓ {requirement}: implemented at {file:line}
✗ {requirement}: NOT implemented — {what's missing}
⚠ {requirement}: partially implemented — {what's missing}

### Implicit Requirements

✓ Loading state handled
✓ Error state handled
✗ Empty state not handled — {where it's needed}

### Unrequested Changes

⚠ {file}: {description of change not in spec} — decision memo `{OUT}/decisions/d{NNN}-validate-ui-{slug}.md` ({open | resolved: <answer>})

### Test Coverage

✓ Unit tests present
✗ E2E tests missing for {flow}

### Summary

{1-2 sentences on overall status and what to address before this is done. If any decision memo from Step 3 is still open, say so explicitly here.}
```

Prepend the script's frontmatter to that body and write the whole thing to:

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/validation-report-$TS.md"   # ← write the report to this exact path
```

Write this report to the path echoed above so the next agent can read the verdict and act on gaps or unrequested changes.

```bash
# Record this run in the session runlog, so a skill invoked BY HAND is still a
# cycle /analyze-cycle can resolve. Silently no-ops when a cycle runner already
# logs this step. Guards + rationale: lib/runlog.sh. STATUS carries the verdict:
# COMPLETE -> PASS; gaps found -> FAIL; an open decision memo -> BLOCKED.
source ~/.claude/skills/lib/skill-env.sh
source ~/.claude/skills/lib/runlog.sh
runlog_append validate "PASS|FAIL|BLOCKED" "<validation-report path just written, or ->" \
  "<one-sentence verdict>" "<gaps or unrequested changes to address, or ->" "<decision memo ids, or ->"
```
