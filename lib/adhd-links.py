#!/usr/bin/env python3
"""adhd-links.py — resolve a restyled document's [[wiki-links]] to hrefs.

Usage:
  adhd-links.py <restyled.md> [source-path]

Prints a JSON object mapping each link target as written (the part before any
`#` or `|`, e.g. "repository-functions") to {"href", "kind", "title"}. The
reading page shows every wiki-link as readable text and turns the resolved
ones into links. Resolution, first match wins:

  page     — another adhd-format reading page restyled from that note (newest
             run wins), linked relatively so the pages work as a set
  obsidian — the note inside the Obsidian vault holding the source (nearest
             ancestor with a .obsidian/ dir), opened by absolute path
  file     — the note as a .md file, searched under the source's own directory

A note matches the way Obsidian resolves links: `name` matches any `name.md`
in the tree, the shortest path wins; `dir/name` matches by path suffix.
Targets that resolve to nothing are left out; the page shows them as plain
text. With no source path (pasted text) only `page` resolution is possible,
and only for absolute targets, so the output is usually `{}`.
"""
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

OUT_ROOT = Path.home() / ".claude" / "skill-output" / "adhd-format"
SKIP_DIRS = {".git", "node_modules", ".obsidian", ".trash"}
WIKILINK = re.compile(r"!?\[\[([^\[\]\n]+?)\]\]")
FENCE = re.compile(r"^\s*(```|~~~)")


def targets(md_text):
    found, in_code = [], False
    for line in md_text.split("\n"):
        if FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        # Inline code spans are literal text, not links.
        prose = re.sub(r"`[^`]*`", "", line)
        for m in WIKILINK.finditer(prose):
            # Inside a pipe table Obsidian escapes the alias bar as \|.
            t = m.group(1).split("|", 1)[0].rstrip("\\").split("#", 1)[0].strip()
            if t and t not in found:
                found.append(t)
    return found


def find_root(source):
    """The Obsidian vault holding source, else source's own directory."""
    for d in [source.parent, *source.parents]:
        if (d / ".obsidian").is_dir():
            return d, True
    return source.parent, False


def index_notes(root):
    notes = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(".md"):
                notes.append(Path(dirpath) / f)
    return notes


def match(target, notes, root):
    want = target[:-3] if target.endswith(".md") else target
    want = want.strip("/")
    hits = []
    for n in notes:
        rel = n.relative_to(root).with_suffix("").as_posix()
        if rel == want or rel.endswith("/" + want):
            hits.append(n)
    if not hits:
        return None
    return min(hits, key=lambda p: (len(p.relative_to(root).parts), str(p)))


def restyled_pages():
    """Map a source note's real path to its newest reading page."""
    pages = {}
    if not OUT_ROOT.is_dir():
        return pages
    for run in OUT_ROOT.iterdir():
        sp, html = run / "source-path.txt", run / "restyled.html"
        if not (sp.is_file() and html.is_file()):
            continue
        src = os.path.realpath(sp.read_text().strip())
        mtime = html.stat().st_mtime
        if src not in pages or mtime > pages[src][1]:
            pages[src] = (html, mtime)
    return {k: v[0] for k, v in pages.items()}


def main():
    if len(sys.argv) < 2:
        print("usage: adhd-links.py <restyled.md> [source-path]", file=sys.stderr)
        sys.exit(2)
    md = Path(sys.argv[1])
    source = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 and sys.argv[2] else None
    wanted = targets(md.read_text())
    out = {}
    if not wanted or not source or not source.is_file():
        print(json.dumps(out))
        return

    root, is_vault = find_root(source.resolve())
    notes = index_notes(root)
    pages = restyled_pages()
    here = md.resolve().parent

    for t in wanted:
        note = match(t, notes, root)
        if not note:
            continue
        rel = note.relative_to(root).as_posix()
        page = pages.get(os.path.realpath(note))
        if page and page.resolve() != (here / "restyled.html").resolve():
            out[t] = {"href": os.path.relpath(page, here), "kind": "page",
                      "title": "Reading page: " + rel}
        elif is_vault:
            out[t] = {"href": "obsidian://open?path=" + urllib.parse.quote(str(note), safe=""),
                      "kind": "obsidian", "title": "Open in Obsidian: " + rel}
        else:
            out[t] = {"href": note.as_uri(), "kind": "file", "title": rel}

    # "<" escaped so the JSON can sit inside a <script> element verbatim.
    print(json.dumps(out, ensure_ascii=False).replace("<", "\\u003c"))


if __name__ == "__main__":
    main()
