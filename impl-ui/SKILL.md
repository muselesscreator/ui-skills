---
name: impl-ui
description: Implements a UI feature or change. Loads repo learnings and any existing plan, implements the change checking standards inline, delegates the presentation layer (semantic markup, CSS, class composition) to a dedicated sonnet subagent, then triggers test writing. Use when building a new UI feature, modifying an existing component, or executing a /plan-ui output.
version: 1.0.0
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

## Step 1: Load Context

```bash
source ~/.claude/skills/lib/skill-env.sh   # sets REPO, BRANCH, OUT, SRC, LEARNINGS_DIR
```

Load learnings. `$SRC` says where: a repo with a `./wiki/` (work repo) keeps canonical knowledge in the wiki (QMD `wiki` collection) → `$SRC=wiki`; a repo with none (OSS checkout) uses flat files under `$LEARNINGS_DIR` → `$SRC=flat`.

**If SRC=wiki** — query QMD, scoped to `collections: ["wiki"]` with an `intent`, for reference implementations, gotchas/conventions, and file placement; then read the top hits with `_get`/`_multi_get`. If a plan file is in use, add a sub-query per pattern in its "Patterns to Follow" section.

**If SRC=flat** — read `~/.claude/repo-learnings/$REPO/index.md`, `gotchas.md`, and `file-structure.md`; for plan patterns, also read `ui-patterns.md`/`advanced-patterns.md`.

If $ARGUMENTS contains "use plan": find the most recent plan file with `ls -t ~/.claude/skill-output/$REPO/$BRANCH/plan-*.md 2>/dev/null | head -1` and read it as the implementation spec.
If $ARGUMENTS contains a file path: read that file as the implementation spec.
Otherwise: treat $ARGUMENTS as the task description and derive the approach from learnings + live code reading.

## Step 2: Identify Reference Implementation

From `index.md`, pick the most relevant reference implementation for this task type. Read it. This is the pattern to follow.

## Step 3: Implement

Build the change. At each meaningful decision point, check against:
- The loaded ui-patterns: am I following the established data layer pattern?
- The loaded file-structure: am I placing files at the right level?
- The loaded gotchas: am I about to do something the codebase has flagged as a trap?
- The loaded standards: am I naming things consistently?

Do not deviate from established patterns without flagging it:
```
⚠ Deviation from pattern: [description]
Reason: [why this case is different]
Proceeding? [yes/no — ask if non-obvious]
```

## Step 3.5: Presentation-Layer Pass (delegated to a lower tier)

Step 3 builds the structure, data layer, and component logic. The **presentation layer** — semantic element choice (`div` vs `span` vs `button` vs list/landmark elements), the CSS/styling approach, and `className`/token composition — is standard implementation work that doesn't need the architectural-reasoning tier. Delegate it to a dedicated subagent so heavy reasoning stays on structure, not on `div`-vs-`span`.

**Spawn one subagent (`model: sonnet`)** pointed at the component files written in Step 3. The Task/Agent tool's `model` is the lever here (effort is session-level — see `~/.claude/skills/AUTHORING.md`). When this skill itself runs on `sonnet` (e.g. the orch-ui feature-cycle `impl` step), this is a same-tier split — its value is then **context isolation**, not a tier drop; the tier drop applies when impl runs on a higher tier (e.g. a direct `/impl-ui` opus session). Give it, in the prompt:
- The component files to refine (paths from Step 3).
- The repo's presentation conventions from the learnings loaded in Step 1 — the established CSS/utility/token/styled pattern and the relevant design-system reference file. It must follow these, not invent its own.
- Its scope, fenced tightly — it must not touch data hooks, state, prop contracts, or business logic; those are fixed by Step 3.

Prompt skeleton:
```
You are refining the presentation layer of already-implemented components.
Files: {paths}
Follow these repo conventions exactly (do not invent patterns):
  CSS / styling: {pattern + reference file from the loaded learnings}
  Semantic markup / a11y: {element & accessibility conventions from learnings}
Edit ONLY:
  - semantic element choice (div/span/button/ul/nav/… — prefer the most semantic, accessible element)
  - styling via the established pattern above
  - className / design-token composition
Do NOT change: data hooks, state, prop contracts, business logic, file structure.
Report the files you edited and any element/styling choice that was non-obvious.
```

Why sonnet: per the model-tiering rubric in `AUTHORING.md`, presentation markup and styling are standard implementation work — sonnet, not the opus tier reserved for architecture/correctness. Keep it at sonnet rather than haiku because **accessibility semantics** (landmarks, button-vs-div, ARIA) carry real judgment; the conventions you pass in must still carry any a11y rules, and `/pr-review-ui`'s accessibility specialist is the downstream backstop.

**If no Agent tool is available** (impl-ui spawned under a restricted agent type that can't fan out): skip the delegation and fold the presentation work into Step 3 inline — note in the Step 4 report that it ran inline rather than delegated.

## Step 4: Post-Implementation Check

After writing all files:

1. **Self-review against standards:**
   - No `any` or unchecked type assertions
   - No hardcoded user-facing strings (check for i18n conventions if present)
   - No business logic in presentational components
   - No direct calls to server layer from component (should go through data hooks)
   - Imports ordered correctly per project conventions

2. **Test gap check** — based on what was written:
   - List what new unit tests are needed
   - List what new E2E tests are needed
   - List what existing tests are likely affected

3. **Report:**
```
## Implementation Complete

Files created:
- {path}

Files modified:
- {path}

Standards check:
✓ Type safety
✓ Pattern compliance
✓ Import conventions
⚠ {any deviation noted}

Test work needed:
- Unit: {list}
- E2E: {list}

Next steps:
- Run /write-unit-tests {path} to write unit tests
- Run /write-e2e-tests "{flow description}" to write E2E tests
- Run /cleanup-ui to lint/type-check
- Run /validate-ui "{original task description}" to confirm behavioral correctness
```

```bash
source ~/.claude/skills/lib/skill-env.sh
echo "$OUT/impl-report-$TS.md"   # ← write the report to this exact path
```

Write this report to the path echoed above so the next agent can read what was built, what tests are needed, and what to run next.

## Step 5: Update Repo Learnings

After implementation, capture anything new or surprising. Where it goes depends on the repo:

- **Work repo (has `./wiki/`)** — never hand-edit the wiki. Surface new knowledge via `/wiki-braindump` so the next `/wiki-ingest` absorbs it. Capture it if: you hit an undocumented trap; found a `// HACK`/`// NOTE`/`// FIXME` not yet recorded; established or discovered an undocumented pattern; a tooling constraint forced a non-obvious fix; or you created files in a location not previously described.

- **OSS/reference repo (no wiki)** — append to the relevant flat file under `~/.claude/repo-learnings/$REPO/` (`gotchas.md`, `ui-patterns.md`, `standards.md`, `file-structure.md`), bumping its `Last analyzed` date.

Format new gotcha entries as:
```markdown
### {short title}
{1-2 sentence description of the trap or pattern}
**Where:** {file or feature area}
**Fix/approach:** {what to do instead}
```

If there is nothing new to add:
```
✓ No learnings updates — implementation followed established patterns.
```
