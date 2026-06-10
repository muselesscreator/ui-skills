---
name: analyze-e2e-impact
internal: true
description: "Pipeline analysis skill. Given a code snapshot of changed files, scans E2E specs for flows that exercise those components or routes, and identifies what will break. Runs after snapshot-branch, before pipe-plan."
version: 1.0.0
---

# analyze-e2e-impact

**Pipeline skill — invoked by `pipeline-next`, not directly.**

## Inputs

- `~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-latest.md`

## Step 1: Resolve Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
SNAPSHOT=~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-latest.md
```

If `$SNAPSHOT` does not exist, write an ERROR output (see Step 5 error format) and stop.

## Step 2: Extract Searchable Names from the Snapshot

Read `$SNAPSHOT`. Parse the `## File List` section to get changed file paths.

For each changed file, extract:

**Component names** — PascalCase identifiers exported from `.tsx` / `.jsx` files:
```bash
grep -h "export.*const\|export default\|export function" "$FILE" 2>/dev/null \
  | grep -oE '[A-Z][A-Za-z0-9]+' | sort -u
```

**Route paths** — string literals that look like URL paths from router files (files whose path contains `router`, `routes`, or `Route`):
```bash
grep -hoE '"(/[^"]+)"' "$FILE" 2>/dev/null | tr -d '"' | sort -u
grep -hoE "'(/[^']+)'" "$FILE" 2>/dev/null | tr -d "'" | sort -u
```

**Feature area names** — the immediate parent directory name for each changed file (e.g., `features/invoices/InvoiceList.tsx` → `invoices`). Deduplicate.

Collect all extracted names into a single list. Remove generic tokens (e.g., `Index`, `Default`, `src`, `components`) that would produce noise in grep results.

## Step 3: Find Matching E2E Spec Files

Search common E2E directory locations. Try each; use whichever exist:

```bash
E2E_DIRS=""
for candidate in \
  "packages/e2e/tests" \
  "packages/e2e/specs" \
  "cypress/integration" \
  "cypress/e2e" \
  "e2e/tests" \
  "e2e/specs" \
  "tests/e2e" \
  "playwright/tests"
do
  [ -d "$candidate" ] && E2E_DIRS="$E2E_DIRS $candidate"
done
```

If no E2E directory exists at all, skip to Step 5 (no-E2E path).

For each name extracted in Step 2, grep across all found E2E directories:

```bash
for name in $EXTRACTED_NAMES; do
  grep -rl "$name" $E2E_DIRS 2>/dev/null
done | sort -u
```

Collect the unique set of matching spec files.

## Step 4: Analyze Each Matching Spec File

For each spec file found in Step 3:

### 4a. Find associated page object

Look for a page object file using these strategies (try each):
- Check for an import in the spec: `grep "from.*page" "$SPEC"` → resolve the import path
- Look for a same-name file in a `page-objects/` or `pages/` sibling directory
- Look for `{spec-basename}.page.ts` or `{spec-basename}PO.ts` next to the spec

Read the page object if found.

### 4b. Read and classify

Read the spec file (and page object if found). For each `describe` / `it` block that references the changed components, routes, or feature areas:

**Flows that break** — user journey steps that will fail because:
- A component being changed or removed is the target of a selector or assertion
- A route path is changing, affecting `cy.visit()` or `page.goto()` calls
- An API shape used in an intercept stub is being modified

**Intercepts affected** — `cy.intercept()`, `cy.route()`, or `page.route()` calls whose route pattern or stubbed response shape matches a changed API or tRPC route:
- Route added, removed, or renamed
- Request/response body shape changing

**Selector changes** — `data-testid`, `data-key`, ARIA role selectors, or text-content assertions that reference a changed component's rendered output:
```bash
grep -n 'data-testid\|data-key\|getByRole\|getByText\|getByLabel' "$SPEC"
```
Flag any whose value references a changed component name, prop, or label.

**Navigation changes** — `cy.visit(`, `page.goto(`, or `router.push(` calls with a hardcoded route that is being changed.

## Step 5: Write Output File

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
OUTDIR=~/.claude/skill-output/$REPO/$BRANCH
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/e2e-impact-$TS.md"
```

**If no E2E directory was found** (from Step 3), write:

```
---
skill: analyze-e2e-impact
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs:
  - code-snapshot-latest.md
---

No E2E test directory found in this repo.
```

Otherwise write `$OUTFILE` with the following structure:

```
---
skill: analyze-e2e-impact
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs:
  - code-snapshot-latest.md
---

## E2E Impact

### Specs Affected
- `{spec file}` — exercises {component/feature}

### Flows That Break
- `{spec file}` > `{describe block}` > `{it block}`: {what breaks and why}

### Intercepts to Update
- `{spec file}`: intercept for `{route}` — {what changes}

### Selectors at Risk
- `{spec file}`: `{selector}` — {why it may break}

### No E2E Coverage
{List changed components/features with no matching E2E spec, or "All changed areas have E2E coverage"}
```

If a section has no entries, write `None` under the heading (do not omit the heading).

**On error:** if any step fails, write the file anyway with an `### ERROR` section at the top describing what failed and what partial results are available.

## Step 6: Symlink and State Update

```bash
ln -sf "$OUTFILE" "$OUTDIR/e2e-impact-latest.md"
```

Update `pipeline-state.json` if it exists:

```bash
STATE="$OUTDIR/pipeline-state.json"
if [ -f "$STATE" ]; then
  python3 - <<'PYEOF'
import json, sys, os

state_path = os.environ.get('STATE') or (os.path.expanduser('~/.claude/skill-output') + '/' +
    os.popen('git remote get-url origin 2>/dev/null | sed "s/.*\\///" | sed "s/\\.git//"').read().strip() + '/' +
    os.popen('git branch --show-current 2>/dev/null | sed "s/\\//-/g"').read().strip() + '/pipeline-state.json')

try:
    with open(state_path) as f:
        state = json.load(f)
    state.setdefault('phases', {})['analyze-e2e-impact'] = {
        'status': 'complete',
        'output': 'e2e-impact-latest.md'
    }
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)
    print('pipeline-state.json updated')
except FileNotFoundError:
    print('No pipeline-state.json found — skipping state update')
except Exception as e:
    print(f'State update failed: {e}', file=sys.stderr)
PYEOF
fi
```

If `pipeline-state.json` does not exist, skip the state update silently and proceed.
