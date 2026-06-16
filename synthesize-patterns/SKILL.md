---
name: synthesize-patterns
description: Reads all analyze-patterns learnings files across repos and synthesizes cross-repo insights — universal best practices, conflicting approaches with trade-off analysis, complementary pattern pairs, novel patterns worth generalizing, and overarching meta-principles.
version: 1.0.0
triggers:
  explicit:
    - synthesize patterns
    - cross-repo patterns
    - patterns across repos
    - compile pattern learnings
    - synthesize learnings
  strong_intent:
    - what patterns show up everywhere
    - which patterns conflict with each other
    - what have I learned across all my codebases
    - what are the universal best practices I've found
    - what patterns work well together
confidence_threshold: 75
---

# synthesize-patterns

**Arguments**: $ARGUMENTS (optional: repo filter — e.g. "only paragon and editor.js", or area filter — e.g. "focus on testing")

Read all `patterns.md` learnings files from `~/.claude/repo-learnings/` and synthesize cross-repo insights: universal patterns, conflicting approaches, complementary pairs, and overarching principles.

This is the PERSONAL layer's synthesis engine: it distills general, repo-agnostic engineering knowledge from OSS/reference checkouts into `~/.claude/cross-repo-learnings/synthesis.md`. **Synthesize OSS/reference repos only.** A work repo's `patterns.md` (one whose source repo has a `./wiki/`, e.g. `incentives`) is code-specific knowledge headed for that repo's wiki — exclude it from the synthesis so the personal layer holds zero code-specific facts.

---

## Step 1: Discover Available Repos

```bash
# Find all repos with patterns.md files
find ~/.claude/repo-learnings -name "patterns.md" | sort

# List repos and their analyzed areas
for f in ~/.claude/repo-learnings/*/patterns.md; do
  repo=$(basename $(dirname $f))
  scope=$(grep "^Scope:" "$f" 2>/dev/null | head -1 || grep "^Last analyzed:" "$f" | head -1)
  echo "  $repo — $scope"
done
```

Exclude any **work-repo** dir from the synthesis set — these are code-specific learnings pending migration to that repo's wiki (Phase D of the skill-system optimization), not personal-layer material. Today that means skipping `incentives`. Flag it in the Step 2 scope summary as excluded-by-design rather than silently dropping it.

If no `patterns.md` files exist at all, stop and tell the user:
```
No patterns.md files found in ~/.claude/repo-learnings/.
Run /analyze-patterns in each repo first to generate learnings.
```

---

## Step 2: Confirm Scope with User

Present what's available:

```
## Available Pattern Learnings

{for each repo with patterns.md}
- **{repo-name}**: {scope line from the file, e.g. "ui-components, data-fetching, testing"}

**Synthesis will cover**: {N} repos, {list of areas that appear in 2+ repos}

---
Include all repos, or focus on specific ones?
(e.g. "all", "just paragon and editor.js", "skip the small ones")

Focus on specific pattern areas?
(e.g. "all areas", "just testing and abstractions", "everything except file-organization")
```

Use `AskUserQuestion` to receive the user's preference before proceeding.

If $ARGUMENTS already specifies a filter (repo names or areas), parse it and skip the question. Accept "all" as a valid answer to proceed without filtering.

After receiving input: filter the repo list and area list accordingly.

---

## Step 3: Read All Patterns Files

Read every `patterns.md` in the filtered set in parallel. For each file, extract:
- Repo name and stack (from the file header)
- Scope (areas analyzed)
- Most Distinctive Patterns list
- Each named pattern under each area section: name, "Why it's effective", "How to apply it", and the code snippet

Track this as an internal map: `{repo} → {area} → [{pattern-name, summary, code?}]`

---

## Step 4: Cross-Repo Analysis

This is the synthesis pass. Work through the following lenses in order:

### Lens 1: Universal Patterns

A pattern is **universal** if the same core idea appears independently in 2+ repos — possibly with different implementations, naming, or stack.

For each universal pattern found:
- Name the underlying idea (not the repo-specific name)
- Note which repos use it and how
- State why its recurrence across independent codebases validates it as a real best practice
- Note any meaningful implementation differences

Examples to look for:
- Compound component / static subcomponent namespacing
- Context-over-prop-drilling for shared display state
- Thin handlers (parse + delegate + return, no logic)
- Centralized error handling boundaries
- Named tuple return types for hooks
- Co-located tests

### Lens 2: Convergent Solutions (Same Problem, Different Approaches)

Find cases where multiple repos solve **the same problem** with **different implementations**. These are productive to compare because the trade-offs become visible.

Format: State the problem, describe each approach, analyze the trade-off, give a recommendation.

Examples to look for:
- Prop migration strategies (HOC wrapper vs in-component branching vs deprecation warnings)
- Browser API unavailability / SSR safety (try/catch fallback vs feature detection vs conditional import)
- Module wiring / avoiding circular dependencies (registry pattern vs barrel files vs deferred injection)
- Test isolation (module-level mocks vs per-test mocks vs context injection)

### Lens 3: Complementary Pattern Pairs

Find patterns from the same repo or across repos that **actively reinforce each other** — using both together produces better outcomes than either alone.

Format: Name the pair, explain the synergy, show where each pattern is seen.

Examples to look for:
- Compound components + context propagation (the sub-component knows its parent's state without props)
- Named tuple return types + FakeComponent hook tests (clear hook API + behavior-level verification)
- Query key factories + optimistic mutation updates (predictable invalidation targets)
- Discriminated union types + exhaustiveness checks (type safety from definition to switch statement)

### Lens 4: Conflicting Patterns (Trade-off Required)

Find cases where patterns from different repos **contradict each other** — choosing one makes the other harder or impossible. These aren't bad patterns; they're genuine trade-offs that require a conscious choice.

Format: Name the tension, describe each side, explain when each is appropriate.

Examples to look for:
- Simple vs advanced dual API (easier for consumers vs harder to maintain two contracts)
- Typed context defaults vs loosely typed context (safety vs flexibility for dynamic shapes)
- Module-level mocks vs per-test mocks (less boilerplate vs clearer test isolation)
- Global state minimalism vs rich derived state (simplicity vs performance)

### Lens 5: Novel Patterns Worth Generalizing

Find patterns from a single repo that are **unusually elegant** and would improve any codebase that adopted them — patterns the repo invented or applied in a non-obvious way.

Format: Name the pattern, which repo it came from, why it's generalizable, how to apply it in a new context.

Examples to look for:
- `requiredWhen` / `requiredWhenNot` conditional PropType validators
- `CriticalError` sentinel class for failure severity routing
- `useIndexOfLastVisibleChild` ResizeObserver width-seeding trick
- Generic typed event bus with mapped types

---

## Step 5: Overarching Principles

From the analysis above, distill **meta-principles** — rules that operate above any single pattern area and recur across multiple lenses.

Each principle should:
- State the rule in one sentence
- Cite at least 2 concrete examples from the patterns analyzed
- Explain what breaks if the principle is violated

Aim for 4–8 principles. Examples of what strong principles look like:
- "Expose simple defaults, but let complexity compose" — recurs in two-level APIs, hook return tuples, test helpers
- "Push cross-cutting concerns to the boundary, not the component" — recurs in error handling, validation middleware, module-level mocks
- "Encode intent in types, not runtime checks" — recurs in discriminated unions, branded types, named tuples
- "Scoped internal APIs prevent external coupling" — recurs in compound components, barrel files, public/private type split

---

## Step 6: Present Synthesis

Output findings with this structure:

```
# Cross-Repo Pattern Synthesis
Repos analyzed: {repo list}
Areas covered: {area list}
Generated: {ISO date}

---

## Overarching Principles
{4-8 principles, each with examples and consequence-of-violation}

---

## Universal Patterns
{patterns appearing in 2+ repos, with cross-repo comparison}

---

## Convergent Solutions
{same-problem / different-implementation comparisons with recommendations}

---

## Complementary Pairs
{pattern pairs that reinforce each other, with synergy explanation}

---

## Conflicting Trade-offs
{genuine tensions between valid patterns, with when-to-use-each guidance}

---

## Novel Patterns Worth Generalizing
{single-repo gems with generalization guidance}
```

Rules for output:
- **Be specific**: cite repo name and pattern name for every claim ("paragon's `withDeprecatedProps` HOC" not "a component library we looked at")
- **Show the reasoning**: for trade-offs especially, explain *why* each side is valid — don't just pick a winner
- **Focus on the non-obvious**: skip observations any experienced dev would make on first read; surface what you'd only see by comparing multiple codebases

---

## Step 7: Write Synthesis File

After presenting findings, write the synthesis to a persistent file.

```bash
SYNTHESIS_DIR=~/.claude/cross-repo-learnings
mkdir -p "$SYNTHESIS_DIR"
```

Write `~/.claude/cross-repo-learnings/synthesis.md` with the full output from Step 6, plus this frontmatter:

```markdown
---
repos: [{comma-separated repo names}]
areas: [{comma-separated areas}]
generated: {ISO date}
source: synthesize-patterns
---

{full synthesis output}
```

If `synthesis.md` already exists, overwrite it entirely (this is a fresh synthesis pass).

After writing, check for an existing `index.md`:
```bash
[ -f "$SYNTHESIS_DIR/index.md" ] && cat "$SYNTHESIS_DIR/index.md" || echo "no index"
```

**If `index.md` does not exist**, create it:
```markdown
# Cross-Repo Learnings

## Synthesis Files
- synthesis.md — cross-repo pattern synthesis (from /synthesize-patterns)
```

**If `index.md` exists**, add or update a pointer to `synthesis.md` under the "Synthesis Files" section.

Confirm to the user:
```
✅ Synthesis written to ~/.claude/cross-repo-learnings/synthesis.md
Repos analyzed: {N} repos ({repo list})
Principles identified: {N}
Universal patterns found: {N}
Novel patterns worth generalizing: {N}

Run /synthesize-patterns again after running /analyze-patterns on new repos to keep it current.
```
