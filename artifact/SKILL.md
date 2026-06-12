---
name: artifact
description: Performs a request and persists its result to a distinct artifact file in the skill-output directory, so follow-on agents can read the result instead of redoing the work. Each invocation derives its own artifact name from the request, so multiple /artifact calls in one turn write separate files. Use when a result (a log, an analysis, a query output, a generated document) is worth saving for reuse rather than only printing inline.
version: 1.0.0
triggers:
  explicit:
    - artifact
    - save as artifact
    - write to artifact
    - persist the output
  strong_intent:
    - save the output so we don't redo it
    - write the result to a file for later
confidence_threshold: 70
---

# artifact

**Arguments**: $ARGUMENTS — the request to perform, phrased as an action. The request is **both** the work to do and the source of the artifact's name. Examples:
- `artifact log the output` → does the logging, writes `artifact-log-<ts>.md`
- `artifact analyze the output` → does the analysis, writes `artifact-analyze-<ts>.md`
- `artifact summarize the failing tests` → writes `artifact-summarize-failing-tests-<ts>.md`

Each invocation produces **one distinct file**. Two `/artifact` calls in the same turn (e.g. "log the output" and "analyze the output") must write two separate files — never append to or overwrite each other. The per-request slug (Step 2) guarantees this.

The point of this skill is **reuse**: do the work once, persist the result, so a follow-on agent reads the file instead of repeating the work. Write the artifact for a reader who does not have this conversation — make it self-contained.

## Step 1: Resolve Repo and Branch

```bash
REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')
[ -z "$REPO" ] && REPO=$(basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null)
[ -z "$REPO" ] && REPO="no-repo"
BRANCH=$(git branch --show-current 2>/dev/null | sed 's/\//-/g')
[ -z "$BRANCH" ] && BRANCH="no-branch"
```

## Step 2: Parse the Request into a Task and a Slug

From $ARGUMENTS, derive two things:

1. **The task** — what to actually do (log, analyze, summarize, query, generate, etc.) and against what subject.
2. **The slug** — a short kebab-case name for the artifact, taken from the request's verb and (if distinguishing) its subject. Keep it 1–4 words.
   - `log the output` → `log`
   - `analyze the output` → `analyze`
   - `summarize the failing tests` → `summarize-failing-tests`
   - Strip filler words (the, a, of, this, that, output) unless dropping them makes two requests collide. If `log the output` and `log the errors` appear together, keep the distinguishing noun: `log-output` and `log-errors`.

If $ARGUMENTS is empty, ask the user what to perform and persist — do not guess.

## Step 3: Perform the Request

Do the actual work the request describes. This is a real task, not a stub:
- "log the output" → produce/collect the log content (run the command, capture its output, etc.).
- "analyze the output" → perform the analysis and produce findings.
- Anything else → carry it out fully.

Gather everything the artifact should contain. If the work depends on a prior artifact (e.g. "analyze the output" referring to a log written by an earlier `/artifact log`), check for it first and read it rather than regenerating:

```bash
ls -t ~/.claude/skill-output/$REPO/$BRANCH/artifact-*-latest.md 2>/dev/null
```

If a relevant prior artifact exists, build on it and reference its filename in the new artifact's frontmatter (`based_on:`).

## Step 4: Write the Artifact File

```bash
TS=$(date +%Y%m%d-%H%M%S)-$$
mkdir -p ~/.claude/skill-output/$REPO/$BRANCH
```

Write to `~/.claude/skill-output/$REPO/$BRANCH/artifact-{slug}-$TS.md` with this frontmatter:

```
---
skill: artifact
repo: {repo}
branch: {branch}
timestamp: {ISO-8601 datetime}
request: {original $ARGUMENTS, one line}
slug: {slug}
based_on: {prior artifact filename, or omit if none}
---
```

Then the body:

```
# {Title derived from the request}

## Request
{The exact thing that was asked, restated in one or two sentences so the file stands alone.}

## Result
{The full output of the work — the log, the analysis, the summary, the generated content. This is the payload; make it complete enough that a follow-on agent never needs to redo the work.}

## Notes
{Optional: caveats, how the result was produced, what wasn't covered, commands run. Omit if there's nothing useful to add.}
```

The **Result** section is the reason the file exists — be thorough there. Do not truncate or abbreviate the payload to save space; the whole purpose is to spare a later agent from regenerating it.

## Step 5: Update the Per-Slug `latest` Pointer

A pointer per slug, so each kind of artifact has a predictable path follow-on agents can read:

```bash
ln -sf artifact-{slug}-$TS.md ~/.claude/skill-output/$REPO/$BRANCH/artifact-{slug}-latest.md
```

## Step 6: Report Back

Tell the user, concisely:
- The full path to the artifact written.
- A one-line description of what it contains.
- The predictable read path for a follow-on agent:

  ```
  Read ~/.claude/skill-output/{repo}/{branch}/artifact-{slug}-latest.md
  ```

When invoked multiple times in one turn, report each artifact's path separately — confirm distinct files were written.
