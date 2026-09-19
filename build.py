#!/usr/bin/env python3
"""
build.py — regenerates the Study Library from the original note files.

The site itself is pure HTML/CSS/JS (no build step needed to run it).
This script is only a convenience for (re)generating pages, the sidebar
manifest (site-data.js), the full-text search index (search-data.js) and
the dashboard (index.html) when you add or change note files.

Usage:
    python3 build.py              # rebuild everything
    python3 build.py dbms ai      # rebuild only the named subject folders

To add a brand-new subject, see README.md ("Adding a new subject").
"""

import hashlib
import html as htmllib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT.parent / "uploads"

# ---------------------------------------------------------------------------
# Subject configuration
# ---------------------------------------------------------------------------
# title_mode: "section"  -> chapters are <section id="..."> elements,
#                           title = first h1/h2 inside the section.
#            "h2"        -> chapters are the <h2 id="..."> elements themselves
#                           (content flows until the next h2[id]).
# nav_open:   exact opening tag of the file-level <nav> that is replaced by
#             the library sidebar (removed from the page; links re-created).
# groups:     list of (group name, [chapter ids]) — order = sidebar order.
#             ids not listed here are appended to the first group as-is.
SUBJECTS = [
    dict(
        id="compiler-design", folder="compiler-design", src="cdc.html",
        title="Compiler Design & Construction", code="CDC",
        color="#38bdf8", monogram="CD",
        blurb=("Seven chapters from compiling fundamentals to code generation — "
               "plus a terminology dictionary, exam checklists and a chapter-wise "
               "question bank."),
        title_mode="section", nav_open='<nav id="topnav">',
        groups=[
            ("Chapters", ["ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "ch7"]),
            ("Exam prep & revision", ["dict", "howto", "qbank", "revision", "matrix", "report"]),
        ],
        sub_tag="h3",
    ),
    dict(
        id="dbms", folder="dbms", src="DBMS.html",
        title="BIT 231 — Database Management System", code="DBMS",
        color="#3b82f6", monogram="DB",
        blurb=("Twelve chapters covering the full BIT 231 syllabus — ER modelling, "
               "relational algebra, normalisation, SQL — with per-chapter VSQA / SQA "
               "/ LQA banks, practice drills and a rapid-revision section."),
        title_mode="section", nav_open='<nav id="toc">',
        groups=[
            ("Chapters", ["ch1", "ch2", "ch3", "ch4", "ch5", "ch6",
                          "ch7", "ch8", "ch9", "ch10", "ch11", "ch12"]),
            ("Practice drills", ["sqlpractice", "rapractice", "normpractice"]),
            ("Exam prep & revision", ["revision", "qbank", "matrix", "finalreport"]),
        ],
        sub_tag="h2",
    ),
    dict(
        id="sad", folder="sad", src="SAD.html",
        title="System Analysis & Design", code="SAD",
        color="#14b8a6", monogram="SA",
        blurb=("Eight chapters of SAD theory with worked examples and diagrams — "
               "plus a consolidated mistakes-and-traps section, an all-chapter "
               "question bank and rapid revision."),
        title_mode="h2", nav_open="<nav>",
        groups=[
            ("Chapters", ["ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "ch7", "ch8"]),
            ("Exam prep & revision", ["mistakes", "qbank", "revision", "checklist",
                                      "matrix", "outcomes", "report"]),
        ],
        sub_tag="h3",
    ),
    dict(
        id="ai", folder="ai", src="bit353-ai-master-guide.html",
        title="BIT 353 — Artificial Intelligence", code="AI",
        color="#a78bfa", monogram="AI",
        blurb=("Seven topics — agents, problem solving, searching, knowledge "
               "representation, ML, neural nets and NLP — with worked examples, "
               "a formula sheet, a practice bank and a final question bank."),
        title_mode="h2", nav_open='<nav class="toc" aria-label="Table of contents">',
        groups=[
            ("Topics", ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]),
            ("Exam prep & revision", ["matrix", "outcomes", "audit", "practice",
                                      "formulas", "revision", "bank"]),
        ],
        sub_tag="h3",
    ),
    dict(
        id="technopreneurship", folder="technopreneurship", src="techno.html",
        title="Technopreneurship", code="TECHNO",
        color="#f59e0b", monogram="TP",
        blurb=("Eight core topics from innovation to raising capital, plus "
               "additional topics 9–12, worked examples, a question bank and "
               "past-board patterns."),
        title_mode="section", nav_open='<nav id="toc">',
        groups=[
            ("Topics", ["intro", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8",
                        "add-header", "t9", "t10", "t11", "t12"]),
            ("Exam prep & revision", ["revision", "qbank", "pbank", "matrix"]),
        ],
        sub_tag="h3",
    ),
]

# Titles that need a manual fix after extraction (markup quirks).
TITLE_OVERRIDES = {
    ("technopreneurship", "add-header"): "Additional Topics 9–12",
    ("sad", "outcomes"): "Learning-Outcome Alignment",
    ("ai", "outcomes"): "Learning-Outcome Alignment",
}

FAVICON = ("data:image/svg+xml," +
           "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' rx='7' fill='%230d2a4a'/%3E"
           "%3Cpath d='M9 8h9a4 4 0 0 1 0 8H9zm0 8h11a4 4 0 0 1 0 8H9z' fill='none' "
           "stroke='%237dd3fc' stroke-width='2.2'/%3E%3C/svg%3E")


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------
def strip_tags(fragment: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", fragment)
    return htmllib.unescape(re.sub(r"\s+", " ", txt)).strip()


def clean_heading(fragment: str) -> str:
    """Heading text, without decorative unit-number / tag spans."""
    fragment = re.sub(r'<span class="unitno">.*?</span>', " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r'<span class="tag[^"]*">.*?</span>', " ", fragment, flags=re.S | re.I)
    return strip_tags(fragment)


def extract_head_externals(head: str) -> str:
    """Keep <link>/<meta> tags pointing at external resources (e.g. fonts)."""
    keep = []
    for m in re.finditer(r'<(link|meta)\b[^>]*>', head, flags=re.I):
        tag = m.group(0)
        if re.search(r'(?:href|content)\s*=\s*["\']https?://', tag, re.I):
            keep.append(tag)
    return "\n".join(keep)


def split_top_level(s: str, sep: str = ",") -> list:
    """Split on `sep` only outside parentheses."""
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def scope_selector(sel: str, w: str):
    sel = sel.strip()
    if not sel:
        return None
    if sel == ":root":
        return w
    if sel.startswith(":root"):
        return w + sel[5:]          # :root[data-theme=…] → w[data-theme=…]
    if sel == "html" or sel == "body":
        return w
    if sel == "*":
        return w + " *"
    if sel.startswith(("html ", "body ", "html*", "body*")):
        return w + " " + sel[4:].lstrip("*").strip() if sel[4:].startswith("*") else w + " " + sel[4:]
    return w + " " + sel


def scope_css(css: str, w: str) -> str:
    """Mechanically scope a stylesheet to wrapper class `w`.

    `html`/`body`/`:root` selectors are remapped to the wrapper, every other
    selector is prefixed.  At-rules (@media …) are processed recursively.
    Declarations are never touched, so the visual result is unchanged.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def process(block: str) -> str:
        out, i, n = [], 0, len(block)
        while i < n:
            j = block.find("{", i)
            if j == -1:
                break
            depth, k = 1, j + 1
            while k < n and depth:
                if block[k] == "{":
                    depth += 1
                elif block[k] == "}":
                    depth -= 1
                k += 1
            pre = block[i:j].strip()
            body = block[j + 1:k - 1]
            if pre.startswith(("@media", "@supports", "@container")):
                out.append(pre + " {\n" + process(body) + "\n}")
            else:
                sels = [scope_selector(s, w) for s in split_top_level(pre)]
                sels = [s for s in sels if s]
                if sels:
                    out.append(",\n".join(sels) + " {\n" + body.strip() + "\n}")
            i = k
        return "\n".join(out)

    return process(css)


def section_spans(body: str, mode: str):
    """Yield (id, start, end) spans of top-level chapters."""
    if mode == "section":
        spans, matches = [], list(re.finditer(r'<section\b[^>]*\bid="([^"]+)"[^>]*>', body))
        for idx, m in enumerate(matches):
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
            spans.append((m.group(1), m.start(), end))
        return spans
    # mode == "h2"
    matches = list(re.finditer(r'<h2\b[^>]*\bid="([^"]+)"[^>]*>', body))
    spans = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        spans.append((m.group(1), m.start(), end))
    return spans


def chapter_title(body: str, span, mode: str) -> str:
    cid, start, end = span
    chunk = body[start:end]
    if mode == "h2":
        m = re.match(r'<h2\b[^>]*>(.*?)</h2>', chunk, flags=re.S)
        return clean_heading(m.group(1)) if m else cid
    m = re.search(r'<h[12]\b[^>]*>(.*?)</h[12]>', chunk, flags=re.S)
    return clean_heading(m.group(1)) if m else cid


def extract_text(fragment: str, limit: int = 3000) -> str:
    """Visible text of a fragment (SVGs/scripts stripped) for the search index."""
    f = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    f = re.sub(r"<svg\b.*?</svg>", " ", f, flags=re.S | re.I)
    f = re.sub(r"<(script|style)\b.*?</\1>", " ", f, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", f)
    txt = htmllib.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip().lower()[:limit]


def subheading_entries(body: str, span, sub_tag: str, subject: str, group: str):
    """Finer-grained search entries: each subheading inside a chapter."""
    cid, start, end = span
    chunk = body[start:end]
    entries = []
    matches = list(re.finditer(
        rf'<{sub_tag}\b[^>]*>(.*?)</{sub_tag}>', chunk, flags=re.S))
    for idx, m in enumerate(matches):
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(chunk)
        text = extract_text(chunk[m.end():next_start], 1500)
        title = clean_heading(m.group(1))
        if len(title) < 3 or not text:
            continue
        entries.append(dict(s=subject, g=group, t=title, a=cid, c="sub", txt=text))
    return entries


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
PAGE_TPL = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — My Study Library</title>
<meta name="description" content="{blurb}">
<link rel="icon" href="{favicon}">
{externals}
<link rel="stylesheet" href="../styles.css">
<style>
/* =====================================================================
   Original stylesheet from {src} — mechanically scoped to .src-{sid}.
   The note's own design is preserved exactly; only selectors were
   prefixed so they apply inside this library page.
   ===================================================================== */
{scoped_css}
</style>
</head>
<body class="page-subject" data-subject="{sid}">
<div class="shell">
  <header class="topbar">
    <button class="iconbtn nav-toggle" id="nav-toggle" aria-label="Open menu" aria-expanded="false">
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
    </button>
    <a class="brand" href="../index.html">
      <svg viewBox="0 0 32 32" width="24" height="24" aria-hidden="true"><rect width="32" height="32" rx="7" fill="currentColor" opacity="0.14"/><path d="M9 8h9a4 4 0 0 1 0 8H9zm0 8h11a4 4 0 0 1 0 8H9z" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>
      <span>Study Library</span>
    </a>
    <nav class="crumbs" aria-label="Breadcrumb">
      <a href="../index.html">Library</a><span class="sep">/</span><strong>{short}</strong>
    </nav>
    <div class="topbar-search" role="search">
      <svg class="s-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-3.8-3.8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <input id="search-input" type="search" placeholder="Search all notes…  ( / )" autocomplete="off" spellcheck="false" aria-label="Search all notes">
      <div class="search-results" id="search-results" hidden></div>
    </div>
    <button class="iconbtn theme-toggle" id="theme-toggle" aria-label="Toggle dark mode"></button>
  </header>

  <aside class="sidebar" id="sidebar" aria-label="Subjects and chapters">
    <div class="side-block">
      <div class="side-head">
        <h2><span class="dot" style="background:{color}"></span>{short}</h2>
        <button id="mark-all" class="mark-all" type="button" title="Toggle reviewed status for every section of this subject">✓ reviewed</button>
      </div>
      <div class="side-progress" aria-hidden="true">
        <div class="bar"><span id="prog-bar" style="width:0%"></span></div>
        <em id="prog-label">0 of 0 reviewed</em>
      </div>
      <nav class="side-chapters" id="side-chapters"></nav>
    </div>
    <div class="side-block">
      <h3 class="side-sub">Other subjects</h3>
      <ul class="side-others" id="side-others"></ul>
    </div>
  </aside>
  <div class="scrim" id="scrim" hidden></div>

  <main class="content" id="content">
    <div class="content-inner src src-{sid}">
<span id="toc" hidden></span>{content}
    </div>
  </main>
</div>
<script src="../site-data.js"></script>
<script src="../search-data.js"></script>
<script src="../script.js"></script>
</body>
</html>
"""

DASH_TPL = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>My Study Library</title>
<meta name="description" content="A personal library of course notes and exam guides.">
<link rel="icon" href="{favicon}">
<link rel="stylesheet" href="styles.css">
</head>
<body class="page-dashboard">
<div class="dash">
  <header class="dash-hero">
    <div class="dash-hero-inner">
      <div class="dash-brand">
        <svg viewBox="0 0 32 32" width="42" height="42" aria-hidden="true"><rect width="32" height="32" rx="7" fill="currentColor" opacity="0.16"/><path d="M9 8h9a4 4 0 0 1 0 8H9zm0 8h11a4 4 0 0 1 0 8H9z" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>
        <div>
          <h1>My Study Library</h1>
          <p class="tagline">All of my course notes and exam guides — in one place.</p>
        </div>
      </div>
      <div class="dash-actions">
        <div class="topbar-search dash-search" role="search">
          <svg class="s-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-3.8-3.8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input id="search-input" type="search" placeholder="Search all notes…  ( / )" autocomplete="off" spellcheck="false" aria-label="Search all notes">
          <div class="search-results" id="search-results" hidden></div>
        </div>
        <button class="iconbtn theme-toggle" id="theme-toggle" aria-label="Toggle dark mode"></button>
      </div>
    </div>
    <p class="dash-stats" id="dash-stats"></p>
  </header>

  <div class="continue-card" id="continue-card" hidden></div>

  <main class="dash-grid" id="subject-grid" aria-label="Subjects"></main>

  <footer class="dash-footer">
    <span>Notes preserved verbatim from the original files · progress is saved in this browser only</span>
    <a href="index.html" onclick="location.reload();return false">Refresh</a>
  </footer>
</div>
<script src="site-data.js"></script>
<script src="search-data.js"></script>
<script src="script.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build_subject(cfg: dict):
    folder = ROOT / cfg["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    src_file = folder / cfg["src"]
    if not src_file.exists():
        up = UPLOADS / cfg["src"]
        if up.exists():
            src_file.write_bytes(up.read_bytes())
        else:
            raise SystemExit(f"missing source file: {src_file} (also not in {UPLOADS})")

    raw = src_file.read_text(encoding="utf-8")
    m = re.search(r"<head\b[^>]*>(.*?)</head>", raw, flags=re.S | re.I)
    head = m.group(1)
    m = re.search(r"<body[^>]*>(.*)</body>", raw, flags=re.S | re.I)
    body = m.group(1)
    css = re.search(r"<style[^>]*>(.*?)</style>", head, flags=re.S).group(1)

    # Remove the file-level nav (replaced by the library sidebar).
    nav_open = cfg["nav_open"]
    i = body.find(nav_open)
    assert i != -1, f"nav not found in {cfg['src']}"
    j = body.find("</nav>", i)
    assert j != -1
    content = body[:i] + body[j + len("</nav>"):]

    w = f".src-{cfg['id']}"
    scoped = scope_css(css, w)

    # Chapters
    spans = section_spans(body, cfg["title_mode"])
    chapters = []
    seen = set()
    for span in spans:
        cid = span[0]
        if cid in seen:
            continue
        seen.add(cid)
        title = TITLE_OVERRIDES.get((cfg["id"], cid)) or chapter_title(body, span, cfg["title_mode"])
        chapters.append(dict(id=cid, title=title))
    if not chapters:
        raise SystemExit(f"no chapters found in {cfg['src']}")

    # Sidebar groups (keep configured order; append unknown ids to group 1)
    groups = []
    chapter_by_id = {c["id"]: c for c in chapters}
    used = set()
    for gname, ids in cfg["groups"]:
        items = []
        for cid in ids:
            if cid in chapter_by_id:
                items.append(chapter_by_id[cid])
                used.add(cid)
        if items:
            groups.append(dict(name=gname, items=items))
    leftovers = [c for c in chapters if c["id"] not in used]
    if leftovers:
        if groups:
            groups[0]["items"].extend(leftovers)
        else:
            groups.append(dict(name="Sections", items=leftovers))

    # Search entries
    search = []
    span_by_id = {s[0]: s for s in spans}
    group_of = {}
    for g in groups:
        for it in g["items"]:
            group_of[it["id"]] = g["name"]
    for c in chapters:
        span = span_by_id[c["id"]]
        chunk = body[span[1]:span[2]]
        gname = group_of[c["id"]]
        search.append(dict(s=cfg["id"], g=gname, t=c["title"], a=c["id"], c="chap",
                           txt=extract_text(chunk, 10000)))
        search.extend(subheading_entries(body, span, cfg["sub_tag"], cfg["id"], gname))

    html_out = PAGE_TPL.format(
        title=htmllib.escape(cfg["title"]),
        short=htmllib.escape(cfg["title"]),
        blurb=htmllib.escape(cfg["blurb"]),
        favicon=FAVICON,
        externals=extract_head_externals(head),
        scoped_css=scoped,
        sid=cfg["id"],
        src=cfg["src"],
        color=cfg["color"],
        content=content,
    )
    (folder / "index.html").write_text(html_out, encoding="utf-8")

    # Integrity check: original body (minus the removed nav) must be present verbatim.
    assert body[:i] in html_out and body[j + len("</nav>"):] in html_out, \
        f"content integrity check failed for {cfg['id']}"

    return dict(
        cfg=cfg,
        sha=hashlib.sha256(src_file.read_bytes()).hexdigest()[:12],
        chapters=chapters,
        groups=groups,
        search=search,
    )


def write_dashboard(results):
    page = DASH_TPL.format(favicon=FAVICON)
    (ROOT / "index.html").write_text(page, encoding="utf-8")


def write_data_files(results):
    subjects = []
    search = []
    for r in results:
        cfg = r["cfg"]
        subjects.append(dict(
            id=cfg["id"], title=cfg["title"], code=cfg["code"], color=cfg["color"],
            monogram=cfg["monogram"], blurb=cfg["blurb"], src=cfg["src"],
            sha=r["sha"], url=cfg["folder"] + "/index.html",
            groups=[dict(name=g["name"], items=g["items"]) for g in r["groups"]],
        ))
        search.extend(r["search"])

    today = date.today().strftime("%B %d, %Y")
    manifest = (
        "/* Generated by build.py — do not edit by hand. Re-run the build instead. */\n"
        "window.SITE_DATA = " + json.dumps(
            dict(subjects=subjects, updated=today),
            indent=1, ensure_ascii=False) + ";\n"
    )
    (ROOT / "site-data.js").write_text(manifest, encoding="utf-8")

    payload = json.dumps(search, separators=(",", ":"), ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    (ROOT / "search-data.js").write_text(
        "/* Generated by build.py — full-text index for client-side search. "
        "Re-run the build after editing notes. */\n"
        "window.SEARCH_DATA = " + payload + ";\n",
        encoding="utf-8")


def main():
    only = set(sys.argv[1:])
    results = []
    for cfg in SUBJECTS:
        if only and cfg["folder"] not in only and cfg["id"] not in only:
            continue
        r = build_subject(cfg)
        n_sec = sum(len(g["items"]) for g in r["groups"])
        n_sub = len(r["search"])
        print(f"[ok] {cfg['folder']:<20} sections={n_sec:<3} search entries={n_sub:<4} sha={r['sha']}")
        for g in r["groups"]:
            for it in g["items"]:
                print(f"       {it['id']:<14} {it['title'][:64]}")
        results.append(r)
    write_dashboard(results)
    write_data_files(results)
    total = sum(len(r["search"]) for r in results)
    size = (ROOT / "search-data.js").stat().st_size
    print(f"\nDone. Dashboard + {len(results)} subject pages + site-data.js + search-data.js "
          f"({total} search entries, {size/1024:.0f} KB).")


if __name__ == "__main__":
    main()
