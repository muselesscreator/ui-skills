---
name: simple-task
description: Implement → cleanup → commit, for a small, already-understood UI change (a test tweak, a copy/style fix, a one- or two-file modification). Skips the analyze / plan / validate passes the feature-cycle runs — no opus steps. Use when the change is already scoped and specified and there's no architecture to reason about.
steps:
  - id: impl
    skill: impl-ui
    args: "$TASK"
    model: sonnet
    stop_on_fail: true
    note: Implements $TASK directly from the description (plus any plan/handoff impl-ui finds on its own). sonnet — standard build. No analyze/plan step precedes it, so $TASK must be specific enough to build from; if it isn't, use feature-cycle instead.
  - id: cleanup
    skill: cleanup-ui
    args: ""
    model: haiku
    stop_on_fail: true
    note: Lint, type-check, dead-code, and test fixes on the branch diff (calls cleanup-unit-tests / cleanup-e2e-tests if test files are touched). haiku — mechanical.
  - id: commit
    skill: commit-branch
    args: ""
    model: haiku
    stop_on_fail: true
    note: Stage + commit (no push). Message generated from the diff. haiku — mechanical.
---

# simple-task

Run with: `/orch-ui simple-task <what to change>` — or just `/orch-ui <description>`
and pick `simple-task` at the confirm prompt.

The lightweight loop for a change you already understand: **impl → cleanup →
commit**. No `analyze`, no `plan`, no `validate`, and **no opus steps** — the whole
cycle runs on sonnet + haiku.

## When to use this instead of feature-cycle

Reach for `simple-task` when the change is **already scoped and specified** and
there's no architecture to reason about or user-facing behavior to confirm:

- a test-only change (add/refactor a test, de-mock a fixture)
- a copy, style, or className fix
- a one- or two-file modification you (or a prior `/savepoint` handoff) have
  already pinned down

For these, the feature-cycle's `analyze` + `plan` (opus) + `validate` (opus) passes
are pure overhead: there's nothing to discover that a fixed-template artifact would
surface, and "tests / type-check pass" *is* the validation. Dropping those four
steps removes both opus passes and ~4 subagents.

## When NOT to use it — fall back to feature-cycle

- The change spans several files or domains, or its blast radius is unknown.
- The approach isn't decided — you need a plan before writing code.
- The result needs a behavioral gate (does it actually do what was asked?) beyond
  lint/type/tests.
- You want the wiki-capture (`braindump` / `ingest`) steps — those live in
  feature-cycle.

`impl-ui` still loads repo learnings and will pick up an existing `plan-*.md` or
`handoff-latest.md` on its own, so `simple-task` benefits from prior context
without re-deriving it. `cleanup` and `commit` are the same steps feature-cycle
runs.
