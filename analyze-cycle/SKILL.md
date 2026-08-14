---
name: analyze-cycle
description: Post-mortem for a completed work cycle. Reads the step ledger, artifacts, per-step cost, transcripts, and the branch's out-of-cycle fix-sessions, then proposes evidence-backed edits to the skills and cycle definition that caused each problem. Proposes by default; applies only when told to. Use after a cycle finishes, when one cost or looped too much, or when you keep hand-fixing the same thing after every run.
version: 1.0.0
triggers:
  explicit:
    - analyze cycle
    - analyze-cycle
    - cycle retro
    - cycle post-mortem
    - review the last cycle
    - why did that cycle cost so much
  strong_intent:
    - what went wrong in that run
    - improve the skills based on that cycle
    - the cleanup step keeps looping
  question_form:
    - where did the cycle waste money
    - what did the cycle miss
confidence_threshold: 80
---

# analyze-cycle

**Arguments**: $ARGUMENTS (optional) — a cycle id, a cycle dir, a path to an `orch-run-*.md` runlog, `latest`, or nothing (then you resolve and confirm the target). May also name a focus (`cost`, `looping`, `what leaked`) to weight the triage, and/or the word `retro` to select retro mode.

## Retro mode (`retro` in $ARGUMENTS)

When invoked as a cycle's **own final step**, you are analyzing a cycle that is still running — your own step is part of it.

**Never raise a decision memo, never report `BLOCKED`, never apply an edit.** A retro's proposals gate nothing downstream — the work is already committed — and `BLOCKED` halts the cycle in `orch-ui` Step 3e regardless of `stop_on_fail`. Report `PASS` with the artifact path in `FOLLOWUP` and skip Step 7 entirely.

**A live retro is not a degraded retro. Capture everything, now.** The leak record needs the right window, not a settled branch: `cycle-forensics.py` opens it at **the end of the previous cycle on this branch** and holds it to *now*. Already on disk:

| Available at retro time | Attributed to |
|---|---|
| `inter-cycle` sessions + commits — every hand-fix in the gap before this cycle started | the **previous** cycle — its complete, final leak record |
| `during` sessions, including ones **still active** right now | this cycle — concurrent human intervention |
| **Live rework** — files a cycle step edited that an outside session then edited again, read from transcript edit-lists, no commit needed | whichever session pair it names |
| **Intra-cycle rework** — a file two different steps of this cycle both edited (a later step patching an earlier one) | this cycle |
| **Uncommitted working tree** — often where the whole diff still lives mid-cycle | this cycle |

Retros therefore **compound**: each closes the loop on its predecessor while capturing its own live signals. The only thing a retro can't see is its own post-cycle leak; the next one reports it. Never call the leak analysis unavailable or deferred.

Two attribution rules, both hard:

- **Never blame this cycle for `inter-cycle` evidence.** Carry `attributed_to` into every finding; a proposal targeting a step from the *previous* cycle is still valid — just say so.
- **Read `active` sessions as present-tense.** `🔴 STILL ACTIVE` means the human is working around the cycle *right now* — the strongest signal there is, and it belongs at the top of the report.

Everything else (Steps 1–6) runs unchanged.

You are running a **post-mortem on one cycle**, turning what you find into proposed edits to the skills that ran it. The deliverable is a written proposal; you edit skills only after explicit approval (Step 7).

The insight this skill is built on: **a cycle's real failures are recorded in the sessions that ran around it.** If the human opened a fresh session on that branch to fix the loading bar, add the tests, or work the PR feedback, some step either didn't do its job or doesn't exist. Those sessions are ground truth; the step ledger only says what the cycle *thought* happened.

## Caps (fixed)

- **6** investigations fanned out in Step 4. Triage takes the 6 highest-signal; the rest are listed as un-investigated, never silently dropped.
- **8** proposals in the artifact. Rank and cut, don't pad.
- Both are hard. If the evidence needs more, say so and let the human re-run scoped to what you left out — never self-authorize a bigger sweep.

## Step 0: Resolve the cycle — then CONFIRM

```bash
source ~/.claude/skills/lib/skill-env.sh
python3 ~/.claude/skills/lib/cycle-forensics.py list --limit 15
```

Take the target from `$ARGUMENTS` — an id prefix, a dir, a runlog path, or `latest`. If it names none, use the most recent cycle for the current repo/branch, else the most recent overall.

**Confirm before spending anything**, and wait for the reply:

> Cycle: **f0e8c64c** — eli-feature-cycle · incentives / bw/ai-eval-transition · completed · $32.72 · 2026-07-29
> 8 steps, 13 runs. I'll read the ledger, the artifacts, the step transcripts, and the branch's un-connected sessions, then propose skill edits.
> Proceed? Or pick another cycle.

Use AskUserQuestion when the choice is genuinely open (options = the listed cycles). Running **isolated** with a cycle named unambiguously in `$ARGUMENTS`, take that as the confirmation.

**In retro mode**, skip the confirmation: the target is the newest cycle for this repo/branch — the in-flight one you are a step of. Its status reading `running` and your own attempt files being mid-write are expected, not errors. With no cycle dir (an in-session cycle), fall back to the newest `$OUT/orch-run-*.md`; with neither, report `PASS` and `SUMMARY: no cycle record to analyze` rather than failing a cycle over its own retro.

## Step 1: Deterministic forensics (free — no model reading)

```bash
python3 ~/.claude/skills/lib/cycle-forensics.py report <target> > "$OUT/cycle-forensics-$TS.md"
python3 ~/.claude/skills/lib/cycle-forensics.py history --limit 12 > "$OUT/cycle-history-$TS.md"
echo "$OUT/cycle-forensics-$TS.md"
```

The report already carries, mechanically: the **step ledger** and **attempt table** (status, attempts, remediation rounds, cost, tokens, session ids), **cost rollups**, **step summaries**, **artifact inventory**, **decision memos**, the **session map** with `attributed_to` and `🔴 STILL ACTIVE` labels, **live and intra-cycle rework**, the **working tree**, bucketed **commits**, and **mechanical flags**. `FORENSICS.md` in this skill's directory is the full inventory — read it when you need to know exactly what a section holds. Re-derive none of it by hand.

Also capture the suite's prose budgets — a skill over budget is a candidate finding in its own right, and the check is free:

```bash
python3 ~/.claude/skills/lib/skill-size.py > "$OUT/skill-size-$TS.txt"
```

Read the forensics report yourself; it's bounded and cheap. **Never read step transcripts in this context** — they are megabytes each, and Step 4's subagents read them by path.

If the report says `no cost data` (the in-session `/orch-ui` runlog surface), make no cost findings at all and say so explicitly rather than estimating. Never invent prices.

## Step 2: Check what's already been fixed

The human often patches the skill mid-frustration and moves on. Re-proposing a change that already landed is the fastest way to make this skill worthless.

```bash
git -C ~/.claude/skills log --since='<cycle start date>' --format='%h %ad %s' --date=short --name-only
git -C ~/.claude/skills status --short
```

Cross-reference the forensics `unlinked-session-edited-skills` flags, which name the exact skill files a session touched. Classify every candidate problem as **already committed**, **uncommitted in the working tree**, or **not addressed**. Only the third becomes a proposal; the first two go in the report as already-handled — and an incomplete uncommitted fix gets a proposal to *finish* it, referencing what's there.

Read the current text of any skill you intend to propose editing. A proposal against remembered content is worthless — the suite changes weekly.

## Step 3: Triage — build the investigation list

Group the flags into candidate problems, then rank. Signal, strongest first:

| Evidence | What it usually means | Where the fix usually belongs |
|---|---|---|
| Session marked **`🔴 STILL ACTIVE`** | the human is working around the cycle *right now* | whatever they're doing by hand — read that session first |
| **`inter-cycle`** fix-session or commit | the **previous** cycle didn't deliver something; this record is complete | the step that owned it in *that* cycle — attribute it correctly |
| **Live rework** (transcript overlap) | a step shipped something an outside session immediately corrected | the step that shipped it |
| **Intra-cycle rework** (two steps, one file) | a later step is patching an earlier one — the seam between them is wrong | the earlier step, or the handoff between them |
| Unlinked fix-session **after** the cycle | the cycle didn't deliver something | the step that owned that concern, or a missing step |
| A post-cycle session invoking a skill the cycle never ran (`/write-unit-tests`, `/pr-review`) | a capability the cycle should include | the **cycle definition** — add a step |
| **Rework files** — cycle shipped it, later commit fixed it | the wrong thing shipped and the gate passed it | impl-ui, or validate-ui's gate |
| Same step retried 3+ times, same block each time | the skill re-diagnoses instead of bailing; no dedupe-before-raise | the skill's block/memo path, or a preflight |
| Step failed on toolchain/env (Node, Prisma, deps) | **environmental, not a skill defect** | a fast preflight that detects and bails — never "fix the environment" |
| Missing `STATUS:` line / crash / nonzero exit | five-line contract violated | the skill's report step |
| Cost outlier or cache-read hotspot | a step is reading raw material it should delegate or digest | the skill's delegation step, or the model tier in the cycle |
| Skill over its prose budget (`skill-size-$TS.txt`) | instruction density is above the tier — deliberation the step doesn't need | move rationale to `RATIONALE.md`, cut a restated contract, push deterministic logic to `lib/` |
| A step re-deriving a rule the skill states as prose (counting, precedence, tallies) | a computation is being reasoned about every run | `lib/`, invoked from the skill |
| Open decision memo at cycle end | the run sailed past a block | orch-ui's gate, or the raising skill |
| Empty / duplicate artifacts | artifact plumbing bug | the skill's artifact step |
| Session hand-edited the skill suite | the human already diagnosed it for you | read their edit first, then extend it |

Two known false-positive sources — check both before promoting a flag:

- **`unlinked-session-during` is often just parallel work.** On a long-lived branch, a session overlapping the cycle window may be unrelated feature work. Read its first prompt and edited files: one that edited the *skill suite* or complained about a step is signal; one building an unrelated feature is not.
- **Runlog-surface owner detection is a grep** for the runlog filename, so it also matches any later session that merely read it (including a previous `/analyze-cycle`). Verify before treating a session as cycle-owned.

Weight by the `$ARGUMENTS` focus if one was given, then write the ranked list (max **6**) as a one-liner each, and name what you're leaving un-investigated.

**Distinguish environmental from skill defects ruthlessly.** A step that failed because Node was too old for Prisma is not a broken skill; a step that burned five attempts discovering that *is*, and the fix is detect-and-bail-fast, never a toolchain change.

## Step 4: Fan out — one reader per investigation (sonnet)

Spawn the investigations **in parallel**, one `general-purpose` subagent each at `model: sonnet`. Pass paths, never contents. Each gets:

> Investigate ONE problem from a completed work cycle. Repo `<REPO>`, branch `<BRANCH>`, cycle `<id>`.
>
> **Problem:** `<the one-line candidate from triage>`
> **Evidence to start from:** `<the specific flags, verbatim>`
> **Read (by path, only what you need):**
> - forensics report: `<$OUT/cycle-forensics-$TS.md>`
> - step artifacts: `<the relevant artifact paths>`
> - step transcripts: `<the relevant session jsonl paths>` (huge — grep/filter, never cat whole)
> - the skill as it exists today: `<~/.claude/skills/<skill>/SKILL.md>`
> - the cycle definition: `<~/.claude/skills/orch-ui/cycles/<cycle>.md>`
>
> Answer exactly these, and nothing else:
> 1. **What happened** — the sequence, with concrete evidence (file:line, artifact quote, transcript timestamp/session).
> 2. **Root cause** — and classify it: `skill-defect` | `cycle-definition` | `environmental` | `human-choice` | `no-defect-found`.
> 3. **The exact instruction that failed** — quote the sentence/section of the SKILL.md (or cycle entry) that produced the behavior, or state plainly that no instruction covers this case.
> 4. **Minimal fix** — the smallest edit to the smallest number of files that prevents a recurrence. Name the target file and section. Prefer changing a cycle entry (model tier, cap, `remediate`, step order, added step) over rewriting skill prose when the problem is cost or looping.
> 5. **What would regress** — what the current wording is protecting against, and whether your fix breaks it.
> 6. **Confidence** — high/medium/low, and what evidence would raise it.
>
> Do NOT edit any file. Do not propose comment removals or comment-standards steps. Return under 400 words. If the evidence doesn't support a finding, say `no-defect-found` — that is a useful, expected answer.

Include these transcript hints: filter the jsonl with `grep`/`python3` rather than reading it whole; the useful entries are `type:"assistant"` messages with `tool_use` blocks, `toolUseResult` payloads, and the final text. A step's subagent transcripts live in `<session>/subagents/*.jsonl`.

## Step 5: Corroborate — systemic or one-off

For each finding that came back `skill-defect` or `cycle-definition`, check `$OUT/cycle-history-$TS.md`:

- High `mean attempts`, `non-pass slots`, or `$/run` for that skill across **other** cycles → **systemic**. Propose the fix.
- Only this cycle, cause traces to this task's specifics → **one-off**. Propose only if the fix is cheap and safe; otherwise record a watch-item with the evidence so a second occurrence promotes it.
- Contradicted by other cycles → say so and drop it.

A single cycle is one data point. Over-fitting the suite to one bad run is a worse outcome than leaving a one-off unfixed — the history table exists so you can tell the difference. State the classification for every proposal.

## Step 6: Synthesize the proposal artifact (opus-grade reasoning)

Write `<cycle output dir>/cycle-analysis-$TS.md` — the cycle's own output dir (the forensics report's `output dir`), so it sits with the evidence it's about. Use this shape:

```markdown
---
cycle: <id>            cycle_type: <name>
repo: <repo>           branch: <branch>
ran: <start> → <end>   cost: <$ or "not recorded">
analyzed: <timestamp>  forensics: <path to cycle-forensics-*.md>
---

# Cycle analysis — <id>

## Verdict
<3–5 lines: did the cycle deliver? what did it cost? what leaked out into hand-fixes?>

## What the cycle cost
<step table: step | model | status | attempts | cost | share of total. Then the 2–3 sentences
that actually matter — where the money went and whether it bought anything.>

## What leaked — happening now
<`🔴 STILL ACTIVE` sessions and the uncommitted working tree: what the human is working
around at this moment. Omit the section only if there is genuinely nothing live.>

## What leaked — this cycle
<`during` sessions that did real work, live rework, intra-cycle rework. What the human had
to do alongside the cycle, and which step should have covered it.>

## What leaked — previous cycle (<its id>)
<`inter-cycle` sessions and commits: the previous cycle's COMPLETE leak record, closed out
here. This is the section that makes retros compound — never skip it because the evidence
predates this run. If this is the branch's first cycle, say so.>

## Findings
<per finding: what happened · root cause · classification (skill-defect | cycle-definition |
environmental | human-choice) · systemic|one-off · evidence paths. Findings with no proposal
still belong here.>

## Proposals
### P1 — <one-line change> · `<target file>` · <systemic|one-off> · <high|med|low priority>
**Evidence:** <paths, quotes, session ids>
**Root cause:** <one or two sentences>
**Current text:** <quote the instruction that failed, or "no instruction covers this">
**Proposed edit:** <the exact replacement text, or the precise cycle-entry change>
**Why this file:** <why here and not in a different skill>
**Regression risk:** <what the current wording protects; whether this breaks it>
**Already-fixed check:** <not addressed | partially, uncommitted in <path> | superseded by <sha>>

## Suite prose budgets
<the `skill-size.py` table from Step 1: any skill over its tier budget, with how far over.
"All within budget" is a valid and expected line. A skill that grew past budget since the
last retro is a finding, not a note.>

## Already handled
<problems found that the human already fixed — with the commit or working-tree change.>

## Watch-items (one-off, not proposed)
<evidence recorded so a second occurrence promotes it to a proposal.>

## Not investigated
<triage items dropped at the cap of 6, with their flags, so nothing is silently lost.>
```

Rules for proposals, all of them hard:

- **Every proposal cites concrete evidence** — an artifact path, a transcript session, a commit, a quoted line. A proposal whose support is "this seems better" gets cut, not softened.
- **Smallest edit that prevents recurrence.** No rewrites-while-you're-in-there, no drive-by restructuring of a skill you happened to open.
- **A proposal that adds prose to a SKILL.md must say where the rationale goes.** State the rule as an imperative in the skill; the incident narrative that justifies it goes in that skill's `RATIONALE.md` (AUTHORING.md § Rationale files). A proposal whose text embeds the war story in SKILL.md is not ready — rewrite it before proposing.
- **A proposal must fit the target's prose budget.** Check `$OUT/skill-size-$TS.txt` (Step 1) for the target's tier and headroom. An edit that would push a skill over must name what it replaces or moves out — never "add this too." This is what keeps retros from ratcheting the suite's prose upward one justified clause at a time. A skill already over budget gets a trim proposal of its own, with the size table as evidence.
- **Never propose removing comments** — from skills or from code — and never reintroduce a comment-standards or comment-removal step into any flow. Standing constraint from CLAUDE.md.
- **Respect the suite's conventions** (AUTHORING.md): caps stay integers fixed at authoring time; a pause always ends the turn; deterministic plumbing goes in `lib/`; a global skill never loads a repo-specific project skill.
- **Model-tier proposals cite the rubric** — haiku mechanical, sonnet standard, opus expensive-if-wrong — plus the measured cost/attempt evidence.
- **A proposal touching CLAUDE.md or AUTHORING.md is a policy change**, not a skill edit. Flag it, keep it separate, never apply it under a general "yes, apply the proposals."
- **No proposal may change code in the analyzed repo.** This skill improves the tooling; fixing the product is a different cycle.

## Step 7: Present, then gate application

**Retro mode skips this entire step** — print the summary, report `PASS`, and stop. No menu, no memo, no edits.

Print a compact summary: the verdict, the cost line, what leaked, and one line per proposal (`P1 · target file · priority · systemic/one-off`). Point at the artifact; never dump it into the conversation.

Then ask, per **AUTHORING.md § Interaction contract** — and this **ends the turn**:

- **A) Apply the high-priority proposals** (P<n>, P<n>) — the ones with systemic evidence
- **B) Apply a subset I name**
- **C) Propose only — leave the skills alone for now**
- **―) none of these — add context**

**If approved**, apply only the named proposals, exactly as written — no scope expansion at apply time. Re-read each target file first, edit, then append an `## Applied` section to the artifact listing each change and where it landed. Leave the skills repo uncommitted unless asked; these are the human's global tools.

**If isolated** (no AskUserQuestion): apply nothing. Raise one memo — `$OUT/decisions/d{NNN}-analyze-cycle-apply-proposals.md`, `raised_by: analyze-cycle`, the options above — per AUTHORING.md § Decision memos, then report `STATUS: BLOCKED` with its id.

## Report contract

When invoked as a cycle step, end with exactly:

```
STATUS: PASS | FAIL | BLOCKED
ARTIFACT: <absolute path to cycle-analysis-$TS.md>
SUMMARY: <one sentence — what the cycle cost, what leaked, how many proposals>
FOLLOWUP: <the highest-priority proposal and its target file, or ->
DECISIONS: <memo ids, or ->
```

`PASS` means the analysis completed, including "clean cycle, no proposals" — a cycle with problems still yields `PASS`, since the problems are the product. `FAIL` is only for an analysis that couldn't run (no such cycle, no readable forensics). In retro mode `BLOCKED` is unavailable.

## Rules

The step-level rules above are not restated here. Two that belong to the whole run:

- **Keep your own output short** — the confirmation, the triage list, the summary, the artifact path. Nothing else.
- **Never apply a proposal without explicit approval**, and never expand past what was approved.
