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

**Never raise a decision memo, never report `BLOCKED`, never apply an edit.** A retro's proposals gate nothing downstream (there is no downstream — the work is already committed), and `BLOCKED` halts the cycle in `orch-ui` Step 3e regardless of `stop_on_fail`. Report `PASS` with the artifact path in `FOLLOWUP`. Skip Step 7's menu entirely.

**A live retro is not a degraded retro. Capture everything, now.** The leak record does not require a settled branch — it requires the right window, which `cycle-forensics.py` opens at **the end of the previous cycle on this branch** and holds open to *now*. At retro time, all of this is already on disk:

| Available at retro time | Attributed to |
|---|---|
| `inter-cycle` sessions + commits — every hand-fix in the gap before this cycle started | the **previous** cycle — its complete, final leak record |
| `during` sessions, including ones **still active** right now | this cycle — concurrent human intervention |
| **Live rework** — files a cycle step edited that an outside session then edited again, read from transcript edit-lists, no commit needed | whichever session pair it names |
| **Intra-cycle rework** — a file two different steps of this cycle both edited (a later step patching an earlier one) | this cycle |
| **Uncommitted working tree** — often where the whole diff still lives mid-cycle | this cycle |

So retros **compound**: each one closes the loop on its predecessor with complete evidence while capturing its own live signals. The single thing no retro can see is its *own* post-cycle leak — that work has not happened yet, and the next retro on this branch will report it. Never describe the leak analysis as unavailable or deferred, and never tell the human to come back later for it.

Two attribution rules, both hard:

- **Never blame this cycle for `inter-cycle` evidence.** The forensics report labels every session and commit with `attributed_to`; carry that label into every finding. A proposal targeting the step that ran *before* this cycle is still valid and valuable — say which cycle the evidence came from.
- **Read `active` sessions as present-tense.** A `🔴 STILL ACTIVE` session means the human is working around the cycle *right now*. That is the strongest signal available and belongs at the top of the report, not in a past-tense list.

Everything else (Steps 1–6) runs unchanged.

You are running a **post-mortem on one cycle** and turning what you find into proposed edits to the skills that ran it. The deliverable is a written proposal, not applied changes: you edit skills only after explicit approval (Step 7).

The central insight this skill is built on: **a cycle's real failures are recorded in the sessions that ran around it.** If the human had to open a fresh session on that branch to fix the loading bar, add the tests, or work the PR feedback, then some step of the cycle either didn't do its job or doesn't exist. Those sessions are the ground truth; the step ledger only tells you what the cycle *thought* happened.

None of that requires waiting. The evidence window spans **the previous cycle's end to right now**, so every run captures the previous cycle's finished leak record plus its own live surroundings — including sessions still open. See **Retro mode** for the full inventory of what's readable at any moment.

## Caps (fixed)

- **6** investigations fanned out in Step 4. Triage picks the 6 highest-signal; the rest are listed as un-investigated, never silently dropped.
- **8** proposals in the final artifact. Rank and cut, don't pad.
- Both are hard. If the evidence clearly needs more, say so in the report and let the human re-run scoped to what you left out — don't self-authorize a bigger sweep.

## Step 0: Resolve the cycle — then CONFIRM

```bash
source ~/.claude/skills/lib/skill-env.sh
python3 ~/.claude/skills/lib/cycle-forensics.py list --limit 15
```

Pick the target from `$ARGUMENTS`: an id prefix, a dir, a runlog path, or `latest`. If `$ARGUMENTS` names no cycle, take the most recent one **for the current repo/branch** if there is one, else the most recent overall.

**Confirm before spending anything**, and wait for the reply:

> Cycle: **f0e8c64c** — eli-feature-cycle · incentives / bw/ai-eval-transition · completed · $32.72 · 2026-07-29
> 8 steps, 13 runs. I'll read the ledger, the artifacts, the step transcripts, and the branch's un-connected sessions, then propose skill edits.
> Proceed? Or pick another cycle.

Use AskUserQuestion when the choice is genuinely open (options = the listed cycles). If this skill is running **isolated** (no AskUserQuestion available) and `$ARGUMENTS` named a cycle unambiguously, take that as the confirmation and continue.

**In retro mode**, skip the confirmation: the target is the newest cycle for the current repo/branch, which is the in-flight cycle you are a step of. Its `manifest.json` exists from creation, its status still reads `running`, and your own attempt files are mid-write — all expected, none of it an error. If no cycle dir exists for this repo/branch (the cycle was driven in-session rather than by a cycle runner), fall back to the newest `$OUT/orch-run-*.md`; if neither exists, report `PASS` with `SUMMARY: no cycle record to analyze` rather than failing the cycle over its own retro.

## Step 1: Deterministic forensics (free — no model reading)

```bash
python3 ~/.claude/skills/lib/cycle-forensics.py report <target> > "$OUT/cycle-forensics-$TS.md"
python3 ~/.claude/skills/lib/cycle-forensics.py history --limit 12 > "$OUT/cycle-history-$TS.md"
echo "$OUT/cycle-forensics-$TS.md"
```

Everything mechanical is already extracted for you — don't re-derive any of it by hand:

- **Step ledger** — per step: skill, model tier, status, attempts, remediation rounds, cost, wall time.
- **Attempt table** — every isolated run with its model, status, cost, output/cache-read tokens, session id, artifact.
- **Cost rollups** by step and model.
- **Step summaries & follow-ups** — each run's `SUMMARY` / `FOLLOWUP` / `DECISIONS` lines.
- **Artifact inventory** (sizes, empties) and **decision memos** with status.
- **Session map** — which sessions the cycle owned, and the **unlinked** ones: same branch, not part of the cycle, each labelled `inter-cycle` / `during` / `after` **plus an `attributed_to` naming which cycle it belongs to**, marked `🔴 STILL ACTIVE` if live, with title, first real prompt, turn count, slash commands used, files edited, and whether they **hand-edited the skill suite**. The window opens at the previous cycle's end and holds open to now — see Retro mode.
- **Live rework** — files a cycle step edited that an outside session then edited again, and files two different cycle steps both edited. Read from transcript edit-lists, so it appears the moment it happens and needs no commit.
- **Working tree right now** — uncommitted changed + untracked files. Mid-cycle this is often where the entire diff still is.
- **Commits** bucketed `inter-cycle` / `during` / `after`, plus **rework files** (shipped by this cycle, edited again later), **inter-cycle rework** (hand-fixed before this cycle, touched again by it — the previous cycle left it wrong), and files only later commits touched.
- **Mechanical flags** — retries, non-pass steps, contract violations, crashes, cost outliers, cache hotspots, empty artifacts, open memos, unlinked fix-sessions, rework.

Read the forensics report yourself; it is bounded and cheap. **Do not read step transcripts in this context** — they are megabytes each. Transcripts are read by the subagents in Step 4, by path.

If the report says `no cost data` (the in-session `/orch-ui` runlog surface), you may make no cost findings at all. Say that explicitly in the report instead of estimating. Never invent prices; if a USD figure is genuinely needed and absent, the token counts are what you have.

## Step 2: Check what's already been fixed

The human very often patches the skill mid-frustration and moves on. Re-proposing a change that already landed is the fastest way to make this skill worthless.

```bash
git -C ~/.claude/skills log --since='<cycle start date>' --format='%h %ad %s' --date=short --name-only
git -C ~/.claude/skills status --short
```

Cross-reference with the forensics `unlinked-session-edited-skills` flags — those name the exact skill files a session touched. For every candidate problem, establish whether the fix is: **already committed**, **sitting uncommitted in the working tree**, or **not addressed**. Only the third kind becomes a proposal; the first two are noted in the report as already-handled (and if an uncommitted fix is incomplete, the proposal is to *finish* it, referencing what's there).

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
| Open decision memo at cycle end | the run sailed past a block | orch-ui's gate, or the raising skill |
| Empty / duplicate artifacts | artifact plumbing bug | the skill's artifact step |
| Session hand-edited the skill suite | the human already diagnosed it for you | read their edit first, then extend it |

Two known false-positive sources — check both before promoting a flag to an investigation:

- **`unlinked-session-during` is often just parallel work.** If the branch is a long-lived dev branch, sessions overlapping the cycle window may be unrelated feature work, not interventions. Read the session's first prompt and edited files: does it touch what the cycle touched? A `during` session that edited the *skill suite* or complained about a cycle step is real signal; one building an unrelated feature is not.
- **Runlog-surface owner detection is a grep.** On the `orch-run-*.md` surface, "cycle-owned" sessions are found by grepping for the runlog filename, which also matches any later session that merely read it (including a previous `/analyze-cycle` run). Verify before treating a session as cycle-owned.

Weight by `$ARGUMENTS` focus if one was given. Then write the ranked list (max **6**) to the conversation as a one-liner each, and note what you're leaving un-investigated.

**Distinguish environmental from skill defects ruthlessly.** A step that failed because Node was too old for Prisma is not a broken skill — but a step that burned five attempts and 20 minutes discovering that *is*, and the fix is detect-and-bail-fast, not a toolchain change.

## Step 4: Fan out — one reader per investigation (sonnet)

Spawn the investigations **in parallel**, one subagent each (`general-purpose`, `model: sonnet` — reading transcripts and artifacts for a root cause is standard work, not deep reasoning). Pass paths, never contents. Each gets:

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

Transcript reading hints to include for the subagents: filter with `grep`/`python3` on the jsonl rather than reading it whole; the useful entries are `type:"assistant"` messages with `tool_use` blocks, `toolUseResult` payloads, and the final text. Subagent transcripts for a step live in `<session>/subagents/*.jsonl`.

## Step 5: Corroborate — systemic or one-off

For each finding that came back `skill-defect` or `cycle-definition`, check `$OUT/cycle-history-$TS.md`:

- Does the same skill show a high `mean attempts`, `non-pass slots`, or `$/run` across **other** cycles? → **systemic**. Propose the fix.
- Only this cycle, and the cause traces to this task's specifics? → **one-off**. Propose only if the fix is cheap and safe; otherwise record it as a watch-item with the evidence, so a second occurrence promotes it.
- Contradicted by other cycles (the skill is fine everywhere else)? → say so and drop it.

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
- **Never propose removing comments** — from skills or from code — and never reintroduce a comment-standards or comment-removal step into any flow. This is a standing constraint from CLAUDE.md, not a preference.
- **Respect the suite's own conventions** (AUTHORING.md): caps stay integers fixed at authoring time; a pause always ends the turn; deterministic plumbing goes in `lib/`, not inlined into a SKILL.md; a global skill never loads a repo-specific project skill.
- **Model-tier proposals cite the rubric** — haiku mechanical, sonnet standard, opus expensive-if-wrong — and the measured cost/attempt evidence for the change.
- **A proposal touching CLAUDE.md or AUTHORING.md is a policy change**, not a skill edit. Flag it as such, keep it separate, and never apply it under a general "yes, apply the proposals."
- **No proposal may be a code change to the analyzed repo.** This skill improves the tooling; fixing the product is a different cycle.

## Step 7: Present, then gate application

**Retro mode skips this entire step** — print the summary, report `PASS`, and stop. No menu, no memo, no edits.

Print a compact summary: the verdict, the cost line, what leaked, and the proposals as one line each (`P1 · target file · priority · systemic/one-off`). Point at the artifact. Do not dump the artifact into the conversation.

Then ask — and this **ends the turn**:

- **A) Apply the high-priority proposals** (P<n>, P<n>) — the ones with systemic evidence
- **B) Apply a subset I name**
- **C) Propose only — leave the skills alone for now**
- **―) none of these — add context**

Wait for the actual answer. A quiet human is a blocked task, not approval to start editing the suite (CLAUDE.md: silence is never consent).

**If approved**, apply only the named proposals, exactly as written in the artifact — no scope expansion at apply time. Re-read each target file first, edit, and then append an `## Applied` section to the artifact listing each change and the file it landed in. Leave the skills repo uncommitted unless the human asks for a commit; these are their global tools.

**If running isolated** (no AskUserQuestion): do not apply anything. Raise one decision memo naming the proposals and their priorities:

```bash
ID=$(~/.claude/skills/lib/decide.sh next-id)
```
Write `$OUT/decisions/$ID-analyze-cycle-apply-proposals.md` with the standard frontmatter (`id, title, status: open, raised_by: analyze-cycle, raised_at, resolution:`) and the lettered options above, then report `STATUS: BLOCKED` with `DECISIONS: $ID`.

## Report contract

When invoked as a cycle step, end with exactly:

```
STATUS: PASS | FAIL | BLOCKED
ARTIFACT: <absolute path to cycle-analysis-$TS.md>
SUMMARY: <one sentence — what the cycle cost, what leaked, how many proposals>
FOLLOWUP: <the highest-priority proposal and its target file, or ->
DECISIONS: <memo ids, or ->
```

`PASS` means the analysis completed — including "the cycle was clean, no proposals." A cycle with problems still yields `PASS`; the problems are the product. `FAIL` is for when the analysis itself couldn't run (no such cycle, no readable forensics). In **retro mode**, `BLOCKED` is not an available outcome (see Retro mode above).

## Rules

- Never read a step transcript in this context. Paths to subagents; that's the whole reason the fan-out exists.
- Never estimate cost. Report what the runner recorded, or report that nothing was recorded.
- Never apply a proposal without explicit approval, and never expand past what was approved.
- Never propose a fix for a problem already fixed — Step 2 exists precisely to stop that.
- One cycle is one data point. Label systemic vs one-off on every proposal, and let the history table decide.
- Environmental failures get detect-and-bail proposals, not environment changes.
- Keep your own output short: the confirmation, the triage list, the summary, and the artifact path.
