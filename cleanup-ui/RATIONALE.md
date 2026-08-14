# cleanup-ui — rationale

Incident record for the rules in `SKILL.md`. Not loaded at runtime. See
`~/.claude/skills/AUTHORING.md` § Rationale files.

This skill runs on **haiku** in `eli-feature-cycle`, so its `SKILL.md` deliberately
keeps prescriptive density — exact commands, the decision-memo procedure inline,
literal report strings — per AUTHORING.md § Prose tiering. Do not "simplify" it to
match the opus-tier skills; the tiering is the point.

### Only files in `$OUT/cleanup-scope-changed.txt` may be edited

An error surfacing in a file outside the branch's change set is pre-existing. It is
named in the report as a residual and left alone.

**Why:** a cleanup pass that touched 16 files the branch never asked about. That is
not a broader version of success — it is the failure mode, because it puts unrelated
edits in a commit whose message describes something else, and it makes the diff
unreviewable for the human who has to approve it.

### Never remove an existing type assertion, non-null `!`, or `eslint-disable`

A suppression that now *looks* redundant is far more often a symptom of an unclean
environment for that exact spot — stale build cache, partially regenerated client,
project reference not rebuilt — than a genuinely dead guard. An assertion bridging a
real Prisma-type-vs-domain-type gap will pass a broken environment's check the
moment it is deleted and break the instant the environment is fixed, silently,
because nothing caught it at delete time.

### Unused variables are deleted, never `_`-prefixed

Standing constraint from Ben's global CLAUDE.md. Underscore-prefixed dead code reads
as intentionally-kept and outlives the reason it was spared.

### The internal verify loop caps at 3 rounds

Independent of, and smaller in scope than, `orch-ui`'s step-level `remediate`. This
skill only reports `STATUS` upward once its own loop has applied-and-verified or
exhausted the cap and surfaced a cap-exhaustion menu. A fix the model believes will
work does not count — only a fresh `lib/cleanup-verify.sh` pass does.
