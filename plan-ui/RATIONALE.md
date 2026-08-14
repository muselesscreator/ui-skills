# plan-ui — rationale

Incident record for the rules in `SKILL.md`. Not loaded at runtime. See
`~/.claude/skills/AUTHORING.md` § Rationale files.

### Open Questions are resolved in this conversation the moment they are answered

An Open Question that stays open after the human answers it in chat resurfaces
later in the dev-screen Resolve-decision card, and the same answer gets entered a
second time through a slower surface. Worse, `impl-ui` refuses to start while a
memo from its plan is open — so an answered-but-unrecorded question stalls the
cycle on a question that has, in fact, been answered.

Partial answers are resolved partially and the rest re-asked, rather than held as a
batch waiting for one complete reply, for the same reason.

### Presentation-layer decisions are deferred to `impl-ui`

Semantic element choice, the CSS approach, and `className`/token composition are not
planning judgments — deciding them here produces a plan that reads as authoritative
about markup it never saw in context, and `impl-ui`'s presentation pass then either
contradicts it or follows it badly. The plan names the *convention* to follow and
its reference file; the pass resolves the markup.

### The plan HTML comes from a template, never from the model

`lib/render-plan-artifact.sh` wraps `plan-*.md` into `plan-ui/plan-template.html`.
Authoring plan HTML in-session cost context for a page that never varies, so if the
page needs to change, the template changes — not the skill prose.
