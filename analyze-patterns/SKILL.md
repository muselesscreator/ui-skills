---
name: analyze-patterns
description: Analyzes a codebase for effective, clean, and scalable code patterns. Does a top-level sweep, confirms scope with the user, then provides concrete examples with file:line references. Focuses on file organization, novel abstractions, composable solutions, and repeatable conventions worth emulating.
version: 1.0.0
triggers:
  explicit:
    - analyze patterns
    - find patterns
    - show me good patterns
    - what patterns does this codebase use
    - analyze codebase patterns
    - show patterns
  strong_intent:
    - what's worth copying from this codebase
    - what are the best patterns here
    - show me how this codebase solves problems
    - what should I know before writing code here
    - what are the architectural patterns
confidence_threshold: 75
---

# analyze-patterns

**Arguments**: $ARGUMENTS (optional: focus hint — e.g. "UI only", "data layer", "state management")

Analyze the current codebase for effective, reusable, and scalable patterns. This is not a doc-generation task — it is a pattern-appreciation pass. The goal is to surface patterns worth **emulating**, not merely document conventions.

---

## Step 1: Top-Level Sweep

Gather orientation data. Run these in parallel:

```bash
# Repo identity
REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null || pwd))
echo "=== Repo: $REPO ==="

# Directory structure (top 3 levels, no node_modules / dist / .git)
find . -maxdepth 3 \
  -not -path '*/node_modules/*' \
  -not -path '*/.git/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  -not -path '*/.next/*' \
  -not -path '*/coverage/*' \
  -type d | sort | head -80

# File counts by extension (top 15)
find . -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/dist/*' \
  -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -15

# Package / dependency manifest (reveals stack)
cat package.json 2>/dev/null || cat go.mod 2>/dev/null || cat Cargo.toml 2>/dev/null || cat pyproject.toml 2>/dev/null || cat requirements.txt 2>/dev/null | head -40
```

From this sweep, determine:
- **Project type**: frontend SPA, full-stack, API server, monorepo, library, etc.
- **Tech stack**: framework, language, major dependencies
- **Scale**: approximate file count, top-level modules/packages
- **Dominant pattern areas** present in this codebase (only list what actually exists):
  - `file-organization` — directory layout, co-location conventions, naming
  - `ui-components` — component patterns, composition, design system usage
  - `data-fetching` — API calls, query libraries, caching
  - `state-management` — global/local state, stores, context
  - `api-design` — route structure, middleware, handlers (backend)
  - `type-system` — TypeScript patterns, generics, discriminated unions
  - `abstractions` — custom hooks, utilities, composable helpers
  - `testing` — test structure, mocking patterns, factories
  - `error-handling` — error boundaries, result types, try/catch patterns
  - `performance` — memoization, lazy loading, code splitting

---

## Step 2: Confirm Scope with User

Present a brief sweep summary and proposed investigation plan:

```
## Codebase Snapshot: {repo-name}

**Stack**: {detected stack}
**Scale**: ~{N} source files across {N} top-level modules
**Type**: {frontend / backend / fullstack / monorepo}

**Areas I detected (and plan to analyze):**
1. File organization — {one-line observation, e.g. "feature-based structure with co-located tests"}
2. {Area} — {one-line observation}
3. {Area} — {one-line observation}
...

**What I'll look for:** clean abstractions, patterns that appear 3+ times, novel solutions to common problems, and structural choices that scale well.

---
Shall I analyze all of the above, or focus on specific areas?
(e.g. "just UI and state", "skip testing", "focus on the data layer")
```

Use `AskUserQuestion` to receive the user's focus preference before proceeding. If $ARGUMENTS already contains a focus hint (e.g. "UI only"), skip the question and use that directly.

After receiving user input, filter the areas list to only those the user wants. Proceed with only those areas.

---

## Step 3: Deep Analysis by Area

For each confirmed area, run targeted analysis. Be specific — cite actual file paths and line ranges. Quote short snippets inline. Do not paraphrase; show the code.

---

### Area: file-organization

Goal: understand the structural reasoning behind the directory layout.

```bash
# Top-level structure (already have from Step 1)
# Check for barrel files (index.ts re-exports)
find . -name "index.ts" -o -name "index.tsx" | grep -v node_modules | grep -v dist | head -20

# Check for co-location patterns (tests near source)
find . -name "*.test.*" -o -name "*.spec.*" | grep -v node_modules | head -20 | xargs dirname | sort | uniq -c | sort -rn | head -10

# Monorepo: check workspace structure
cat pnpm-workspace.yaml 2>/dev/null || cat lerna.json 2>/dev/null || (cat package.json 2>/dev/null | grep -A10 '"workspaces"')
```

Read 2-3 representative directories in depth. Look for:
- **Feature-based vs type-based** grouping (e.g. `features/checkout/` vs `components/`, `hooks/`, `utils/`)
- **Barrel exports** — do `index.ts` files form a clean public API for each module?
- **Co-location** — are tests, styles, types next to the component or centralized?
- **Naming discipline** — consistent suffixes like `*.store.ts`, `*.service.ts`, `*.hook.ts`?
- **Depth discipline** — is nesting kept shallow? Is there a clear rule?

**What makes it notable**: call out any structural choice that actively prevents problems — e.g. "barrel files enforce a clear module boundary so internal helpers can't be imported directly from outside."

---

### Area: ui-components

Goal: find the component patterns that compose well and stay maintainable.

```bash
# Find components (not pages/views — those are likely larger)
find . -name "*.tsx" -o -name "*.jsx" | grep -v node_modules | grep -v dist | grep -v ".test." | grep -v ".spec." | head -60

# Find the design system / component library entry point
find . -path "*/components/index*" -o -path "*/ui/index*" | grep -v node_modules | head -5
```

Read 4-6 component files, prioritizing:
- Small, reusable leaf components (buttons, inputs, cards)
- A medium-complexity composite (a form, a list with controls)
- A layout component (if present)
- The most-imported component (find via `grep -r "import.*from.*ComponentName" --include="*.tsx"`)

Look for:
- **Composition over configuration** — does the design use `children` / slot props instead of boolean flags?
- **Prop drilling avoidance** — context, compound components, or render props used thoughtfully?
- **Abstraction seams** — thin wrappers around a library that provide consistent defaults?
- **Polymorphic or as-prop patterns** — flexible element type without losing type safety?
- **Clean conditional rendering** — are complex ternaries extracted to variables or sub-components?

---

### Area: data-fetching

Goal: find how the codebase handles async server data cleanly.

```bash
# Find API/query hooks
find . -name "use*.ts" -o -name "use*.tsx" | grep -v node_modules | grep -iE "(query|fetch|api|data|load|request)" | head -20

# Find API client setup
find . -not -path "*/node_modules/*" \( -name "api.ts" -o -name "client.ts" -o -name "http.ts" -o -name "fetcher.ts" \) | head -10

# Check for React Query / SWR / tRPC / Apollo
grep -r "useQuery\|useMutation\|useSWR\|trpc\." --include="*.ts" --include="*.tsx" -l | grep -v node_modules | head -10
```

Read the API client setup file and 3-4 query hooks. Look for:
- **Centralized error/auth handling** — is there one place where 401s are caught, retried, or redirected?
- **Query key factories** — do query keys follow a structured pattern that enables targeted invalidation?
- **Optimistic updates** — are mutations written to update cache before the server confirms?
- **Co-located loading/error states** — are loading/error/data handled consistently per query?
- **Typed responses** — are API responses validated (Zod, io-ts) or blindly cast?

---

### Area: state-management

Goal: understand how state is scoped and why.

```bash
# Find stores
find . -not -path "*/node_modules/*" \( -name "*.store.ts" -o -name "*Store.ts" -o -name "*store.ts" \) | head -15

# Find context providers
grep -r "createContext\|createStore\|atom\|defineStore" --include="*.ts" --include="*.tsx" -l | grep -v node_modules | head -15

# Find state-heavy hooks
grep -r "useState\|useReducer" --include="*.tsx" -l | grep -v node_modules | xargs wc -l 2>/dev/null | sort -rn | head -10
```

Read 2-3 stores/contexts and the hooks that consume them. Look for:
- **Minimal global state** — is only truly shared/persistent state global?
- **Derived state** — are computed values derived (not duplicated) in selectors or memo?
- **Slice discipline** — are stores scoped to a domain, not one giant blob?
- **Selector pattern** — are components subscribing to fine-grained slices to avoid re-renders?
- **Action naming** — do mutations have clear intent names (`setUser` vs `updateUserProfile`)?

---

### Area: api-design (backend / server)

Goal: find how routes, middleware, and handlers are structured.

```bash
# Find route/handler files
find . -not -path "*/node_modules/*" \( -name "routes.ts" -o -name "router.ts" -o -name "*controller*" -o -name "*handler*" \) | head -20

# Find middleware
find . -not -path "*/node_modules/*" \( -path "*/middleware/*" -o -name "*middleware*" \) -name "*.ts" | head -15

# Find schema/validation
grep -r "z\.object\|joi\.\|yup\.\|validateBody\|parseBody" --include="*.ts" -l | grep -v node_modules | head -10
```

Read the router entry point and 3-4 handlers + middleware. Look for:
- **Thin handlers** — does the handler only parse input, call a service, and return a response?
- **Middleware composition** — are cross-cutting concerns (auth, validation, logging) applied as middleware rather than inside handlers?
- **Input validation** — is all user input validated at the boundary with a schema?
- **Error propagation** — is there a centralized error handler, or is each handler responsible?
- **Route grouping** — are related routes co-located under a prefix/router?

---

### Area: type-system

Goal: find TypeScript patterns that carry real safety without verbosity.

```bash
# Find type/interface files
find . -not -path "*/node_modules/*" \( -name "types.ts" -o -name "*.types.ts" -o -name "*.d.ts" \) | head -20

# Find discriminated unions / branded types
grep -r "type.*=.*{.*kind\|type.*=.*{.*__brand\|infer\|keyof\|ReturnType\|Parameters" --include="*.ts" --include="*.tsx" -l | grep -v node_modules | head -10

# Find generics in utility files
find . -name "*.ts" -not -path "*/node_modules/*" | xargs grep -l "function.*<T" | head -10
```

Read the main types file and 2-3 utility type definitions. Look for:
- **Discriminated unions** over boolean flags — `{ status: 'loading' } | { status: 'error'; message: string }` is far safer than `{ loading: boolean; error?: string }`
- **Branded/nominal types** — e.g. `type UserId = string & { __brand: 'UserId' }` to prevent mixing IDs
- **Generic utilities** — reusable types that reduce duplication (`Nullable<T>`, `AsyncState<T>`, etc.)
- **Exhaustiveness checks** — `never` patterns ensuring switch statements handle all cases
- **Type narrowing helpers** — type guards that make runtime checks reusable

---

### Area: abstractions

Goal: find custom hooks or utilities that encapsulate complexity elegantly.

```bash
# Find custom hooks
find . -name "use*.ts" -o -name "use*.tsx" | grep -v node_modules | grep -v ".test." | grep -v ".spec." | head -30

# Find utility files
find . -not -path "*/node_modules/*" \( -path "*/utils/*" -o -path "*/helpers/*" -o -path "*/lib/*" \) -name "*.ts" | grep -v ".test." | head -20

# Find the most-imported utils
grep -r "from.*utils\|from.*helpers\|from.*lib" --include="*.ts" --include="*.tsx" | grep -v node_modules | sed "s/.*from '//;s/'.*//" | sort | uniq -c | sort -rn | head -10
```

Read 3-5 hooks/utilities. Look for:
- **Hooks that colocate logic** — a `useForm` or `useAsync` that centralizes a pattern used everywhere
- **Composition** — hooks that call other hooks, building complexity in layers
- **Escape hatches** — utilities that wrap browser APIs or third-party libs to make them testable/mockable
- **Single-responsibility** — each hook/util does exactly one thing and names it clearly
- **Encapsulated side effects** — effects (subscriptions, timers, event listeners) fully managed inside a hook with proper cleanup

---

### Area: testing

Goal: find test patterns that are fast to write, maintainable, and catch real bugs.

```bash
# Find test files
find . -name "*.test.*" -o -name "*.spec.*" | grep -v node_modules | head -30

# Find factories / fixtures
find . -not -path "*/node_modules/*" \( -name "factories*" -o -name "fixtures*" -o -name "mocks*" -o -name "fakes*" \) | head -15

# Find test setup
find . -not -path "*/node_modules/*" \( -name "setup.ts" -o -name "setupTests.ts" -o -name "vitest.setup.ts" -o -name "jest.setup.ts" \) | head -5
```

Read 3-4 test files (mix of unit and integration if available) plus any factory/fixture files. Look for:
- **Data factories** over inline objects — `buildUser({ role: 'admin' })` beats `{ id: '1', name: 'Test', role: 'admin', ... }` repeated everywhere
- **Testing behavior, not implementation** — tests assert on output/UI state, not internal function calls
- **Minimal mocking** — only external boundaries (network, filesystem) are mocked; internal modules are imported as-is
- **Descriptive test names** — `it('shows error message when email is invalid')` over `it('validates form')`
- **Shared test helpers** — `renderWithProviders()`, `waitForQuery()` reducing boilerplate per-test

---

### Area: error-handling

Goal: find where errors are caught, typed, and surfaced to users.

```bash
# Find error boundaries
grep -r "ErrorBoundary\|componentDidCatch\|getDerivedStateFromError" --include="*.tsx" -l | grep -v node_modules | head -10

# Find Result / Either types
grep -r "Result<\|Either<\|{ error\|{ ok\|{ success" --include="*.ts" --include="*.tsx" -l | grep -v node_modules | head -10

# Find catch patterns
grep -rn "catch.*\(e\)\|catch.*\(err\)\|catch.*\(error\)" --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".test." | head -20
```

Read the error boundary (if any), error handler, and 2-3 files with notable error handling. Look for:
- **Typed errors** — custom error classes or discriminated union error types vs bare `catch (e: any)`
- **Error propagation strategy** — errors thrown up to a boundary vs handled locally vs returned as values
- **User-facing error messages** — is there a single place that maps error codes to user-friendly strings?
- **Recovery paths** — can users retry? Are error states actionable?

---

### Area: performance

Goal: find deliberate performance decisions in the code.

```bash
# Find memoization
grep -rn "useMemo\|useCallback\|React.memo\|memo(" --include="*.tsx" -l | grep -v node_modules | head -15

# Find lazy loading
grep -rn "React.lazy\|import(" --include="*.tsx" --include="*.ts" | grep -v node_modules | head -15

# Find virtualization
grep -r "virtual\|windowing\|VirtualList\|useVirtual" --include="*.tsx" -l | grep -v node_modules | head -5
```

Read 2-3 files with notable performance patterns. Look for:
- **Targeted memoization** — `useMemo`/`useCallback` used with a clear reason, not sprinkled everywhere
- **Route-level code splitting** — lazy loading used at route boundaries
- **List virtualization** — large lists use windowing rather than rendering all rows
- **Stable references** — event handlers and objects defined outside render or memoized to avoid child re-renders

---

## Step 4: Output Findings

For each analyzed area, present findings in this format:

```
## {Area Name}

### Pattern: {Descriptive Pattern Name}
**Why it's effective**: {1-2 sentences on what problem it solves or why it scales}

**Where to see it**: `{file/path/here.ts}:{line_start}-{line_end}`

```{language}
{short code snippet — 5-20 lines — showing the pattern in action}
```

**How to apply it**: {1-2 sentences on how to replicate this pattern when adding new code}

---
```

Rules for output:
- **Always include file paths with line numbers** (format: `path/to/file.ts:42-58`)
- **Show the actual code** — short snippets inline, not summaries
- **Explain WHY** not just WHAT — the insight is in the reasoning
- **Flag novel solutions** — if the codebase invented something non-obvious, call it out explicitly with `**Novel approach:**`
- **Skip the mundane** — don't document "they use TypeScript interfaces" unless the way they use them is unusually clean
- Aim for **3-6 patterns per area**, focusing on the best ones, not an exhaustive list

End with a brief summary:

```
---
## Summary

**Most distinctive patterns in this codebase:**
1. {pattern name} — {one line why it's notable}
2. {pattern name} — {one line why it's notable}
3. {pattern name} — {one line why it's notable}

**Best reference files** (read these to understand the codebase style):
- `{path/to/file.ts}` — {why it's a good reference}
- `{path/to/file.ts}` — {why it's a good reference}
```

---

## Step 5: Write Learnings File

After presenting findings to the user, write a structured learnings file so these patterns are available to future sessions and other skills.

```bash
REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null || pwd))
LEARNINGS_DIR=~/.claude/repo-learnings/$REPO
mkdir -p "$LEARNINGS_DIR"
echo "Writing patterns.md to $LEARNINGS_DIR"
```

Write `~/.claude/repo-learnings/$REPO/patterns.md` with this structure:

```markdown
# Patterns — {repo-name}
Last analyzed: {ISO date, e.g. 2026-04-24}
Scope: {areas analyzed, e.g. "ui-components, data-fetching, state-management"}

## Summary
{2-3 sentence overview of what makes this codebase's patterns distinctive}

## Most Distinctive Patterns
1. {pattern name} — {one line why it's notable}
2. {pattern name} — {one line why it's notable}
3. {pattern name} — {one line why it's notable}

## Best Reference Files
- `{path/to/file.ts}` — {why it's a good reference}
- `{path/to/file.ts}` — {why it's a good reference}

---

## {Area Name}

### Pattern: {Descriptive Pattern Name}
**Why it's effective**: {1-2 sentences}
**Where to see it**: `{file/path/here.ts}:{line_start}-{line_end}`
**How to apply it**: {1-2 sentences on replicating this pattern}

```{language}
{short code snippet — 5-20 lines}
```

{Repeat for each pattern in this area}

---

{Repeat ## section for each analyzed area}
```

Rules:
- Every pattern block must include the `**Where to see it**` file path so future reads can verify the pattern still exists
- Mark novel approaches with `**Novel approach:**` in the pattern body
- Do not pad with obvious conventions; only write patterns that a new contributor would not guess from the stack alone
- If `patterns.md` already exists, overwrite it entirely (this is a fresh analysis pass)

After writing `patterns.md`, check if `index.md` exists in the learnings dir:

```bash
[ -f "$LEARNINGS_DIR/index.md" ] && echo "index exists" || echo "no index"
```

**If `index.md` exists**: append or update a `patterns.md` pointer line under the "Learnings Files" section. Use `grep` to check if the line is already there before adding it:
```
- patterns.md — notable patterns worth emulating (from /analyze-patterns)
```

**If `index.md` does not exist**: create a minimal one:

```markdown
# {repo-name} Learnings
Last analyzed: {ISO date}

## Learnings Files
- patterns.md — notable patterns worth emulating (from /analyze-patterns)
```

Confirm to the user:

```
✅ Learnings written to ~/.claude/repo-learnings/{repo-name}/patterns.md
Areas captured: {comma-separated list}
Run /update-learnings to merge these into the full learnings set.
```
