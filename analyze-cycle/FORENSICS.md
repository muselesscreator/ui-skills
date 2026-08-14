# What `cycle-forensics.py report` extracts

Full inventory of the deterministic forensics report `analyze-cycle` Step 1 generates.
Reference material, not instructions — `SKILL.md` names the categories; this file is
here for when you need to know exactly what a section contains.

Everything below is already extracted mechanically. Never re-derive any of it by hand,
and never read a step transcript in the analyzing context to get it.

## Ledger and cost

- **Step ledger** — per step: skill, model tier, status, attempts, remediation rounds, cost, wall time.
- **Attempt table** — every isolated run: model, status, cost, output and cache-read tokens, session id, artifact.
- **Cost rollups** by step and by model.
- **Step summaries** — each run's `SUMMARY` / `FOLLOWUP` / `DECISIONS` lines.
- **Artifact inventory** — sizes, and which artifacts came back empty.
- **Decision memos** with their status.

Cost is **reported, never computed** — no price table is embedded anywhere in the
suite, because a stale constant is worse than an honest token count. On the
in-session `/orch-ui` runlog surface there is no cost data at all; that surface
supports no cost findings.

## Sessions — the leak record

- **Session map** — the sessions the cycle owned, plus the **unlinked** ones: same
  branch, not part of the cycle. Each carries:
  - a window label — `inter-cycle` / `during` / `after`
  - an **`attributed_to`** naming which cycle it belongs to (the label alone is not
    attribution — an `inter-cycle` session is the *previous* cycle's leak)
  - `🔴 STILL ACTIVE` if the session is live right now
  - title, first real prompt, turn count, slash commands used, files edited
  - whether the session **hand-edited the skill suite** — the human already
    diagnosed something; read their edit before proposing your own
- **Live rework** — files a cycle step edited that an outside session then edited
  again. Read from transcript edit-lists, so it appears the moment it happens and
  needs no commit.
- **Intra-cycle rework** — files two different steps of the same cycle both edited: a
  later step patching an earlier one, which means the seam between them is wrong.

The evidence window opens at **the end of the previous cycle on this branch** and
holds open to now. That is what makes retros compound.

## Repo state

- **Working tree right now** — uncommitted changed and untracked files. Mid-cycle
  this is often where the entire diff still lives.
- **Commits** bucketed `inter-cycle` / `during` / `after`.
- **Rework files** — shipped by this cycle, edited again by a later commit.
- **Inter-cycle rework** — hand-fixed before this cycle and touched again by it,
  meaning the previous cycle left it wrong.
- Files that only later commits touched.

## Mechanical flags

Retries, non-pass steps, contract violations (including `stop-on-fail-bypassed`),
crashes, cost outliers, cache-read hotspots, empty artifacts, open decision memos,
unlinked fix-sessions, and rework.

## Other subcommands

- `list` — enumerate cycle runs.
- `history --limit N` — per-skill aggregates across cycles (`mean attempts`,
  `non-pass slots`, `$/run`). This is the systemic-vs-one-off evidence Step 5 needs.
- `sessions` — the session map as JSON.

Both surfaces are handled: cycle-runner dirs (`$OUT/cycles/<id>/manifest.json` plus
per-attempt request/result/usage/log files, with real USD) and in-session `/orch-ui`
runlogs (`$OUT/orch-run-*.md`, no cost data).
