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
# Repo name
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//' || node -e "console.log(require('./package.json').name.replace('@','').replace('/','--'))")
echo "Repo: $REPO"
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

Create or overwrite `~/.claude/repo-learnings/$REPO/`:

**index.md:**
```markdown
# {repo-name} Learnings
Last analyzed: {ISO date}
Scope: {full | path/to/scope}

## Summary
[2-3 sentence description of what kind of codebase this is]

## Reference Implementations
[1-3 files/features that best exemplify the patterns]

## Learnings Files
- ui-patterns.md — component and data layer patterns
- file-structure.md — where things live
- gotchas.md — anti-patterns and traps
- test-patterns.md — test conventions
- standards.md — inferred project standards
```

**ui-patterns.md:** Component patterns, data flow, state management, naming
**file-structure.md:** Directory conventions, key paths, reference files
**gotchas.md:** Anti-patterns, deprecations, known traps
**test-patterns.md:** All test conventions (used by _test-context)
**standards.md:** Inferred standards — what the codebase consistently does

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
