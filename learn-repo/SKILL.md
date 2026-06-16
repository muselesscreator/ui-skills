---
name: learn-repo
description: Analyzes an OSS/reference repo's code and writes structured flat-file learnings to ~/.claude/repo-learnings/{repo}/. For repos with no ./wiki/ (a work repo's canonical knowledge belongs in its wiki via /wiki-braindump + /wiki-ingest instead). Accepts an optional path to scope analysis. Use when starting work on an unfamiliar codebase.
version: 1.0.0
triggers:
  explicit:
    - learn repo
    - analyze repo
    - learn this codebase
    - analyze this feature
  strong_intent:
    - learn the patterns here
    - understand this codebase before I start
    - what patterns does this project use
confidence_threshold: 80
---

# learn-repo

**Arguments**: $ARGUMENTS (optional: path or component to scope analysis)

Analyze the current repo's code — components, patterns, conventions, test structure — and write learnings to `~/.claude/repo-learnings/{repo-name}/`. Does NOT read steering docs. Source of truth is the code itself.

## Step 1: Identify Repo and Scope

```bash
# Repo name — derive from the remote so it's stable across git worktrees
# (basename of the worktree dir would key learnings under the worktree name, not the repo).
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)
[ -z "$REPO" ] && REPO="no-repo"
echo "Repo: $REPO"

# Work-repo guard: if this repo has a ./wiki/, its canonical knowledge belongs in the wiki,
# not in flat learnings. Stop and route to the wiki workflow instead.
if [ -d "$(git rev-parse --show-toplevel 2>/dev/null)/wiki" ]; then
  echo "This repo has a ./wiki/ — capture code knowledge via /wiki-braindump then /wiki-ingest, not /learn-repo."
  echo "(/learn-repo is for OSS/reference checkouts that have no wiki.)"
  exit 0
fi

# Short-circuit if learnings already exist
LEARNINGS_DIR=~/.claude/repo-learnings/$REPO
if [ -d "$LEARNINGS_DIR" ] && [ -f "$LEARNINGS_DIR/index.md" ]; then
  echo "Existing learnings found at $LEARNINGS_DIR"
  echo "Use /update-learnings to refresh, or continue to do a full re-analysis."
  # Stop here unless the user explicitly asked for a full re-analysis
  exit 0
fi
```

If a path argument was given: analysis is scoped to that path. Learnings are written to `~/.claude/repo-learnings/$REPO/scoped/{slug}.md` and `index.md` is updated with a pointer.

If no argument: full repo analysis. Write all learnings files.

## Step 2: Structural Analysis

For **full repo**:
- Read root `package.json` and workspace config to understand the monorepo shape
- Identify app entry points, key packages, domain boundaries
- Find the UI entry points (apps with frontend code)
- Identify the component library / design system package

For **scoped path**:
- Read files in and around the given path
- Understand the feature's structure, what it imports, how it's organized

## Step 3: UI Pattern Analysis

Analyze frontend code to capture:

**Component patterns:**
- How are components structured? (presentational vs container, size limits)
- What design system / component library is used?
- How are layouts composed? (flex, grid, spacing conventions)
- What props patterns are consistent?
- What patterns appear 3+ times (worth documenting)?

**Data layer patterns:**
- How does server data flow into components? (REST, tRPC, GraphQL, other)
- Where does UI state live? (Zustand, Redux, Context, component state)
- Is there a consistent hook composition pattern?
- How are mutations triggered and errors handled?

**File organization:**
- What is the directory structure convention? (feature-based, type-based, other)
- Where do components live relative to views?
- Where do hooks, utilities, constants, types live?
- What is the "deepest" import pattern you see regularly?

**Naming conventions:**
- Component naming
- Hook naming
- File naming
- Test file naming

## Step 3.5: Tooling Config Analysis

Read and extract enforcement config. This feeds into `standards.md` so `plan-ui` can load it without re-reading config files each time.

**TypeScript:**
```bash
find . -name "tsconfig*.json" -not -path "*/node_modules/*" | head -10
```
Read root and any app-level tsconfigs. Record:
- Which strict flags are active (list explicitly — do not just say "strict: true", enumerate what that enables)
- Any path aliases configured (`paths`) — these affect import style
- `lib` and `target` settings if they constrain API usage

**ESLint:**
```bash
find . -maxdepth 3 \( -name ".eslintrc*" -o -name "eslint.config.*" \) | grep -v node_modules | head -5
```
Read the config. Record:
- Import ordering rules (plugin, rule name, exact group order)
- Rules banning common shortcuts: `no-explicit-any`, `no-non-null-assertion`, `no-restricted-imports`, etc.
- JSX/React-specific rules
- Any rules set to `error` that are commonly triggered during feature work
- `eslint-disable` comments in source — these mark rules the team finds hard to satisfy and are worth noting

**Prettier:**
```bash
find . -maxdepth 3 \( -name ".prettierrc*" -o -name "prettier.config.*" \) | grep -v node_modules | head -3
```
Record non-default settings. If no config found, note "Prettier defaults assumed."

## Step 4: Test Pattern Analysis

Scan test files to capture (feed into `_test-context` output format):
- Test file placement and naming
- Mock patterns for the most common dependencies
- Factory/fixture patterns
- Async assertion style
- E2E: intercept patterns, page object structure, wait strategy

## Step 5: Gotchas and Anti-Patterns

Look for code comments containing `// NOTE:`, `// HACK:`, `// TODO:`, `// FIXME:`, `// WARNING:`, `// IMPORTANT:`, and `@deprecated`. Also look for `eslint-disable` comments — they often mark known awkward patterns.

Capture these as gotchas in `gotchas.md`.

## Step 6: Reference Implementations

Identify 1-3 files or features that represent the cleanest, most idiomatic examples of the codebase's patterns. These become the "read this first" references in `index.md`.

## Step 7: Write Learnings

Write flat markdown files to `~/.claude/repo-learnings/$REPO/`. Each file starts with a one-line `Last analyzed: {ISO-date}` and a short scope line. Keep them concise and synthesized — these feed `load-learnings` (distilled to ≤200 lines) and `synthesize-patterns` (cross-repo), so favor durable rules over verbatim code.

```bash
LD=~/.claude/repo-learnings/$REPO
mkdir -p "$LD"
```

Write these files (the established layout — only the ones the analysis actually produced):
- `index.md` — written **last**. Summary, reference implementations (1-3 cleanest examples), and a pointer list to the other files. Include `Last analyzed: {date}`.
- `ui-patterns.md` — component structure, design-system wrappers, data-fetching, state-management, hook composition.
- `advanced-patterns.md` — deeper/rarer patterns worth recording separately (optional).
- `file-structure.md` — directory conventions, where things live, naming.
- `gotchas.md` — anti-patterns and traps (one line each).
- `test-patterns.md` — unit (Vitest) + E2E (Cypress) conventions, mocks, fixtures, wait strategy.
- `standards.md` — enforced TS strict flags, ESLint rules that reject common patterns, Prettier non-defaults.

For a **scoped run** (path argument given): write `~/.claude/repo-learnings/$REPO/scoped/{slug}.md` and add a pointer to it in `index.md` rather than rewriting the top-level files.

## Step 8: Confirm

```
✅ Learnings written for {repo-name}
Scope: {full | path/to/scope}
Location: ~/.claude/repo-learnings/{repo-name}/

Files written:
- index.md
- ui-patterns.md
- file-structure.md
- gotchas.md
- test-patterns.md
- standards.md

Reference implementations identified:
- {path/to/reference1}
- {path/to/reference2}

Run /update-learnings to refresh after major changes.
```
