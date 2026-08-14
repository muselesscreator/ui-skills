# impl-ui — rationale

Incident record for the rules in `SKILL.md`. Not loaded at runtime. See
`~/.claude/skills/AUTHORING.md` § Rationale files.

### Collision checks are scoped to the plan's files, never the whole dirty tree

`lib/plan-scope-check.sh` compares the working tree against `$OUT/plan-files.txt`
(written by `plan-ui`). A dirty tree that does not intersect the plan is unrelated
parallel work on a shared branch — not a collision, and not a reason to pause.

**Where:** `dev-screen` / `home-cleanup`. Steps running their own unscoped
`git status` and escalating on anything dirty produced five separate blocking
rounds across three steps, each one asking the human about work the step was never
going to touch. Hence both halves of the rule: use the script, and do not
second-guess it with a broader scan afterwards.

### Worker-raised memos are resolved inside this skill, not deferred to a UI

`impl-ui` runs in the calling (interactive) session, so it has AskUserQuestion. A
memo left open here surfaces later in the dev-screen Resolve-decision card, and the
human ends up entering the same answer a second time through a slower surface.
Resolving in place also keeps the respawn narrow — only the workers that actually
had a blocked file get re-run.

### The type gate lives here, before validation

`validate-ui` runs on opus in `eli-feature-cycle`. A type error that survives
implementation spends an expensive behavioral validation on code that cannot
compile. The gate is scoped to type-check only; lint, Prettier, dead code, and
tests belong to `cleanup-ui`, which runs on haiku.
