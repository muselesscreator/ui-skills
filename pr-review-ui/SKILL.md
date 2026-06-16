---
name: pr-review-ui
description: UI-focused PR review. Parallel specialist sub-agents cover design-system usage, accessibility, UI state and data-fetching, render performance, client-side security, and UI test coverage. Bails out early if the PR has no UI files. Loads repo learnings once, scoped to UI topics, and writes them to a file that sub-agents reference by path.
version: 1.2.0
triggers:
  explicit:
    - pr review ui
    - review ui pr
    - review this ui pr
    - review ui changes in pr
  strong_intent:
    - check the ui in this pr
    - look at this ui pr
    - give feedback on ui in pr
  question_form:
    - can you review the ui in this pr
    - what do you think of the ui in pr
exclusions:
  - PRs with no UI changes (use built-in /review or a repo-local pr-review)
  - Creating a PR
  - Generating a PR description
  - Reviewing the local working tree without a PR (use /validate-ui)
confidence_threshold: 80
---

# pr-review-ui

UI-focused PR review. Sub-agents specialize on frontend concerns; non-UI files are noted but not deeply reviewed.

**Arguments**: $ARGUMENTS — PR URL, `owner/repo#N`, `#N`, or `N`. If empty, ask.

Token-economy rules:
- Sub-agents reference the conventions file by path; do NOT embed conventions in prompts.
- Sub-agents read files from disk after checkout; do NOT pass the diff to each agent.
- Load only UI-relevant learnings.

## Step 1: Parse PR Input

Accept URL, `owner/repo#N`, `#N`, or `N`. For number-only, derive owner/repo from `git remote get-url origin`. If empty, ask once and stop.

## Step 2: Fetch PR Data (3 calls, parallel)

```bash
gh pr view $PR_NUMBER --repo $OWNER/$REPO_NAME --json number,title,headRefName,baseRefName,additions,deletions,files,author,state,comments,reviews
gh api repos/$OWNER/$REPO_NAME/pulls/$PR_NUMBER/comments
gh pr diff $PR_NUMBER --repo $OWNER/$REPO_NAME --name-only
```

Compact summary:
```
PR #{n}: {title} | {author} | {head}→{base} | +{add}/-{del} {files} files | {state}
```

If state is MERGED/CLOSED, ask whether to continue.

## Step 3: Classify Files and Gate on UI Content

Categorize each changed file:

- **ui-component** — `.tsx|.jsx|.vue|.svelte`, or under `apps/web|packages/ui|src/components|src/features`
- **ui-style** — `.css|.scss|.sass|.less`, `*.module.css`, tailwind config, theme files
- **ui-hook** — files under `hooks/`, `queries/`, `mutations/`, `stores/`, `state/` that import React/Vue/Svelte primitives
- **ui-story** — `.stories.tsx|.stories.ts|.mdx` under `stories/`
- **ui-test** — `.test.tsx|.spec.tsx|.cy.ts|.cy.tsx|.e2e.ts` referencing UI
- **non-ui** — everything else (api routes, server code, build config, non-UI docs)

**UI gate**: count files in any `ui-*` category. If **zero UI files**:
```
⚠ This PR has no UI changes. /pr-review-ui is UI-focused.
Suggest: built-in /review for a generic pass, or a repo-local pr-review.
Continue anyway? [y/N]
```
If N, stop. If y, proceed but flag in final report that UI focus is mismatched.

If UI files are <30% of total, note this and ask whether the user wants UI-only review (default) or to add a generalist pass alongside.

Hold the file-category map for Step 7.

## Step 4: Checkout PR Branch

```bash
gh pr checkout $PR_NUMBER --repo $OWNER/$REPO_NAME
```

If working tree is dirty, ask before checkout. There is no diff-only fallback.

## Step 5: Load UI Learnings

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")
[ -d "$(git rev-parse --show-toplevel 2>/dev/null)/wiki" ] && SRC=wiki || SRC=flat
```

**If SRC=wiki (work repo — canonical):** query QMD scoped to `collections: ["wiki"]` with an `intent`. Always pull UI gotchas/conventions and component/ui-system/design-system patterns; add keyword-driven sub-queries from the Step 3 file-category map (data-fetching/state for ui-hook, theming/css for ui-style, ui-testing for ui-test, storybook for ui-story) plus an a11y/accessibility query. Read top `qmd://wiki/...` hits.

**If SRC=flat (OSS/reference repo):** read `~/.claude/repo-learnings/$REPO/index.md`, `gotchas.md`, and `ui-patterns.md` always; add `advanced-patterns.md`/`test-patterns.md` per the file-category map.

**If no UI learnings exist**:
```
⚠ No UI learnings for {repo}. Review uses generic UI standards. Run /learn-repo to capture this repo's UI conventions.
```
Proceed.

## Step 6: Write UI Conventions File

Distill to **≤80 lines** at `~/.claude/skill-output/$REPO/$BRANCH/pr-review-ui-conventions.md`:

```
# UI Conventions for PR #{N}

## Gotchas (all)
- {1 line each}

## Design system
- Component library: {name + how it's imported}
- Allowed props/sizes/variants: {1 line each, only the ones reviewers will check}
- Spacing/layout: {flex/gap rules, margin policy}
- Theme tokens: {color/space/typography source of truth}

## State & data
- Data fetching: {TanStack Query / SWR / etc., where hooks live}
- State management: {Zustand / Redux / Context — when each is used}
- Loading/error/empty: {repo's standard pattern}

## Forms
- Library + validation: {RHF + Zod, etc.}
- Controlled vs uncontrolled defaults

## Event handlers
- Naming: {onClick vs onPress, etc.}

## Accessibility
- {1 line each: ARIA conventions, focus management, keyboard expectations}

## Testing
- Component test patterns: {RTL setup, custom render, fixture conventions}
- E2E: {framework, selector strategy, intercept conventions}
```

Sections with no loaded content: write `(none captured)` so reviewers know it was checked.

This file is the **single source** sub-agents reference. Do not embed elsewhere.

## Step 7: Parse Existing Comments

From Step 2, filter bots (`vercel`, `graphite-app`, `github-actions`, `coderabbitai`, `codecov`). Group open inline comments by file:line. Skip the comments agent in Step 8 if zero open.

## Step 8: Spawn UI Review Agents (parallel, single batch)

Each agent gets a short prompt (≤15 lines). Common preamble:

```
Review PR #{N} ({title}) in {OWNER}/{REPO_NAME}. Branch checked out — read files from disk.

UI conventions: ~/.claude/skill-output/{REPO}/{BRANCH}/pr-review-ui-conventions.md
Read only sections relevant to your focus.

Files (your category only): {filtered list}

Focus: {agent-specific list}

Report: SEVERITY | file:line | issue | fix. Severity ∈ {BLOCKING, SHOULD-FIX, SUGGESTION}.
Skip non-UI concerns. Do not flag anything the conventions explicitly allow. No generic nits.
```

**Agents** (spawn only those whose category exists in the file mix). Spawn each with the **Task** tool, passing the `model` tier shown in parentheses — correctness-critical lenses get `opus`, standard lenses `sonnet`, mechanical lenses `haiku`. With up to 8 agents in one parallel batch, demoting the cheap lenses is most of the savings.

1. **design-system** (sonnet) — ui-component, ui-style. Component library usage (valid props, sizes, variants, slots), layout patterns (flex/gap vs margin), spacing scale adherence, theme token usage vs raw values, anti-pattern: building custom when a primitive exists.

2. **a11y** (opus) — ui-component. Semantic HTML, ARIA roles/attrs correctness (and unnecessary ARIA), focus management (visible focus, trap/restore in modals), keyboard nav (tab order, Enter/Space/Escape handlers), screen-reader text (alt, labels, aria-label/labelledby), color-contrast assumptions, motion/reduced-motion.

3. **ui-state** (sonnet) — ui-component, ui-hook. Loading/error/empty states present and correct, data fetching uses repo's hook pattern, cache invalidation/refetch correctness, race conditions, state collocated at right level (no prop drilling vs no over-globalizing), form validation flow.

4. **ui-perf** (sonnet) — ui-component, ui-hook. Unnecessary re-renders (stable refs, memo only where measured), large list virtualization, image sizing/loading, bundle-size red flags (heavy imports, default-exporting whole libs), Suspense/skeleton usage.

5. **ui-security** (opus) — ui-component, ui-hook. XSS via `dangerouslySetInnerHTML`/`v-html`/`{@html}`, unsanitized user content rendered as markup, `href={userInput}`, target="_blank" without rel="noopener", token/PII in client-side state or localStorage, CSP-violating inline handlers.

6. **ui-testing** (sonnet) — ui-test, plus ui-component/ui-hook (to check coverage gaps). New UI behavior has a test, tests assert user-visible behavior (role/text queries), no implementation-detail tests, accessible queries used, E2E selectors stable and match repo convention.

7. **ui-docs** (haiku) — ui-story, .md files describing UI. Stories cover new variants/states, design-system docs updated when tokens/components change.

8. **comments** (haiku) — only if Step 7 found open comments. Status per comment: ADDRESSED / PARTIAL / NOT-ADDRESSED with commit SHA or quoted reply.

**Non-UI files**: if `non-ui` category is non-empty, do NOT spawn a generalist agent. Instead, note in the final report:
```
ℹ Non-UI files not reviewed: {list}. Use built-in /review or repo-local pr-review for those.
```

Run all applicable agents in **one parallel batch**.

## Step 9: Synthesize & Report

Dedupe findings (same file:line from multiple agents). Group by severity.

```
## UI PR Review: #{N} — {title}

Verdict: BLOCKING | APPROVE-WITH-COMMENTS | APPROVE
Counts: B={n} SF={n} S={n}

### Blocking
- `{file}:{line}` [{agent}] {issue} → {fix}

### Should Fix
- {same format}

### Suggestions
- {same format}

### Existing Comments ({open}/{total})
- {status} `{file}:{line}` ({author}): "{preview}" — {evidence}

### Coverage: design-system {✓|—} a11y {✓|—} ui-state {✓|—} ui-perf {✓|—} ui-security {✓|—} ui-testing {✓|—} ui-docs {✓|—} comments {✓|—}

{If non-ui files present: ℹ Non-UI files not reviewed: {count}}
{If any agent failed: ⚠ {agent} failed — category not covered}
```

No decorative banners.

## Step 10: Write Report

```bash
BRANCH=$(git branch --show-current | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write to `~/.claude/skill-output/$REPO/$BRANCH/pr-review-ui-$PR_NUMBER-$TS.md`:
```
---
skill: pr-review-ui
repo: {repo}
pr_number: {N}
verdict: {…}
counts: {b:N, sf:N, s:N}
ui_files: {N}
non_ui_files: {N}
---
```
Plus the report from Step 9.

Then ask: post comments / dig into a finding / done. If posting, show `gh` commands and confirm each — never auto-post.
