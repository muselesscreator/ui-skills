#!/usr/bin/env python3
"""cycle-forensics.py — deterministic extraction of everything knowable about a
completed work cycle: its step ledger, its real cost, its artifacts, and the
Claude sessions on its branch that were NOT part of it.

No judgment lives here. This script only reads what is on disk and prints it.
Interpretation (root cause, which skill to change) is the model's job — see
~/.claude/skills/analyze-cycle/SKILL.md.

Subcommands
  list [--repo R] [--branch B] [--limit N]
      Enumerate cycle runs, newest first: id, repo/branch, cycle-type, status, cost.

  report <cycleId | 'latest' | path/to/cycle-dir | path/to/orch-run-*.md> [--json]
      Full forensics for one cycle: step ledger (every attempt), cost rollups,
      artifact inventory, session map, live rework, working tree, branch commits,
      anomaly flags.

      The session scan window opens at the END OF THE PREVIOUS CYCLE on the same
      branch (fallback --lookback-hours) and stays open to NOW, so a retro running
      inside a live cycle still sees a complete leak record: `inter-cycle` sessions
      and commits are the previous cycle's leakage, `during` ones (possibly still
      active) are this cycle's. Sessions belonging to OTHER cycles on the branch are
      separated out as machinery so they never inflate the leak count.

  history [--repo R] [--limit N]
      Per-skill aggregates across cycles (pass rate, mean attempts, mean cost).
      This is the systemic-vs-one-off evidence: does this skill fail everywhere,
      or only in the cycle under review?

  sessions <cycleId>
      Just the session map — cycle-owned, other cycles', and unlinked human
      sessions — with transcript paths and live-rework overlap.

Two execution surfaces are supported:
  A. dev-screen cycle dirs — $OUT/cycles/<cycleId>/ with manifest.json plus
     per-attempt request/result/usage/log files. Full cost data (real USD).
  B. in-session /orch-ui runs — $OUT/orch-run-<TS>.md runlog only. Step statuses
     are parsed from the markdown; cost is unavailable (reported as such).

Cost policy: USD is only ever REPORTED, never computed. It comes from
usage.json / result.json written by the runner. Transcript-derived numbers are
tokens only — no price table is embedded here, because prices drift and a stale
constant is worse than an honest token count.
"""

import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys
import time

SKILL_OUTPUT = os.path.expanduser("~/.claude/skill-output")
PROJECTS = os.path.expanduser("~/.claude/projects")

# A run this short did not do its work — it crashed, was killed, or hit a
# startup error. Flagged rather than silently averaged into the ledger.
CRASH_SECONDS = 45
# Cache-read tokens above this in a single attempt means the step re-read a
# large context repeatedly; worth a look even when the step passed.
CACHE_READ_HOT = 5_000_000
PROMPT_TRUNC = 240
# A session with fewer than this many assistant turns and no file edits did no
# real work (a stray /clear, an abandoned shell). Listed, but never flagged.
TRIVIAL_TURNS = 3
# Slash commands that are session plumbing, not the human's actual request —
# skipped when picking the prompt that describes what a session was for.
PLUMBING_COMMANDS = {"/clear", "/compact", "/model", "/resume", "/exit", "/cost",
                     "/config", "/status", "/context", "/fast", "/login"}
SKILLS_ROOT = os.path.expanduser("~/.claude/skills")
# A session written this recently is still live — flagged so a retro can say
# "this is happening right now" rather than describing it in the past tense.
ACTIVE_WINDOW_MS = 20 * 60 * 1000
# How far back to scan for branch sessions when there is no previous cycle on the
# branch to anchor to. Only a fallback; the previous cycle's end is preferred.
DEFAULT_LOOKBACK_HOURS = 72


# ---------------------------------------------------------------- transcripts


def encode_project_dir(cwd):
    """~/.claude/projects dir name for a working directory."""
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def resolve_project_dir(cwd):
    """Locate the transcript dir for cwd; fall back to scanning if the encoded
    name doesn't exist (encoding has changed across Claude Code versions)."""
    guess = os.path.join(PROJECTS, encode_project_dir(cwd or ""))
    if os.path.isdir(guess):
        return guess
    for d in sorted(glob.glob(os.path.join(PROJECTS, "*"))):
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.jsonl"))[:3]:
            for line in _lines(f, limit=60):
                if line.get("cwd") == cwd:
                    return d
    return guess if os.path.isdir(guess) else None


def _lines(path, limit=None):
    """Yield parsed jsonl entries, tolerating truncated/garbage lines."""
    try:
        with open(path, errors="ignore") as fh:
            for i, line in enumerate(fh):
                if limit is not None and i >= limit:
                    return
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (ValueError, TypeError):
                    continue
    except OSError:
        return


def _text(content):
    """Flatten a message content field to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text") or "")
            elif isinstance(c, str):
                parts.append(c)
        return "\n".join(parts)
    return ""


def clean_prompt(text):
    """Strip the wrappers Claude Code adds around slash commands and local
    command output so the first prompt reads like what the human typed."""
    text = re.sub(r"<local-command-caveat>.*?</local-command-caveat>", "", text, flags=re.S)
    text = re.sub(r"<local-command-(stdout|stderr)>.*?</local-command-\1>", "", text, flags=re.S)
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = re.sub(r"<command-message>.*?</command-message>", "", text, flags=re.S)
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    cmd = re.search(r"<command-name>(.*?)</command-name>", text, flags=re.S)
    args = re.search(r"<command-args>(.*?)</command-args>", text, flags=re.S)
    if cmd:
        head = cmd.group(1).strip()
        if args:
            head += " " + args.group(1).strip()
        text = head + "\n" + re.sub(r"<command-(name|args|contents)>.*?</command-\1>", "", text, flags=re.S)
    return " ".join(text.split())


def scan_session(path):
    """Summarize one session transcript. Everything here is cheap counting —
    the expensive reading of *what actually happened* is left to a subagent."""
    sid = os.path.basename(path)[: -len(".jsonl")]
    s = {
        "session_id": sid,
        "transcript": path,
        "branches": collections.Counter(),
        "cwd": None,
        "title": None,
        "first_prompt": None,
        "fallback_prompt": None,
        "user_turns": 0,
        "assistant_turns": 0,
        "skills": collections.Counter(),
        "commands": collections.Counter(),
        "tools": collections.Counter(),
        "files_touched": collections.Counter(),
        "started": None,
        "ended": None,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "models": collections.Counter(),
        "subagents": 0,
    }
    for d in _lines(path):
        if d.get("gitBranch"):
            s["branches"][d["gitBranch"]] += 1
        if d.get("cwd") and not s["cwd"]:
            s["cwd"] = d["cwd"]
        if d.get("type") == "ai-title" and d.get("aiTitle"):
            s["title"] = d["aiTitle"]
        ts = d.get("timestamp")
        if ts:
            s["started"] = s["started"] or ts
            s["ended"] = ts
        typ = d.get("type")
        if typ == "user" and not d.get("isSidechain"):
            raw = _text((d.get("message") or {}).get("content"))
            s["user_turns"] += 1
            m = re.search(r"<command-name>(.*?)</command-name>", raw, flags=re.S)
            if m:
                s["commands"][m.group(1).strip()] += 1
            if s["first_prompt"] is None:
                cleaned = clean_prompt(raw)
                # Prefer the first prompt that says something. A bare /clear or
                # /model is what a session *starts* with, not what it was for.
                if cleaned and cleaned.split()[0] not in PLUMBING_COMMANDS:
                    s["first_prompt"] = cleaned[:PROMPT_TRUNC]
                elif cleaned and s["fallback_prompt"] is None:
                    s["fallback_prompt"] = cleaned[:PROMPT_TRUNC]
        elif typ == "assistant":
            msg = d.get("message") or {}
            s["assistant_turns"] += 1
            if d.get("attributionSkill"):
                s["skills"][d["attributionSkill"]] += 1
            if msg.get("model"):
                s["models"][msg["model"]] += 1
            u = msg.get("usage") or {}
            s["output_tokens"] += u.get("output_tokens") or 0
            s["cache_read_tokens"] += u.get("cache_read_input_tokens") or 0
            for c in msg.get("content") or []:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                name = c.get("name") or "?"
                s["tools"][name] += 1
                inp = c.get("input") or {}
                if name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
                    fp = inp.get("file_path") or inp.get("notebook_path")
                    if fp:
                        s["files_touched"][fp] += 1
    subdir = path[: -len(".jsonl")]
    s["subagents"] = len(glob.glob(os.path.join(subdir, "subagents", "*.jsonl")))
    s["subagent_dir"] = os.path.join(subdir, "subagents") if s["subagents"] else None
    return s


def branch_sessions(project_dir, branch, floor_ms):
    """Every session transcript in project_dir that touched `branch` and was
    written since `floor_ms`. The mtime filter keeps us from parsing a year of
    history; `floor_ms` is chosen by the caller to reach back to the previous
    cycle, not merely to this cycle's start."""
    if not project_dir or not os.path.isdir(project_dir):
        return []
    floor = (floor_ms / 1000.0) if floor_ms else 0
    out = []
    for f in glob.glob(os.path.join(project_dir, "*.jsonl")):
        try:
            if os.path.getmtime(f) < floor:
                continue
        except OSError:
            continue
        s = scan_session(f)
        if branch in s["branches"]:
            out.append(s)
    out.sort(key=lambda x: x["started"] or "")
    return out


# ------------------------------------------------------------------- surface A


def find_cycle_dirs(repo=None, branch=None):
    pattern = os.path.join(SKILL_OUTPUT, repo or "*", branch or "*", "cycles", "*", "manifest.json")
    found = []
    for m in glob.glob(pattern):
        try:
            man = json.load(open(m))
        except (OSError, ValueError):
            continue
        found.append((os.path.dirname(m), man))
    found.sort(key=lambda x: x[1].get("createdAt") or 0, reverse=True)
    return found


def all_cycle_sessions(repo, branch):
    """sessionId → cycle id, for EVERY cycle ever run on this repo+branch.

    A branch usually carries several cycles. Their step sessions are not part of
    *this* cycle, but they are not human fix-work either — counting them as leakage
    would inflate every report with other runs' machinery."""
    owned = {}
    for cdir, man in find_cycle_dirs():
        if repo and man.get("repo") != repo:
            continue
        if branch and man.get("branch") != branch:
            continue
        cid = man.get("id") or os.path.basename(cdir)
        for rq in glob.glob(os.path.join(cdir, "*.request.json")):
            sid = (_load(rq) or {}).get("sessionId")
            if sid:
                owned[sid] = cid
    return owned


# Fixed openings of the prompts cycle runners hand a step subagent. Fallback for
# when a cycle's dir is missing its request.json files but the transcripts remain
# (e.g. a single-skill cycle that recorded no attempts).
STEP_PROMPT_RES = (
    re.compile(r"You are running one isolated step of the\s+(\S+)\s+cycle", re.I),
    re.compile(r"This is the \S+ step of cycle\s+([0-9a-f-]{8,36})", re.I),
    re.compile(r"^Invoke the (\S+) skill with arguments", re.I),
)


def runner_prompt_cycle(prompt):
    """The cycle/skill a runner-issued step prompt names, or None if this reads
    like a human typing."""
    for rx in STEP_PROMPT_RES:
        m = rx.search(prompt or "")
        if m:
            return m.group(1)
    return None


def previous_cycle_end(repo, branch, before_ms):
    """When the last cycle on this same branch finished. This is the floor for
    session scanning: everything between it and now is fix-work that the PREVIOUS
    cycle failed to deliver, and it is all on disk already — no waiting required."""
    if not (repo and branch and before_ms):
        return None
    best = None
    for _cdir, man in find_cycle_dirs():
        if man.get("repo") != repo or man.get("branch") != branch:
            continue
        created = man.get("createdAt") or 0
        if created >= before_ms:
            continue
        end = man.get("finishedAt") or man.get("updatedAt") or created
        if best is None or end > best[0]:
            best = (end, man.get("id"), man.get("cycle"))
    return {"end_ms": best[0], "cycle_id": best[1], "cycle": best[2]} if best else None


def load_runs(cycle_dir):
    """One record per attempt, assembled from request/result/usage/log files.
    Files are the source of truth; the manifest's `runs` list is only a hint."""
    runs = []
    for rq in glob.glob(os.path.join(cycle_dir, "*.request.json")):
        base = rq[: -len(".request.json")]
        name = os.path.basename(base)
        req = _load(rq) or {}
        res = _load(base + ".result.json") or {}
        use = _load(base + ".usage.json") or res.get("usage") or {}
        stdout = res.get("stdout") or ""
        fields = parse_status_block(stdout)
        started = res.get("startedAt") or req.get("startedAt")
        finished = res.get("finishedAt")
        m = re.match(r"^(.*?)-(attempt|remediation)-(\d+)-(\d+)$", name)
        runs.append(
            {
                "run": name,
                "step_id": m.group(1) if m else name,
                "kind": m.group(2) if m else "step",
                "attempt": int(m.group(3)) if m else 1,
                "model": req.get("model"),
                "session_id": req.get("sessionId"),
                "cwd": req.get("cwd"),
                "prompt": (req.get("prompt") or "")[:PROMPT_TRUNC],
                "status": fields.get("STATUS"),
                "artifact": fields.get("ARTIFACT"),
                "summary": fields.get("SUMMARY"),
                "followup": fields.get("FOLLOWUP"),
                "decisions": fields.get("DECISIONS"),
                "exit_code": res.get("exitCode"),
                "termination": res.get("termination"),
                "stderr_tail": (res.get("stderr") or "")[-400:],
                "started_ms": started,
                "finished_ms": finished,
                "duration_s": round((finished - started) / 1000.0, 1) if started and finished else None,
                "cost_usd": use.get("totalCostUsd"),
                "output_tokens": use.get("outputTokens"),
                "cache_read_tokens": use.get("cacheReadInputTokens"),
                "cache_creation_tokens": use.get("cacheCreationInputTokens"),
                "models_used": list((use.get("models") or {}).keys()),
                "log": base + ".log" if os.path.exists(base + ".log") else None,
                "result_file": base + ".result.json" if os.path.exists(base + ".result.json") else None,
                "stdout_len": len(stdout),
            }
        )
    runs.sort(key=lambda r: r["started_ms"] or 0)
    return runs


def _load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return None


def parse_status_block(text):
    """Pull the five-line step contract (STATUS/ARTIFACT/SUMMARY/FOLLOWUP/
    DECISIONS) out of a step's stdout or a runlog section."""
    fields = {}
    for line in (text or "").splitlines():
        m = re.match(r"^\s*(STATUS|ARTIFACT|SUMMARY|FOLLOWUP|DECISIONS)\s*:\s*(.*)$", line)
        if m and m.group(1) not in fields:
            fields[m.group(1)] = m.group(2).strip()
    return fields


# ------------------------------------------------------------------- surface B


def parse_runlog(path):
    """Parse an in-session /orch-ui runlog into the same shape as a manifest.
    No cost data exists on this surface — that gap is reported, not guessed."""
    text = open(path, errors="ignore").read()
    head = re.match(r"#\s*orch-ui run\s*—\s*(\S+)\s*—\s*(\S+)", text)
    task = re.search(r"\*\*Task:\*\*\s*(.*?)(?:\n\n|\n##)", text, flags=re.S)
    steps = []
    for m in re.finditer(r"^###\s+(\S+)\s*—\s*(.+?)$(.*?)(?=^###|\Z)", text, flags=re.S | re.M):
        body = m.group(3)
        fields = parse_status_block(body)
        steps.append(
            {
                "id": m.group(1),
                "skill": None,
                "model": None,
                "status": (fields.get("STATUS") or m.group(2)).strip().lower(),
                "attempts": 1,
                "artifact": fields.get("ARTIFACT"),
                "summary": fields.get("SUMMARY"),
                "followup": fields.get("FOLLOWUP"),
                "decisions": fields.get("DECISIONS"),
            }
        )
    spawns = collections.Counter(re.findall(r"^SPAWN:\s*(\S+)", text, flags=re.M))
    st = os.stat(path)
    return {
        "surface": "runlog",
        "runlog": path,
        "cycle": head.group(1) if head else None,
        "task": " ".join((task.group(1) if task else "").split())[:400],
        "status": None,
        "createdAt": int(st.st_mtime * 1000),
        "finishedAt": int(st.st_mtime * 1000),
        "steps": steps,
        "spawns": dict(spawns),
        "cost_available": False,
    }


# --------------------------------------------------------------------- report


def build_report(target, lookback_hours=DEFAULT_LOOKBACK_HOURS):
    if target.endswith(".md") and os.path.isfile(target):
        return report_runlog(target, lookback_hours)
    return report_cycle_dir(resolve_cycle(target), lookback_hours)


def resolve_cycle(target):
    if os.path.isdir(target) and os.path.exists(os.path.join(target, "manifest.json")):
        return target
    cycles = find_cycle_dirs()
    if not cycles:
        sys.exit("no cycle dirs found under " + SKILL_OUTPUT)
    if target in ("latest", "-", ""):
        return cycles[0][0]
    for d, _man in cycles:
        if os.path.basename(d).startswith(target):
            return d
    sys.exit("no cycle matching %r (try: cycle-forensics.py list)" % target)


def report_cycle_dir(cycle_dir, lookback_hours):
    man = _load(os.path.join(cycle_dir, "manifest.json")) or {}
    runs = load_runs(cycle_dir)
    rep = {
        "surface": "cycle-dir",
        "cycle_dir": cycle_dir,
        "cycle_id": man.get("id") or os.path.basename(cycle_dir),
        "cycle": man.get("cycle"),
        "repo": man.get("repo"),
        "branch": man.get("branch"),
        "branch_key": man.get("branchKey"),
        "worktree": man.get("worktree"),
        "output_dir": man.get("outputDir"),
        "status": man.get("status"),
        "task": " ".join((man.get("task") or "").split())[:600],
        "created_ms": man.get("createdAt"),
        "finished_ms": man.get("finishedAt") or man.get("updatedAt"),
        "max_budget_usd": man.get("maxBudgetUsd"),
        "cost_available": any(r.get("cost_usd") is not None for r in runs),
        "steps": [],
        "runs": runs,
    }
    by_step = collections.defaultdict(list)
    for r in runs:
        by_step[r["step_id"]].append(r)
    for s in man.get("steps") or []:
        sid = s.get("id")
        sruns = by_step.get(sid, [])
        rep["steps"].append(
            {
                "id": sid,
                "skill": s.get("skill"),
                "model": s.get("model"),
                "agent_type": s.get("agentType"),
                "scope": s.get("scope"),
                "interactive": s.get("interactive"),
                "stub": s.get("stub"),
                "stop_on_fail": s.get("stopOnFail"),
                "remediate": s.get("remediate"),
                "status": s.get("status"),
                "attempts": s.get("attempts"),
                "remediation_rounds": s.get("remediationRounds"),
                "note": s.get("note"),
                "runs": [r["run"] for r in sruns],
                "cost_usd": _sum(r.get("cost_usd") for r in sruns),
                "duration_s": _sum(r.get("duration_s") for r in sruns),
            }
        )
    # Steps present as attempt files but absent from the manifest step list.
    known = {s["id"] for s in rep["steps"]}
    for sid, sruns in by_step.items():
        if sid not in known:
            rep["steps"].append(
                {
                    "id": sid,
                    "skill": None,
                    "model": sruns[0].get("model"),
                    "status": (sruns[-1].get("status") or "").lower() or None,
                    "attempts": len(sruns),
                    "note": "(not in manifest step list — remediation or ad-hoc run)",
                    "runs": [r["run"] for r in sruns],
                    "cost_usd": _sum(r.get("cost_usd") for r in sruns),
                    "duration_s": _sum(r.get("duration_s") for r in sruns),
                }
            )
    rep["total_cost_usd"] = _sum(r.get("cost_usd") for r in runs)
    rep["artifacts"] = inventory(cycle_dir, man.get("outputDir"))
    attach_sessions(rep, {r.get("session_id") for r in runs if r.get("session_id")}, lookback_hours)
    rep["commits"] = branch_commits(man.get("worktree"), man.get("branch"), rep.get("created_ms"),
                                    rep.get("finished_ms") if not rep.get("window_open") else None,
                                    (rep.get("previous_cycle") or {}).get("end_ms"))
    rep["working_tree"] = working_tree(man.get("worktree"))
    rep["anomalies"] = flag_anomalies(rep)
    return rep


def report_runlog(path, lookback_hours):
    rep = parse_runlog(path)
    out_dir = os.path.dirname(path)
    parts = out_dir.split(os.sep)
    rep.update(
        {
            "cycle_id": os.path.basename(path),
            "cycle_dir": None,
            "repo": parts[-2] if len(parts) >= 2 else None,
            "branch_key": parts[-1] if parts else None,
            "branch": None,
            "worktree": None,
            "output_dir": out_dir,
            "runs": [],
            "total_cost_usd": None,
        }
    )
    rep["artifacts"] = inventory(None, out_dir)
    # The orchestrating session is whichever transcript mentions this runlog.
    owners = grep_transcripts(os.path.basename(path))
    rep["orchestrator_sessions"] = owners
    attach_sessions(rep, set(owners), lookback_hours, branch_hint=rep["branch_key"])
    rep["anomalies"] = flag_anomalies(rep)
    return rep


def grep_transcripts(needle):
    """Which session transcripts mention this string (used to find the session
    that owned an in-session runlog). Plain text grep — no JSON parse.

    Heuristic, and deliberately loose: any session that merely *mentions* the
    runlog path matches, including a later analysis session reading it. Treat
    the result as candidate owners, not proof."""
    try:
        out = subprocess.run(
            ["grep", "-rl", "--include=*.jsonl", needle, PROJECTS],
            capture_output=True, text=True, timeout=120,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [os.path.basename(p)[: -len(".jsonl")] for p in out.split() if p.endswith(".jsonl")]


def _sum(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals), 4) if vals else None


def inventory(cycle_dir, output_dir):
    """Artifacts the cycle produced, plus what else is sitting in $OUT."""
    seen = {}
    for root in filter(None, [os.path.join(cycle_dir, "artifacts") if cycle_dir else None, output_dir]):
        if not os.path.isdir(root):
            continue
        for f in sorted(glob.glob(os.path.join(root, "*"))):
            if os.path.isdir(f) or os.path.islink(f):
                continue
            try:
                st = os.stat(f)
            except OSError:
                continue
            seen[f] = {
                "path": f,
                "bytes": st.st_size,
                "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                "empty": st.st_size == 0,
            }
    # Memos can live in more than one dir: skill-env.sh used to redirect $OUT to the
    # cycle dir, so a cycle's memos may sit under output_dir/decisions, cycle_dir/decisions,
    # or cycle_dir/artifacts/decisions. Scanning only one silently undercounts open memos,
    # and because next-id allocated per-dir, the same id can name different questions.
    decisions = []
    dec_roots = [
        os.path.join(output_dir, "decisions") if output_dir else None,
        os.path.join(cycle_dir, "decisions") if cycle_dir else None,
        os.path.join(cycle_dir, "artifacts", "decisions") if cycle_dir else None,
    ]
    dec_seen = set()
    for root in filter(None, dec_roots):
        if not os.path.isdir(root):
            continue
        for f in sorted(glob.glob(os.path.join(root, "*.md"))):
            real = os.path.realpath(f)
            if real in dec_seen:
                continue
            dec_seen.add(real)
            head = open(f, errors="ignore").read(1200)
            decisions.append(
                {
                    "path": f,
                    "dir": root,
                    "id": _fm(head, "id"),
                    "title": _fm(head, "title"),
                    "status": _fm(head, "status"),
                    "raised_by": _fm(head, "raised_by"),
                }
            )
    return {"files": sorted(seen.values(), key=lambda x: x["mtime"]), "decisions": decisions}


def _fm(text, key):
    m = re.search(r"^%s:\s*(.*)$" % re.escape(key), text, flags=re.M)
    return m.group(1).strip().strip("\"'") if m else None


def attach_sessions(rep, cycle_session_ids, lookback_hours=72, branch_hint=None):
    """Split the branch's sessions into cycle-owned and unlinked. Unlinked
    sessions are the point of this whole script: work the human had to do on
    this branch that the cycle did not do for them.

    The scan window reaches back to the END OF THE PREVIOUS CYCLE on this branch
    (falling back to `lookback_hours`), not to this cycle's start. That matters
    for a retro running inside a live cycle: sessions in the inter-cycle gap are
    the previous cycle's leak, they are complete, and they are readable right now.
    Waiting for a cycle to age is never necessary to measure leakage."""
    now_ms = int(time.time() * 1000)
    prev = previous_cycle_end(rep.get("repo"), rep.get("branch"), rep.get("created_ms"))
    floor_ms = prev["end_ms"] if prev else (rep.get("created_ms") or now_ms) - lookback_hours * 3600 * 1000
    rep["previous_cycle"] = prev
    rep["scan_floor_ms"] = floor_ms
    rep["scan_floor_source"] = "previous cycle on this branch" if prev else "%dh lookback" % lookback_hours

    project_dir = resolve_project_dir(rep.get("worktree") or "")
    branch = rep.get("branch")
    sessions = []
    if project_dir and branch:
        sessions = branch_sessions(project_dir, branch, floor_ms)
    elif project_dir and branch_hint:
        for f in glob.glob(os.path.join(project_dir, "*.jsonl")):
            s = scan_session(f)
            if any(b.replace("/", "-") == branch_hint for b in s["branches"]):
                sessions.append(s)
        sessions.sort(key=lambda x: x["started"] or "")
    elif not project_dir:
        rep["transcripts_available"] = False

    start = rep.get("created_ms")
    # A cycle still running has no end — the window is open to now, so nothing is
    # misfiled as "after" and the retro sees its own live surroundings.
    end = rep.get("finished_ms") if rep.get("status") not in ("running", None) else None
    rep["window_open"] = end is None

    # Other cycles' step sessions on this branch, so they aren't mistaken for
    # human fix-work. Excludes this cycle's own.
    owned_elsewhere = {sid: cid for sid, cid in all_cycle_sessions(rep.get("repo"), rep.get("branch")).items()
                       if sid not in cycle_session_ids}
    other = []
    cyc, unlinked = [], []
    for s in sessions:
        touched = [f for f, _ in s["files_touched"].most_common(20)]
        # Edits under ~/.claude/skills mean the human stopped working on the
        # product and started patching the tooling — the loudest possible signal
        # that a skill was wrong, and one the human already partly acted on.
        skill_edits = [f for f in touched if f.startswith(SKILLS_ROOT)]
        rec = {
            "session_id": s["session_id"],
            "transcript": s["transcript"],
            "subagent_dir": s.get("subagent_dir"),
            "subagents": s["subagents"],
            "title": s["title"],
            "first_prompt": s["first_prompt"] or s["fallback_prompt"],
            "started": s["started"],
            "ended": s["ended"],
            "user_turns": s["user_turns"],
            "assistant_turns": s["assistant_turns"],
            "skills": dict(s["skills"].most_common(6)),
            "commands": dict(s["commands"].most_common(6)),
            "tools": dict(s["tools"].most_common(8)),
            "files_touched": touched[:10],
            "skill_edits": skill_edits,
            "output_tokens": s["output_tokens"],
            "cache_read_tokens": s["cache_read_tokens"],
            "models": dict(s["models"]),
            "when": relation(s["started"], s["ended"], start, end),
            "active": bool(_iso_ms(s["ended"] or "") and now_ms - _iso_ms(s["ended"]) < ACTIVE_WINDOW_MS),
            "trivial": s["assistant_turns"] < TRIVIAL_TURNS and not touched,
        }
        # Attribution: a session in the inter-cycle gap is the PREVIOUS cycle's
        # leak, not this one's. Without this split a retro would blame itself for
        # work that happened before it started.
        rec["attributed_to"] = ("previous-cycle (%s)" % (prev["cycle_id"][:8] if prev else "?")
                                if rec["when"] == "inter-cycle" else "this-cycle")

        if s["session_id"] in cycle_session_ids:
            cyc.append(rec)
            continue
        # Belongs to a different cycle on this branch — machinery, not hand-fixing.
        other_cycle = owned_elsewhere.get(s["session_id"])
        label = other_cycle[:8] if other_cycle else None
        if not other_cycle:
            named = runner_prompt_cycle(rec.get("first_prompt"))
            # A prompt naming THIS cycle is our own step whose request.json didn't
            # record this session id (a resume, or a nested runner invocation).
            if named and str(rep.get("cycle_id") or "").startswith(named):
                cyc.append(rec)
                continue
            if named:
                other_cycle, label = named, "unrecorded: %s" % named
        if other_cycle:
            rec["cycle_id"] = other_cycle
            rec["attributed_to"] = "other-cycle (%s)" % label
            other.append(rec)
        else:
            unlinked.append(rec)
    rep["cycle_sessions"] = cyc
    rep["other_cycle_sessions"] = other
    rep["unlinked_sessions"] = unlinked
    rep["live_rework"] = live_rework(cyc, unlinked)
    rep["transcripts_available"] = bool(sessions) or rep.get("transcripts_available", True)
    missing = sorted(cycle_session_ids - {c["session_id"] for c in cyc})
    rep["cycle_sessions_missing_transcript"] = missing


def relation(s_start, s_end, c_start_ms, c_end_ms):
    """Where a session sits relative to the cycle window.

    `inter-cycle` (wholly before this cycle started, but inside the scan window,
    so after the previous cycle ended) is the label that makes live retros
    useful — it is the previous cycle's leak, measurable now."""
    if not (s_start and c_start_ms):
        return "unknown"
    ss, se = _iso_ms(s_start), _iso_ms(s_end or s_start)
    if ss is None:
        return "unknown"
    if c_end_ms and ss > c_end_ms:
        return "after"
    if ss < c_start_ms and (se or ss) < c_start_ms:
        return "inter-cycle"
    return "during"


def live_rework(cycle_sessions, unlinked_sessions):
    """Rework measured from transcripts instead of commits.

    Commits lag — a file can be broken, hand-fixed, and re-broken before anything
    is committed, and a retro inside a live cycle may have nothing committed yet.
    Session edit-lists are written continuously, so overlap between what the
    cycle's own steps edited and what an outside session edited is available the
    moment it happens."""
    cycle_files = {}
    for s in cycle_sessions:
        for f in s["files_touched"]:
            cycle_files.setdefault(f, []).append(s["session_id"][:8])
    out = []
    for s in unlinked_sessions:
        if s.get("trivial"):
            continue
        for f in s["files_touched"]:
            if f in cycle_files:
                out.append({
                    "file": f,
                    "cycle_sessions": cycle_files[f],
                    "outside_session": s["session_id"][:8],
                    "outside_title": s.get("title"),
                    "when": s["when"],
                    "attributed_to": s.get("attributed_to"),
                })
    # Also: a file two different cycle steps both edited — the later step undoing
    # or patching the earlier one, visible without leaving the cycle.
    multi = [{"file": f, "cycle_sessions": ids} for f, ids in cycle_files.items() if len(set(ids)) > 1]
    return {"outside_overlap": out, "multi_step_files": multi}


def working_tree(worktree):
    """Uncommitted state at analysis time. For a retro inside a live cycle this is
    often where the whole diff still lives, so a commit-only view sees nothing."""
    if not worktree or not os.path.isdir(worktree):
        return {"available": False}
    try:
        st = subprocess.run(["git", "-C", worktree, "status", "--porcelain"],
                            capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {"available": False}
    changed, untracked = [], []
    for line in st.splitlines():
        if not line[3:]:
            continue
        (untracked if line.startswith("??") else changed).append(line[3:])
    return {"available": True, "changed": changed, "untracked": untracked,
            "clean": not (changed or untracked)}


def _iso_ms(iso):
    try:
        t = time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return int((time.mktime(t) - time.timezone) * 1000)
    except (ValueError, TypeError):
        return None


def branch_commits(worktree, branch, cycle_start_ms, cycle_end_ms=None, prev_end_ms=None):
    """Commits on the branch, bucketed against the cycle window.

    Three buckets, not two: `inter-cycle` commits (after the previous cycle, before
    this one) are the previous cycle's hand-fixes; `during` are the cycle's own;
    `after` only exists once the cycle has ended. A live retro reads the first two
    and needs no waiting."""
    if not worktree or not os.path.isdir(worktree):
        return {"available": False, "reason": "worktree not present"}
    def git(*a):
        return subprocess.run(["git", "-C", worktree, *a], capture_output=True, text=True, timeout=60).stdout.strip()
    try:
        base = git("symbolic-ref", "refs/remotes/origin/HEAD").replace("refs/remotes/origin/", "") or "main"
        raw = git("log", "--no-merges", "--format=%H%x1f%at%x1f%s", "origin/%s..%s" % (base, branch or "HEAD"))
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "reason": "git failed"}
    commits = []
    for line in filter(None, raw.splitlines()):
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        at = int(parts[1]) * 1000
        try:
            files = [f for f in git("show", "--name-only", "--format=", parts[0]).splitlines() if f]
        except (OSError, subprocess.SubprocessError):
            files = []
        if cycle_start_ms and at < cycle_start_ms:
            bucket = "inter-cycle" if (not prev_end_ms or at >= prev_end_ms) else "older"
        elif cycle_end_ms and at > cycle_end_ms:
            bucket = "after"
        else:
            bucket = "during"
        commits.append(
            {
                "sha": parts[0][:9],
                "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(at / 1000)),
                "subject": parts[2],
                "bucket": bucket,
                "after_cycle": bucket == "after",
                "files": files,
            }
        )
    commits.reverse()
    bucket_files = lambda b: {f for c in commits if c["bucket"] == b for f in c["files"]}
    during, after, inter = bucket_files("during"), bucket_files("after"), bucket_files("inter-cycle")
    return {
        "available": True,
        "base": base,
        "commits": commits,
        # This cycle's own miss rate — it shipped the file, a later commit fixed it.
        "rework_files": sorted(during & after),
        "new_files_after": sorted(after - during),
        # The PREVIOUS cycle's miss rate, already complete and readable now: files
        # that were hand-fixed in the gap before this cycle even started.
        "inter_cycle_files": sorted(inter),
        "inter_cycle_rework": sorted(inter & during),
    }


def flag_anomalies(rep):
    """Mechanical flags only — each is a fact, not a diagnosis. The model
    decides which of these are worth a skill change."""
    out = []
    add = lambda kind, detail, **kw: out.append(dict(kind=kind, detail=detail, **kw))
    runs = rep.get("runs") or []

    steps = rep.get("steps") or []
    for i, s in enumerate(steps):
        st = (s.get("status") or "").lower()
        if s.get("stub"):
            continue
        if (s.get("attempts") or 0) > 1:
            add("retried-step", "%s ran %d attempts" % (s["id"], s["attempts"]), step=s["id"])
        if (s.get("remediation_rounds") or 0) > 0:
            add("remediated-step", "%s needed %d remediation round(s)" % (s["id"], s["remediation_rounds"]), step=s["id"])
        if st in ("fail", "blocked", "action_required", "error"):
            add("step-not-pass", "%s ended %s" % (s["id"], st), step=s["id"])
        if st in ("pending", "") and rep.get("status") in ("completed", "blocked", "failed"):
            add("step-never-ran", "%s is %s in a %s cycle" % (s["id"], st or "unset", rep.get("status")), step=s["id"])
        # A stop_on_fail gate that did not pass, yet later steps ran anyway. Distinct from
        # step-not-pass: this says the CONTRACT was overridden, whoever did it and for
        # whatever reason. Legitimate human overrides land here too — that is the point.
        if s.get("stop_on_fail") and st in ("fail", "blocked", "action_required", "error"):
            later = [x for x in steps[i + 1:] if (x.get("status") or "").lower() not in ("", "pending")]
            if later:
                add("stop-on-fail-bypassed",
                    "%s ended %s with stop_on_fail set, yet %d later step(s) ran: %s"
                    % (s["id"], st, len(later), ", ".join(x["id"] for x in later)), step=s["id"])

    for r in runs:
        if not r.get("status"):
            add("missing-status-contract", "%s produced no STATUS: line (stdout %d bytes, exit %s)"
                % (r["run"], r.get("stdout_len") or 0, r.get("exit_code")), step=r["step_id"], run=r["run"])
        # A short run is only suspicious when it also failed to report — a fast
        # clean pass (e.g. commit-branch on a small diff) is just fast.
        if (r.get("duration_s") is not None and r["duration_s"] < CRASH_SECONDS
                and (not r.get("status") or r.get("exit_code") not in (0, None))):
            add("suspiciously-short-run", "%s ran %.1fs and reported no clean status — likely died at startup"
                % (r["run"], r["duration_s"]), step=r["step_id"], run=r["run"])
        if (r.get("cache_read_tokens") or 0) > CACHE_READ_HOT:
            add("cache-read-hotspot", "%s read %.1fM cached tokens"
                % (r["run"], r["cache_read_tokens"] / 1e6), step=r["step_id"], run=r["run"])
        term = r.get("termination") or {}
        if isinstance(term, dict) and (term.get("stopped") or term.get("budgetExhausted")):
            add("terminated-run", "%s terminated: %s" % (r["run"], json.dumps(term)), step=r["step_id"], run=r["run"])
        if r.get("exit_code") not in (0, None):
            add("nonzero-exit", "%s exited %s; stderr tail: %s"
                % (r["run"], r["exit_code"], r.get("stderr_tail") or "(empty)"), step=r["step_id"], run=r["run"])

    costs = [r["cost_usd"] for r in runs if isinstance(r.get("cost_usd"), (int, float))]
    if len(costs) >= 4:
        med = sorted(costs)[len(costs) // 2]
        for r in runs:
            c = r.get("cost_usd")
            if isinstance(c, (int, float)) and med and c > 3 * med:
                add("cost-outlier", "%s cost $%.2f vs $%.2f median run" % (r["run"], c, med),
                    step=r["step_id"], run=r["run"])

    for f in (rep.get("artifacts") or {}).get("files", []):
        if f["empty"]:
            add("empty-artifact", "%s is 0 bytes" % f["path"])
    memos = (rep.get("artifacts") or {}).get("decisions", [])
    for d in memos:
        if (d.get("status") or "").lower() == "open":
            add("open-decision-memo", "%s (%s) still open, raised by %s"
                % (d.get("id"), d.get("title"), d.get("raised_by")))
    # One id naming two different questions — the signature of memos allocated in two
    # dirs by a next-id that only scanned one of them. Resolving such an id is ambiguous:
    # the human cannot know which question they answered.
    by_id = collections.defaultdict(list)
    for d in memos:
        if d.get("id"):
            by_id[d["id"]].append(d)
    for mid, group in sorted(by_id.items()):
        titles = {(g.get("title") or "").strip() for g in group}
        if len(group) > 1 and len(titles) > 1:
            add("decision-id-collision",
                "%s names %d different questions across dirs: %s"
                % (mid, len(titles), " | ".join("%s → %s" % (g.get("dir"), (g.get("title") or "?")[:60]) for g in group)))

    starts = collections.Counter(u["started"] for u in rep.get("unlinked_sessions") or [] if u.get("started"))
    for u in rep.get("unlinked_sessions") or []:
        if u.get("trivial"):
            continue
        label = "%s (%s) — %s" % (u["session_id"][:8], u["title"] or "untitled", (u["first_prompt"] or "")[:140])
        if u["when"] == "after":
            add("unlinked-fix-session-after", label, session=u["session_id"])
        elif u["when"] == "during":
            add("unlinked-session-during", "%s ran while the cycle was live%s"
                % (label, " and is STILL ACTIVE" if u.get("active") else ""), session=u["session_id"])
        elif u["when"] == "inter-cycle":
            add("inter-cycle-fix-session", "%s — ran in the gap after %s, so it is that cycle's leak, "
                "measurable now" % (label, u.get("attributed_to")), session=u["session_id"])
        if u.get("skill_edits"):
            add("unlinked-session-edited-skills", "%s hand-edited the skill suite: %s"
                % (u["session_id"][:8], ", ".join(u["skill_edits"])), session=u["session_id"])
        if starts.get(u.get("started"), 0) > 1:
            add("forked-session", "%s shares its start time with another session — likely a resume/fork, "
                "count it once" % u["session_id"][:8], session=u["session_id"])

    c = rep.get("commits") or {}
    for f in c.get("rework_files") or []:
        add("rework-file", "%s was shipped by the cycle and had to be edited again afterwards" % f)
    for f in c.get("inter_cycle_rework") or []:
        add("inter-cycle-rework", "%s was hand-fixed before this cycle started and this cycle touched it "
            "again — the previous cycle left it wrong" % f)
    if c.get("available") and any(cm["after_cycle"] for cm in c.get("commits") or []):
        add("post-cycle-commits", "%d commit(s) landed on this branch after the cycle finished"
            % sum(1 for cm in c["commits"] if cm["after_cycle"]))

    lr = rep.get("live_rework") or {}
    for r in lr.get("outside_overlap") or []:
        add("live-rework", "%s: cycle step(s) %s edited it, then outside session %s (%s) edited it again — "
            "visible without any commit" % (r["file"], ", ".join(r["cycle_sessions"]),
                                            r["outside_session"], r["when"]))
    for r in lr.get("multi_step_files") or []:
        add("intra-cycle-rework", "%s was edited by %d different cycle sessions (%s) — a later step "
            "patching an earlier one" % (r["file"], len(set(r["cycle_sessions"])),
                                        ", ".join(sorted(set(r["cycle_sessions"])))))

    wt = rep.get("working_tree") or {}
    if wt.get("available") and not wt.get("clean"):
        add("uncommitted-at-analysis", "%d changed + %d untracked file(s) uncommitted right now — "
            "commit-only views would miss this diff entirely"
            % (len(wt.get("changed") or []), len(wt.get("untracked") or [])))

    for sid in rep.get("cycle_sessions_missing_transcript") or []:
        add("transcript-missing", "cycle session %s has no transcript on disk" % sid[:8], session=sid)
    if not rep.get("cost_available", True):
        add("no-cost-data", "this surface records no usage/cost — cost findings cannot be made from it")
    return out


# --------------------------------------------------------------------- history


def build_history(repo=None, limit=12):
    """Per-skill and per-step aggregates across cycles: the corroboration data
    that separates a systemic skill problem from one bad run."""
    rows = []
    agg = collections.defaultdict(lambda: {"runs": 0, "slots": 0, "not_pass": 0, "attempts": 0,
                                           "cost": 0.0, "duration": 0.0, "models": collections.Counter()})
    for cdir, man in find_cycle_dirs(repo=repo)[:limit]:
        runs = load_runs(cdir)
        by_step = collections.defaultdict(list)
        for r in runs:
            by_step[r["step_id"]].append(r)
        rows.append(
            {
                "cycle_id": (man.get("id") or os.path.basename(cdir))[:8],
                "cycle_dir": cdir,
                "repo": man.get("repo"),
                "branch": man.get("branch"),
                "cycle": man.get("cycle"),
                "status": man.get("status"),
                "when": time.strftime("%Y-%m-%d %H:%M", time.localtime((man.get("createdAt") or 0) / 1000)),
                "cost_usd": _sum(r.get("cost_usd") for r in runs),
                "steps": len(man.get("steps") or []),
            }
        )
        for s in man.get("steps") or []:
            key = s.get("skill") or s.get("id")
            a = agg[key]
            sruns = by_step.get(s.get("id"), [])
            a["slots"] += 1
            a["runs"] += len(sruns) or (s.get("attempts") or 0)
            a["attempts"] += s.get("attempts") or 0
            if (s.get("status") or "").lower() not in ("pass", "skipped", "pending", ""):
                a["not_pass"] += 1
            a["cost"] += sum(r.get("cost_usd") or 0 for r in sruns)
            a["duration"] += sum(r.get("duration_s") or 0 for r in sruns)
            if s.get("model"):
                a["models"][s["model"]] += 1
    skills = []
    for k, a in sorted(agg.items(), key=lambda kv: -kv[1]["cost"]):
        # `slots` counts step *instances*, not cycles — a cycle can list the same
        # skill several times (impl-1..impl-8), and legacy/backfilled cycles have
        # no run files at all, so they contribute a slot with zero cost.
        skills.append(
            {
                "skill": k,
                "slots": a["slots"],
                "runs": a["runs"],
                "not_pass_slots": a["not_pass"],
                "mean_attempts": round(a["attempts"] / a["slots"], 2) if a["slots"] else None,
                "total_cost_usd": round(a["cost"], 2),
                "mean_cost_per_run_usd": round(a["cost"] / a["runs"], 2) if a["runs"] else None,
                "mean_minutes_per_run": round(a["duration"] / a["runs"] / 60, 1) if a["runs"] else None,
                "models": dict(a["models"]),
            }
        )
    return {"cycles": rows, "skills": skills}


# ---------------------------------------------------------------------- render


def fmt_money(v):
    return "—" if v is None else "$%.2f" % v


def fmt_mins(v):
    return "—" if v is None else "%.1fm" % (v / 60.0)


def render_report(rep):
    L = []
    p = L.append
    p("# Cycle forensics — %s" % (rep.get("cycle_id") or "?"))
    p("")
    p("| field | value |")
    p("|---|---|")
    for k, v in [
        ("surface", rep.get("surface")),
        ("cycle-type", rep.get("cycle")),
        ("repo / branch", "%s / %s" % (rep.get("repo"), rep.get("branch") or rep.get("branch_key"))),
        ("status", rep.get("status")),
        ("started", time.strftime("%Y-%m-%d %H:%M", time.localtime((rep.get("created_ms") or 0) / 1000)) if rep.get("created_ms") else "—"),
        ("finished", time.strftime("%Y-%m-%d %H:%M", time.localtime((rep.get("finished_ms") or 0) / 1000)) if rep.get("finished_ms") else "—"),
        ("total cost", fmt_money(rep.get("total_cost_usd"))),
        ("budget cap", fmt_money(rep.get("max_budget_usd"))),
        ("cycle dir", rep.get("cycle_dir") or rep.get("runlog")),
        ("output dir", rep.get("output_dir")),
        ("worktree", rep.get("worktree")),
    ]:
        p("| %s | %s |" % (k, v if v not in (None, "") else "—"))
    p("")
    p("**Task:** %s" % (rep.get("task") or "—"))
    p("")

    p("## Step ledger")
    p("")
    p("| step | skill | model | status | attempts | remed | cost | time |")
    p("|---|---|---|---|---|---|---|---|")
    for s in rep.get("steps") or []:
        p("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            s.get("id"), s.get("skill") or "—", s.get("model") or "—",
            s.get("status") or "—", s.get("attempts") if s.get("attempts") is not None else "—",
            s.get("remediation_rounds") if s.get("remediation_rounds") is not None else "—",
            fmt_money(s.get("cost_usd")), fmt_mins(s.get("duration_s"))))
    p("")

    if rep.get("runs"):
        p("## Attempts (each isolated run)")
        p("")
        p("| run | model | status | cost | time | out tok | cache read | session | artifact |")
        p("|---|---|---|---|---|---|---|---|---|")
        for r in rep["runs"]:
            p("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                r["run"], r.get("model") or "—", r.get("status") or "**none**",
                fmt_money(r.get("cost_usd")), fmt_mins(r.get("duration_s")),
                "{:,}".format(r["output_tokens"]) if r.get("output_tokens") else "—",
                "%.1fM" % (r["cache_read_tokens"] / 1e6) if r.get("cache_read_tokens") else "—",
                (r.get("session_id") or "—")[:8],
                os.path.basename(r["artifact"]) if r.get("artifact") and r["artifact"] != "-" else "—"))
        p("")
        p("### Cost by model")
        p("")
        by_model = collections.defaultdict(float)
        for r in rep["runs"]:
            if isinstance(r.get("cost_usd"), (int, float)):
                by_model[r.get("model") or "?"] += r["cost_usd"]
        for m, c in sorted(by_model.items(), key=lambda kv: -kv[1]):
            share = 100 * c / rep["total_cost_usd"] if rep.get("total_cost_usd") else 0
            p("- **%s** — %s (%.0f%%)" % (m, fmt_money(c), share))
        p("")

    p("## Step summaries & follow-ups")
    p("")
    for r in rep.get("runs") or []:
        if not (r.get("summary") or r.get("followup") or r.get("decisions")):
            continue
        p("**%s** (%s)" % (r["run"], r.get("status") or "no status"))
        if r.get("summary"):
            p("- SUMMARY: %s" % r["summary"])
        if r.get("followup") and r["followup"] != "-":
            p("- FOLLOWUP: %s" % r["followup"])
        if r.get("decisions") and r["decisions"] != "-":
            p("- DECISIONS: %s" % r["decisions"])
        p("")
    for s in rep.get("steps") or []:
        if rep.get("surface") == "runlog" and (s.get("summary") or s.get("followup")):
            p("**%s** (%s)" % (s["id"], s.get("status")))
            if s.get("summary"):
                p("- SUMMARY: %s" % s["summary"])
            if s.get("followup") and s["followup"] != "-":
                p("- FOLLOWUP: %s" % s["followup"])
            p("")

    art = rep.get("artifacts") or {}
    p("## Artifacts")
    p("")
    for f in art.get("files", []):
        p("- `%s` — %s bytes, %s%s" % (f["path"], "{:,}".format(f["bytes"]), f["mtime"], "  ⚠ EMPTY" if f["empty"] else ""))
    if not art.get("files"):
        p("- (none found)")
    p("")
    if art.get("decisions"):
        p("### Decision memos")
        p("")
        for d in art["decisions"]:
            p("- `%s` — **%s** · %s · raised by %s" % (d["path"], d.get("id"), d.get("status"), d.get("raised_by")))
        p("")

    p("## Sessions")
    p("")
    prev = rep.get("previous_cycle")
    p("Scan window opens at **%s** (%s)%s, and stays open to **now** — a cycle still"
      % (time.strftime("%Y-%m-%d %H:%M", time.localtime((rep.get("scan_floor_ms") or 0) / 1000)),
         rep.get("scan_floor_source") or "?",
         " — previous cycle `%s` (%s)" % (prev["cycle_id"][:8], prev.get("cycle")) if prev else ""))
    p("running has no end, so nothing is misfiled as `after`.")
    p("")
    p("`inter-cycle` = ran between the previous cycle's end and this cycle's start;")
    p("that is the **previous** cycle's leak, complete and readable now. `during` and")
    p("`after` belong to this cycle.")
    p("")
    if rep.get("transcripts_available") is False:
        p("_No transcripts found for this cycle's worktree — transcript-level findings are unavailable._")
        p("")
    p("### Cycle-owned (%d)" % len(rep.get("cycle_sessions") or []))
    p("")
    for s in rep.get("cycle_sessions") or []:
        p("- `%s` %s · %s turns · %s subagents · `%s`" % (
            s["session_id"][:8], s.get("started") or "?", s["assistant_turns"], s["subagents"], s["transcript"]))
    if rep.get("cycle_sessions_missing_transcript"):
        p("")
        p("⚠ cycle sessions with no transcript on disk: %s"
          % ", ".join(x[:8] for x in rep["cycle_sessions_missing_transcript"]))
    p("")
    oc = rep.get("other_cycle_sessions") or []
    if oc:
        p("")
        p("### Other cycles' steps on this branch (%d) — machinery, not hand-fixing" % len(oc))
        p("")
        for s in oc:
            p("- `%s` [%s] %s — %s" % (s["session_id"][:8], s["when"], s.get("started") or "?",
                                       s.get("attributed_to")))
    p("")
    p("### Unlinked — human work outside any cycle (%d)" % len(rep.get("unlinked_sessions") or []))
    p("")
    if not rep.get("unlinked_sessions"):
        p("_None. No human work on this branch outside a cycle in the whole window._")
    for s in rep.get("unlinked_sessions") or []:
        p("- **`%s`** [%s → %s] %s — _%s_%s%s" % (
            s["session_id"][:8], s["when"], s.get("attributed_to") or "?", s.get("started") or "?",
            s.get("title") or "untitled",
            "  ·  🔴 STILL ACTIVE" if s.get("active") else "",
            "  ·  (trivial — no work done)" if s.get("trivial") else ""))
        p("  - prompt: %s" % (s.get("first_prompt") or "—"))
        p("  - %s turns · commands: %s · skills: %s" % (
            s["assistant_turns"],
            ", ".join(s["commands"]) or "—",
            ", ".join(s["skills"]) or "—"))
        if s["files_touched"]:
            p("  - edited: %s" % ", ".join(s["files_touched"][:6]))
        if s.get("skill_edits"):
            p("  - ⚠ **hand-edited the skill suite**: %s" % ", ".join(s["skill_edits"]))
        p("  - transcript: `%s`%s" % (s["transcript"],
                                     " · subagents: `%s`" % s["subagent_dir"] if s.get("subagent_dir") else ""))
    p("")

    lr = rep.get("live_rework") or {}
    if lr.get("outside_overlap") or lr.get("multi_step_files"):
        p("## Live rework (from transcripts — no commit required)")
        p("")
        p("_Commits lag; session edit-lists do not. This is rework visible the moment")
        p("it happens, including inside a cycle that has committed nothing yet._")
        p("")
        for r in lr.get("outside_overlap") or []:
            p("- `%s` — cycle step(s) `%s` edited it, then outside session `%s` (%s, %s) edited it again"
              % (r["file"], ", ".join(r["cycle_sessions"]), r["outside_session"],
                 r["when"], r.get("outside_title") or "untitled"))
        for r in lr.get("multi_step_files") or []:
            p("- `%s` — edited by %d different cycle sessions (`%s`) — a later step patching an earlier one"
              % (r["file"], len(set(r["cycle_sessions"])), ", ".join(sorted(set(r["cycle_sessions"])))))
        p("")

    wt = rep.get("working_tree") or {}
    if wt.get("available"):
        p("## Working tree right now")
        p("")
        if wt.get("clean"):
            p("_Clean — everything is committed._")
        else:
            p("Uncommitted (%d changed, %d untracked) — for a live retro this is often" % (
                len(wt.get("changed") or []), len(wt.get("untracked") or [])))
            p("where the whole diff still is, so a commit-only view would see nothing:")
            p("")
            for f in (wt.get("changed") or [])[:25]:
                p("- `%s`" % f)
            for f in (wt.get("untracked") or [])[:10]:
                p("- `%s` _(untracked)_" % f)
        p("")

    c = rep.get("commits") or {}
    if c.get("available"):
        p("## Commits on branch (vs origin/%s)" % c.get("base"))
        p("")
        for cm in c.get("commits", []):
            p("- %s %s [%s] %s" % (cm["sha"], cm["when"], cm.get("bucket") or "?", cm["subject"]))
        p("")
        if c.get("inter_cycle_files"):
            p("**Previous cycle's leak** — hand-fixed in the gap before this cycle started")
            p("(complete now, no waiting):")
            for f in c["inter_cycle_files"][:20]:
                p("- `%s`%s" % (f, "  ← this cycle touched it too" if f in (c.get("inter_cycle_rework") or []) else ""))
            p("")
        if c.get("rework_files"):
            p("**Rework** — shipped by the cycle, edited again afterwards:")
            for f in c["rework_files"]:
                p("- `%s`" % f)
            p("")
        if c.get("new_files_after"):
            p("**New after the cycle** — files only later commits touched:")
            for f in c["new_files_after"][:20]:
                p("- `%s`" % f)
            p("")

    p("## Mechanical flags")
    p("")
    if not rep.get("anomalies"):
        p("_None._")
    for a in rep.get("anomalies") or []:
        p("- **%s** — %s" % (a["kind"], a["detail"]))
    p("")
    return "\n".join(L)


def render_history(h):
    L = []
    p = L.append
    p("# Cycle history")
    p("")
    p("| cycle | when | repo/branch | type | status | steps | cost |")
    p("|---|---|---|---|---|---|---|")
    for c in h["cycles"]:
        p("| %s | %s | %s/%s | %s | %s | %s | %s |" % (
            c["cycle_id"], c["when"], c["repo"], c["branch"], c["cycle"], c["status"], c["steps"],
            fmt_money(c["cost_usd"])))
    p("")
    p("## Per-skill aggregates across those cycles")
    p("")
    p("_`slots` = step instances across those cycles (a cycle may list a skill more")
    p("than once); legacy/backfilled cycles have no run files, so they add a slot with")
    p("no cost. Cost and time are per **run**._")
    p("")
    p("| skill | slots | runs | non-pass slots | mean attempts | total cost | $/run | min/run | models |")
    p("|---|---|---|---|---|---|---|---|---|")
    for s in h["skills"]:
        p("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            s["skill"], s["slots"], s["runs"], s["not_pass_slots"], s["mean_attempts"],
            fmt_money(s["total_cost_usd"]), fmt_money(s["mean_cost_per_run_usd"]),
            "%sm" % s["mean_minutes_per_run"] if s["mean_minutes_per_run"] is not None else "—",
            ", ".join("%s×%d" % (k, v) for k, v in s["models"].items()) or "—"))
    p("")
    return "\n".join(L)


def render_list(cycles):
    L = ["| cycle | when | repo/branch | type | status | steps | cost | dir |", "|---|---|---|---|---|---|---|---|"]
    for cdir, man in cycles:
        runs = load_runs(cdir)
        L.append("| %s | %s | %s/%s | %s | %s | %s | %s | `%s` |" % (
            (man.get("id") or os.path.basename(cdir))[:8],
            time.strftime("%Y-%m-%d %H:%M", time.localtime((man.get("createdAt") or 0) / 1000)),
            man.get("repo"), man.get("branch"), man.get("cycle"), man.get("status"),
            len(man.get("steps") or []), fmt_money(_sum(r.get("cost_usd") for r in runs)), cdir))
    return "\n".join(L)


# ------------------------------------------------------------------------ main


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    l = sub.add_parser("list")
    l.add_argument("--repo")
    l.add_argument("--branch")
    l.add_argument("--limit", type=int, default=25)

    r = sub.add_parser("report")
    r.add_argument("target", nargs="?", default="latest")
    r.add_argument("--json", action="store_true")
    r.add_argument("--lookback-hours", type=float, default=DEFAULT_LOOKBACK_HOURS,
                   help="session scan floor when the branch has no previous cycle to anchor to "
                        "(default: reach back to the previous cycle's end)")

    h = sub.add_parser("history")
    h.add_argument("--repo")
    h.add_argument("--limit", type=int, default=12)
    h.add_argument("--json", action="store_true")

    s = sub.add_parser("sessions")
    s.add_argument("target", nargs="?", default="latest")
    s.add_argument("--json", action="store_true")

    a = ap.parse_args()

    if a.cmd == "list":
        cycles = find_cycle_dirs(a.repo, a.branch)[: a.limit]
        if not cycles:
            print("no cycle dirs found under %s" % SKILL_OUTPUT)
            print("in-session /orch-ui runs instead leave runlogs:")
            for f in sorted(glob.glob(os.path.join(SKILL_OUTPUT, "*", "*", "orch-run-*.md")), reverse=True)[:20]:
                print("  %s" % f)
            return
        print(render_list(cycles))
    elif a.cmd == "report":
        rep = build_report(a.target, a.lookback_hours)
        print(json.dumps(rep, indent=1, default=str) if a.json else render_report(rep))
    elif a.cmd == "history":
        hist = build_history(a.repo, a.limit)
        print(json.dumps(hist, indent=1, default=str) if a.json else render_history(hist))
    elif a.cmd == "sessions":
        rep = build_report(a.target, DEFAULT_LOOKBACK_HOURS)
        slim = {k: rep.get(k) for k in ("cycle_id", "repo", "branch", "worktree",
                                       "previous_cycle", "scan_floor_ms", "scan_floor_source",
                                       "window_open", "cycle_sessions", "other_cycle_sessions", "unlinked_sessions",
                                       "live_rework", "cycle_sessions_missing_transcript")}
        print(json.dumps(slim, indent=1, default=str))


if __name__ == "__main__":
    main()
