---
name: analyze-test-impact
internal: true
description: "Pipeline analysis skill. Given a code snapshot of changed files, reads their co-located unit tests and identifies which tests will break, which need extension, and which files have no coverage. Runs after snapshot-branch, before pipe-plan."
version: 1.0.0
---

# analyze-test-impact

**Pipeline skill — invoked by `pipeline-next`, not directly.**

## Inputs

- `~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-latest.md`

## Step 1: Resolve Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
SNAPSHOT=~/.claude/skill-output/$REPO/$BRANCH/code-snapshot-latest.md
```

If `$SNAPSHOT` does not exist, write an ERROR output (see Step 3 error format) and stop.

## Step 2: Parse the File List

Read `$SNAPSHOT`. Find the `## File List` section and extract the list of changed source files from it. The section contains one file path per line (possibly with brief annotations after `—` — strip those to get the bare path).

**Skip test files themselves** — do not process files whose path contains `.test.`, `.spec.`, or `/__tests__/`.

## Step 3: Analyze Each Source File

For each source file extracted in Step 2:

### 3a. Find co-located test files

```bash
FILE="{path from file list}"
basename=$(basename "$FILE" | sed 's/\.[^.]*$//')
dir=$(dirname "$FILE")

# Primary locations
find "$dir" -maxdepth 1 \( -name "${basename}.test.ts" -o -name "${basename}.test.tsx" \
  -o -name "${basename}.test.js" -o -name "${basename}.test.jsx" \
  -o -name "${basename}.spec.ts" -o -name "${basename}.spec.tsx" \
  -o -name "${basename}.spec.js" -o -name "${basename}.spec.jsx" \) 2>/dev/null

# __tests__ subdirectory
find "$dir/__tests__" -maxdepth 1 -name "${basename}.*" 2>/dev/null
```

### 3b. If one or more test files are found

Read each test file. For each, examine:

**Will BREAK** — look for:
- Assertions against props, function signatures, or named exports being changed or removed
- Tests that import something being renamed or deleted
- Assertions against specific return values or shapes that the change modifies
- `expect(fn).toHaveBeenCalledWith(...)` calls whose arguments reference a changed interface

**Needs EXTENSION** — look for:
- Tests covering a feature that now has new behavior not yet exercised
- Tests whose happy-path setup would still pass, but new code paths are untested
- `describe` blocks covering the feature area where additional `it` cases are warranted

**Mocks to Update** — look for:
- `jest.mock(...)`, `vi.mock(...)`, or inline mock objects whose shape mirrors an interface being changed
- Factory functions or fixtures that construct objects whose shape is being altered

**Unaffected** — tests in this file that clearly do not touch anything being changed (informational only).

### 3c. If no test files are found

Flag the source file as "No coverage."

## Step 4: Write Output File

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
TS=$(date +%Y%m%d-%H%M%S)-$$
OUTDIR=~/.claude/skill-output/$REPO/$BRANCH
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/test-impact-$TS.md"
```

Write `$OUTFILE` with the following structure:

```
---
skill: analyze-test-impact
repo: {REPO}
branch: {BRANCH}
timestamp: {ISO timestamp}
inputs:
  - code-snapshot-latest.md
---

## Unit Test Impact

### Will Break (must fix)
- `{test name}` in `{test file}` — {reason: what changed that breaks this assertion}

### Needs Extension (add cases)
- `{test name}` in `{test file}` — {what new behavior needs coverage}

### Mocks to Update
- `{mock target}` in `{test file}` — {what interface change affects the mock}

### No Coverage (will need new tests)
- `{source file}` — no test file found

### Unaffected (informational)
- `{test file}` — tests for {source file}, no expected impact
```

If a section has no entries, write `None` under the heading (do not omit the heading).

**On error:** if any step fails, write the file anyway with an `### ERROR` section at the top describing what failed and what partial results are available.

## Step 5: Symlink and State Update

```bash
ln -sf "$OUTFILE" "$OUTDIR/test-impact-latest.md"
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
    state.setdefault('phases', {})['analyze-test-impact'] = {
        'status': 'complete',
        'output': 'test-impact-latest.md'
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
