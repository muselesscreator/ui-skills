#!/usr/bin/env python3
"""adhd-fidelity.py — verify a restyled document kept the source wording verbatim.

Usage:
  adhd-fidelity.py <source.md|.txt> <restyled.md> [--json]

The restyled file may ADD only:
  - container blocks fenced by `:::<kind>` ... `:::`
    (kinds: tldr, actions, summary, terms, callout)
  - headings marked with a trailing `{+}`
  - markdown formatting: emphasis, list/blockquote markers, line and paragraph breaks

Everything else must match the source sentence-for-sentence, in the same order.
Splitting a paragraph into bullets at sentence boundaries, or joining/splitting
paragraphs, is allowed — the check compares the wording, not the block layout.

Exit codes: 0 = pass, 1 = fidelity failure, 2 = usage or structure error.
"""
import difflib
import json
import re
import sys

KINDS = {"tldr", "actions", "summary", "terms", "callout"}
ALTERED_RATIO = 0.6

FENCE_RE = re.compile(r"^\s*(```|~~~)")
CONTAINER_OPEN_RE = re.compile(r"^:::\s*([a-z]+)\s*$")
CONTAINER_CLOSE_RE = re.compile(r"^:::\s*$")
ADDED_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s.*\{\+\}\s*$")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
QUOTE_RE = re.compile(r"^\s*(?:>\s?)+")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
HR_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
SENTENCE_SPLIT_RE = re.compile(
    r"(?:(?<=[.!?])|(?<=[.!?][\"')\]]))\s+(?=[\"'(\[]?[A-Z0-9])"
)

TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
    "…": "...",
})


def die(msg):
    print(f"adhd-fidelity: {msg}", file=sys.stderr)
    sys.exit(2)


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().replace("\r\n", "\n").replace("\r", "\n")
    except OSError as e:
        die(f"cannot read {path}: {e}")


def strip_added(text):
    """Blank out added content in the restyled doc, keeping line numbers stable."""
    lines = text.split("\n")
    out = []
    in_code = False
    open_kind = None
    open_line = 0
    for n, line in enumerate(lines, 1):
        if open_kind is None and FENCE_RE.match(line):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue
        if open_kind is not None:
            if CONTAINER_CLOSE_RE.match(line):
                open_kind = None
            elif CONTAINER_OPEN_RE.match(line):
                die(f"line {n}: nested ':::' block inside ':::{open_kind}' (opened line {open_line})")
            out.append("")
            continue
        m = CONTAINER_OPEN_RE.match(line)
        if m:
            if m.group(1) not in KINDS:
                die(f"line {n}: unknown block ':::{m.group(1)}' (allowed: {', '.join(sorted(KINDS))})")
            open_kind, open_line = m.group(1), n
            out.append("")
            continue
        if CONTAINER_CLOSE_RE.match(line):
            die(f"line {n}: ':::' close with no open block")
        if ADDED_HEADING_RE.match(line):
            out.append("")
            continue
        out.append(line)
    if open_kind is not None:
        die(f"line {open_line}: ':::{open_kind}' block is never closed")
    return "\n".join(out)


def norm_inline(s):
    s = s.translate(TRANSLATE)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]*)[^)]*\)", r"\1 (\2)", s)
    s = re.sub(r"\[([^\]]*)\]\(([^)\s]*)[^)]*\)", r"\1 (\2)", s)
    s = re.sub(r"<(https?://[^>]+)>", r"\1", s)
    s = s.replace("**", "").replace("__", "").replace("~~", "").replace("`", "")
    s = re.sub(r"(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)", "", s)
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def units(text):
    """Split a document into comparable units: (key, display, line)."""
    result = []
    para = []
    para_line = 0
    in_code = False

    def flush():
        nonlocal para
        if not para:
            return
        joined = norm_inline(" ".join(para))
        for sent in SENTENCE_SPLIT_RE.split(joined):
            sent = sent.strip()
            if sent:
                result.append((sent, sent, para_line))
        para = []

    for n, line in enumerate(text.split("\n"), 1):
        if FENCE_RE.match(line):
            flush()
            in_code = not in_code
            continue
        if in_code:
            if line.strip():
                code = line.rstrip()
                result.append(("code:" + code.strip(), code, n))
            continue
        if not line.strip() or HR_RE.match(line) or TABLE_SEP_RE.match(line):
            flush()
            continue
        if line.lstrip().startswith("|"):
            flush()
            cells = [norm_inline(c) for c in line.strip().strip("|").split("|")]
            row = " | ".join(cells)
            result.append(("row:" + row, row, n))
            continue
        h = HEADING_RE.match(line)
        if h:
            flush()
            para, para_line = [h.group(1)], n
            flush()
            continue
        body = QUOTE_RE.sub("", line)
        if LIST_RE.match(body):
            flush()
            body = LIST_RE.sub("", body, count=1)
        if not para:
            para_line = n
        para.append(body.strip())
    flush()
    return result


def squash(items):
    return re.sub(r"\s+", "", "".join(k.split(":", 1)[1] if k.startswith(("code:", "row:")) else k
                                      for k, _, _ in items))


def compare(src, out):
    sm = difflib.SequenceMatcher(None, [u[0] for u in src], [u[0] for u in out], autojunk=False)
    report = {"matched": 0, "reblocked": 0, "dropped": [], "altered": [], "invented": []}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            report["matched"] += i2 - i1
            continue
        s_seg, o_seg = src[i1:i2], out[j1:j2]
        if s_seg and o_seg and squash(s_seg) == squash(o_seg):
            report["reblocked"] += len(s_seg)
            continue
        used = set()
        for su in s_seg:
            best, best_j = 0.0, None
            for j, ou in enumerate(o_seg):
                if j in used:
                    continue
                r = difflib.SequenceMatcher(None, su[0], ou[0], autojunk=False).ratio()
                if r > best:
                    best, best_j = r, j
            if best_j is not None and best >= ALTERED_RATIO:
                used.add(best_j)
                ou = o_seg[best_j]
                report["altered"].append({
                    "source_line": su[2], "source": su[1],
                    "restyled_line": ou[2], "restyled": ou[1],
                    "similarity": round(best, 2),
                })
            else:
                report["dropped"].append({"source_line": su[2], "source": su[1]})
        for j, ou in enumerate(o_seg):
            if j not in used:
                report["invented"].append({"restyled_line": ou[2], "restyled": ou[1]})
    report["source_units"] = len(src)
    report["pass"] = not (report["dropped"] or report["altered"] or report["invented"])
    return report


def print_report(r):
    print(f"FIDELITY: {'PASS' if r['pass'] else 'FAIL'}")
    print(f"source units: {r['source_units']}  matched: {r['matched']}  re-blocked: {r['reblocked']}")
    print(f"dropped: {len(r['dropped'])}  altered: {len(r['altered'])}  invented: {len(r['invented'])}")
    if r["dropped"]:
        print("\n--- dropped (in source, missing from restyled) ---")
        for d in r["dropped"]:
            print(f"  source L{d['source_line']}: {d['source']}")
    if r["altered"]:
        print("\n--- altered (wording changed) ---")
        for a in r["altered"]:
            print(f"  source   L{a['source_line']}: {a['source']}")
            print(f"  restyled L{a['restyled_line']}: {a['restyled']}")
    if r["invented"]:
        print("\n--- invented (in restyled, not in source; move into a ::: block or mark the heading {+}) ---")
        for i in r["invented"]:
            print(f"  restyled L{i['restyled_line']}: {i['restyled']}")


def main(argv):
    args = [a for a in argv if a != "--json"]
    if len(args) != 2:
        die("usage: adhd-fidelity.py <source> <restyled.md> [--json]")
    src = units(read(args[0]))
    out = units(strip_added(read(args[1])))
    if not src:
        die(f"source {args[0]} has no text")
    report = compare(src, out)
    if "--json" in argv:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
