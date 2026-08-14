# validate-ui — rationale

Incident record for the rules in `SKILL.md`. Not loaded at runtime. See
`~/.claude/skills/AUTHORING.md` § Rationale files.

### Unrelated concurrent work on the branch is not a validation finding

**Where:** `dev-screen` / `home-cleanup`. Two opus attempts were spent reporting
that "three streams of unrelated concurrent work share the uncommitted tree." The
observation was accurate and completely irrelevant to whether the feature matched
its spec — the most expensive model in the suite, twice, on a non-finding. Scope
the tree check through `lib/plan-scope-check.sh` and treat only an intersection as
in scope.

### The human-only gap exception routes to `BLOCKED`, not `FAIL`

`orch-ui`'s bounded remediation fires on `FAIL`. When every remaining gap is a
mandated manual, visual, or in-browser check with no automation surface in the
environment, a `FAIL` spends remediation rounds on work no code change can do —
and then halts the cycle anyway. `BLOCKED` puts it in front of the human on the
first pass instead.

The exception requires *zero* remaining code-level gaps: one fixable `✗` means the
normal `GAPS FOUND` verdict applies. That condition is enforced arithmetically by
`lib/validation-verdict.sh` (`--human-only-gaps N` is honored only when `N` equals
the total gap count), because as prose it was a carve-out an opus step re-derived
on every run.

### Verdict arithmetic lives in `lib/`, not in this skill

The gap/unrequested counting rule and its precedence were a prose paragraph here
for several revisions. Counting is a computation; handing a computation to opus as
reasoning material buys nothing and costs deliberation on every run. What stays in
the skill is the part that is genuinely judgment: *which* findings earn a `✗` or
`⚠` mark in the first place.
