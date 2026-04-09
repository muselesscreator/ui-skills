---
name: learn-repo
description: Analyzes the current repo's code and writes structured learnings to ~/.claude/repo-learnings/{repo}/. Repo-agnostic. Accepts an optional path to scope analysis to a specific feature or file. Use when starting work on an unfamiliar codebase or before implementing a feature.
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
# Repo name — use git root dirname, no remote lookup needed
REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null || pwd))
echo "Repo: $REPO"

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

Write to the Obsidian vault at `/Users/bwarzeski/.claude/obsidian-vault/repo-learnings/$REPO/` using `create-note` MCP calls. All notes must include frontmatter with `repo`, `category`, `tags`, and `last-updated` fields.

**Vault path:** `/Users/bwarzeski/.claude/obsidian-vault/repo-learnings/$REPO/`

**Frontmatter schema for every note:**
```yaml
---
repo: {repo-name}
category: {ui-patterns | gotchas | test-patterns | standards | file-structure | index}
tags:
  - repo/{repo-name}
  - category/{category}
  - topic/{specific-topic}   # one or more topic tags (see below)
last-updated: {ISO-date}
---
```

**Topic tags to use:**
- `topic/components` — component structure, props, presentational/container split
- `topic/data-fetching` — API hooks, query patterns
- `topic/state-management` — Zustand, XState, local state
- `topic/forms` — form patterns
- `topic/testing` — any test content
- `topic/e2e` — Cypress-specific
- `topic/unit-tests` — Vitest-specific
- `topic/file-placement` — where things go, naming
- `topic/typescript` — TS config, strict flags
- `topic/eslint` — lint rules
- `topic/gotcha` — traps and anti-patterns
- `topic/design-system` — component library wrappers

**Note structure (split from the old flat files):**

Create notes in these subdirectories:
- `ui-patterns/component-structure.md` — presentational/container split, props conventions. Tags: `topic/components`
- `ui-patterns/design-system.md` — component library wrapper rules. Tags: `topic/design-system`, `topic/components`
- `ui-patterns/data-fetching.md` — API hooks, query patterns. Tags: `topic/data-fetching`
- `ui-patterns/state-management.md` — state libraries and rules. Tags: `topic/state-management`
- `ui-patterns/hook-composition.md` — custom hook patterns. Tags: `topic/components`, `topic/state-management`
- `file-structure.md` — directory conventions, naming. Tags: `topic/file-placement`
- `gotchas/component-antipatterns.md` — Tags: `topic/gotcha`, `topic/components`, `topic/design-system`
- `gotchas/state-antipatterns.md` — Tags: `topic/gotcha`, `topic/state-management`
- `gotchas/form-traps.md` — Tags: `topic/gotcha`, `topic/forms`
- `gotchas/test-traps.md` — Tags: `topic/gotcha`, `topic/testing`
- `test-patterns/e2e-patterns.md` — Tags: `topic/testing`, `topic/e2e`
- `test-patterns/unit-patterns.md` — Tags: `topic/testing`, `topic/unit-tests`
- `standards/typescript.md` — Tags: `topic/typescript`
- `standards/eslint.md` — Tags: `topic/eslint`
- `standards/prettier.md` — Tags: `topic/eslint`

Create notes using MCP:
```
mcp__obsidian__create-note: vault="obsidian-vault", filename="{note}.md", folder="repo-learnings/{repo-name}/{subfolder}", content="{frontmatter + content}"
```

Create `index.md` last (it references all other notes). It should list all notes created under "Learnings Notes" and include the summary and reference implementations.

**Also write flat files as fallback** to `~/.claude/repo-learnings/$REPO/` using the original format, so skills that haven't been updated yet continue to work.

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
