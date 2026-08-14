# orch-ui — rationale

Incident record for the rules in `SKILL.md`. Not loaded at runtime. See
`~/.claude/skills/AUTHORING.md` § Rationale files.

### `$TASK` is normalised to the bare requirement before substitution (Step 0)

A cycle invoked through a wrapper can arrive with `$ARGUMENTS` already wearing a
skill-invocation preamble. Steps that treat `$TASK` as the requirements spec —
`validate-ui` above all — then grade the implementation against *an instruction to
invoke a skill* rather than against the feature.

**Where:** `dev-screen` / `home-cleanup`. All three of analyze, plan, and validate
received `args` beginning `"Invoke the analyze-task skill with arguments: …"`. The
normalised task is echoed back in the Step 0 confirmation specifically so a human
can catch a bad strip before six steps run on it.

### A dead step with no five-line report is `FAIL`, never left `running`

Existence of a result file is not liveness, and a wrapper's death is not the
session's death.

**Where:** `dev-screen` / `home-cleanup`. A remediation wrapper died on an unrelated
crash while its headless session kept running for roughly twenty more minutes and
did emit a valid `STATUS: PASS` — which nothing captured, because the thing that
would have captured it was gone. The step displayed "Remediating" indefinitely; a
human spent 84 turns hand-patching `manifest.json` to get the cycle unstuck. This
is why the rule is written as a cross-runner obligation rather than as advice to
this skill: the runner that has to honor it is often not this one.

### `stop_on_fail: true` cannot be overridden by a manual step jump

Same class of problem: a cycle that advanced past an unpassed gate is
non-conformant, not `completed`, and `lib/cycle-forensics.py` flags it as
`stop-on-fail-bypassed`. The value of the gate is entirely in its being
unskippable, including by the human driving the runner UI.
