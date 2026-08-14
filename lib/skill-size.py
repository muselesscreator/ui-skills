#!/usr/bin/env python3
"""Prose-budget check for the global skill suite (AUTHORING.md § Prose tiering).

Measures each SKILL.md's *prose words* — the reasoning material a model has to
read and reconcile — and compares it to the budget for the model tier the skill
actually runs on.

Prose words EXCLUDE, deliberately:
  - frontmatter (metadata, not read as instructions)
  - fenced code blocks (commands and output templates — these constrain output
    rather than inviting deliberation, so they are cheap)
  - markdown table rows (structured lookup, not argument)
  - blockquote lines (verbatim subagent prompt templates)

Tier is resolved from the cycle definitions in orch-ui/cycles/*.md: a skill's
budget is the STRICTEST tier any cycle runs it at. Skills no cycle references
have no budget and are reported as unbudgeted.

Usage:
  skill-size.py                    # table for every skill, exit 1 if any over
  skill-size.py plan-ui impl-ui    # only these
  skill-size.py --json
"""

import json
import re
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent
CYCLES = SKILLS / "orch-ui" / "cycles"

# prose-word budgets by tier — see AUTHORING.md § Prose tiering & size budgets
BUDGETS = {"opus": 900, "sonnet": 1500, "haiku": 2100}
ORCHESTRATOR_BUDGET = 1600  # orch-ui is a protocol doc, not a step body
STRICTNESS = ["opus", "sonnet", "haiku"]  # tightest first


def prose_words(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").split("\n")
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1
    fenced = False
    total = 0
    for line in lines[i:]:
        s = line.strip()
        if s.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not s or s.startswith("|") or s.startswith(">"):
            continue
        total += len(s.split())
    return total


def tiers_from_cycles() -> dict:
    """skill name -> strictest tier any cycle definition runs it at."""
    found = {}
    for cycle in sorted(CYCLES.glob("*.md")):
        if cycle.name == "README.md":
            continue
        text = cycle.read_text(encoding="utf-8")
        # steps live in the frontmatter as a YAML list; a light scan is enough
        skill = None
        for line in text.split("\n"):
            m = re.match(r"\s*-?\s*skill:\s*(\S+)", line)
            if m:
                skill = m.group(1)
                continue
            m = re.match(r"\s*model:\s*(haiku|sonnet|opus)\b", line)
            if m and skill:
                found.setdefault(skill, []).append(m.group(1))
            if re.match(r"\s*-\s+id:", line):
                skill = None
    return {
        s: min(t, key=lambda x: STRICTNESS.index(x)) for s, t in found.items()
    }


def main(argv):
    as_json = "--json" in argv
    wanted = [a for a in argv if not a.startswith("--")]
    tiers = tiers_from_cycles()

    rows = []
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if wanted and name not in wanted:
            continue
        words = prose_words(skill_md)
        if name == "orch-ui":
            tier, budget = "orchestrator", ORCHESTRATOR_BUDGET
        elif name in tiers:
            tier = tiers[name]
            budget = BUDGETS[tier]
        else:
            tier, budget = "-", None
        over = budget is not None and words > budget
        rows.append(
            {
                "skill": name,
                "tier": tier,
                "prose_words": words,
                "budget": budget,
                "over_by": (words - budget) if over else 0,
                "status": "OVER" if over else ("ok" if budget else "unbudgeted"),
                "rationale_file": (skill_md.parent / "RATIONALE.md").exists(),
            }
        )

    if as_json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'skill':22} {'tier':13} {'prose':>6} {'budget':>7}  status")
        for r in sorted(rows, key=lambda r: -r["prose_words"]):
            b = r["budget"] if r["budget"] else "-"
            flag = f"OVER by {r['over_by']}" if r["over_by"] else r["status"]
            print(f"{r['skill']:22} {r['tier']:13} {r['prose_words']:6} {b:>7}  {flag}")
        overs = [r for r in rows if r["over_by"]]
        if overs:
            print(
                "\n"
                + f"{len(overs)} skill(s) over budget. Trim prose, or move rationale "
                "to the skill's RATIONALE.md (AUTHORING.md § Prose tiering)."
            )

    return 1 if any(r["over_by"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
