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

**Scope the tree check to the plan's files.** Validation reads the committed diff above. If you also need to reason about *uncommitted* work, do not scan the whole tree:

```bash
~/.claude/skills/lib/plan-scope-check.sh   # exit 1 + paths = real collision; exit 0 = clear
```

Treat only a non-empty result as in scope, and quote exactly those paths. Unrelated concurrent work on a shared branch is not a validation finding and is not grounds for a memo — on `dev-screen/home-cleanup` two opus attempts were spent reporting "three streams of unrelated concurrent work share the uncommitted tree", which was true and irrelevant.

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
   - Feature works but is not accessible (missing ARIA, keyboard navigation)

3. **Are there unrequested changes?**
   - Changes to files not related to the feature
   - Behavior changes in existing functionality
   - New dependencies or global state changes that weren't requested
   - Refactors that weren't asked for (even if they look like improvements)

   Each one is a judgment call, not a fact — route it through a decision memo rather than settling it unilaterally or leaving it as unresolved prose (AUTHORING.md § Decision memos & per-repo review heuristics):
   - **Dedupe before raising**: `~/.claude/skills/lib/decide.sh list open` first; if an open memo already covers this change, reference its id instead of raising a near-duplicate.
   - **New finding**: get the next id (`~/.claude/skills/lib/decide.sh next-id`) and Write a memo to `$OUT/decisions/d{NNN}-validate-ui-{slug}.md` — frontmatter `id, title, status: open, raised_by: validate-ui, raised_at, resolution:` (empty), then a body: the change and why it reads as unrequested, lettered options (e.g. `A) keep — intentional`, `B) revert`, `C) split into a separate change`) with a recommendation first.
   - **Running interactively** (AskUserQuestion available): present the memo's options via AskUserQuestion right away, then `~/.claude/skills/lib/decide.sh resolve <id>` with the chosen answer piped on stdin — the memo doubles as a decision log even when answered immediately.
   - **Running isolated** (no AskUserQuestion — e.g. spawned as an `/orch-ui` subagent): never attempt AskUserQuestion. Leave the memo `open`, cite it by id in the report, and treat this run as blocked in your final summary — a wrapping subagent should reply `STATUS: BLOCKED` and list the id(s) under `DECISIONS:` per orch-ui's subagent contract, not `PASS`/`FAIL`.

## Step 4: Check for Tests

Are the required tests present?
- Unit tests for the new logic
- E2E tests for the new flow
- Existing tests updated for changed behavior

## Step 5: Output Validation Report

The report opens with machine-consumable frontmatter so the orch remediation loop can read the verdict and counts without parsing prose, followed by the human-readable body:

```
---
verdict: COMPLETE | GAPS FOUND | OUT OF SCOPE CHANGES
gaps: {n}
unrequested: {n}
---

## Validation Report: {feature name}

**Verdict: COMPLETE | GAPS FOUND | OUT OF SCOPE CHANGES**

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

`gaps` = count of `✗` and `⚠` lines across Requirements Check + Implicit Requirements + Test Coverage, when the missing/partial coverage is for a new or substantially-changed stateful component or hook central to this feature (not a blanket "no E2E for the whole app" note, and not covered by the Human-only gap exception below). `unrequested` = count of entries under Unrequested Changes (memoed or already resolved). Verdict: `GAPS FOUND` if `gaps > 0` (regardless of `unrequested` — a missing requirement is more severe than an open scope question); else `OUT OF SCOPE CHANGES` if `unrequested > 0`; else `COMPLETE`.

**Human-only gap exception.** If *every* remaining `✗`/`⚠` gap is a mandated manual, visual, or in-browser pass with no automation surface in this environment — verify it: no browser automation tool, no E2E runner, no component test runner installed — do not verdict `GAPS FOUND`. Raise it as a decision memo (Step 3's dedupe rule first) and report `STATUS: BLOCKED` citing that memo id, never `FAIL`. `orch-ui`'s `remediate` fires only on `FAIL`, so `BLOCKED` routes the gap to the human instead of spending a remediation round on work no code change can do. This exception requires zero remaining code-level gaps — a single fixable `✗` means the normal `GAPS FOUND` rule still applies.

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/validation-report-$TS.md"   # ← write the report to this exact path
```

Write this report to the path echoed above so the next agent can read the verdict and act on gaps or unrequested changes.
