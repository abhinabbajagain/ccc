# My Study Library

A single, cohesive study library built from my standalone course-note HTML files.
Everything is **pure HTML + CSS + vanilla JavaScript** — no frameworks, no build
step required to *run* it. Open `index.html` directly in a browser, or host the
whole folder on GitHub Pages / Netlify.

## Quick start

```
index.html                 ← start here (dashboard)
```

Double-click it, or serve the folder:

```bash
python3 -m http.server 8000     # then open http://localhost:8000
```

GitHub Pages / Netlify: point them at the folder root — nothing else to do.

## What you get

| Feature | Where |
|---|---|
| Dashboard listing every subject with progress | `index.html` |
| Consistent sidebar (chapters + other subjects) on every guide | `script.js` builds it from `site-data.js` |
| Full-text search across **all** notes, with highlighted snippets + jump-to-passage | search box on every page (`/` to focus) |
| Dark / light mode (remembers your choice; follows OS if unset) | top-right toggle |
| Breadcrumb "Library / Subject" + back link on every guide | top bar / sidebar |
| Per-section **reviewed** checkboxes + per-subject "mark all" + progress bars | saved in `localStorage` (per browser, nothing uploaded) |
| "Pick up where you left off" card on the dashboard | last-visited subject/chapter |
| Responsive: sidebar becomes a drawer on phones | under 900 px |
| Print stylesheet | Ctrl/Cmd+P on any guide |

## Folder structure

```
study-library/
├── index.html               dashboard (generated from site-data.js at runtime)
├── styles.css               shared shell styles + dark mode
├── script.js                shared behaviour: search, sidebar, theme, progress
├── site-data.js             subject/chapter manifest  (generated — see build.py)
├── search-data.js           full-text search index    (generated — see build.py)
├── build.py                 regeneration tool (optional, Python 3, no deps)
├── README.md
├── compiler-design/
│   ├── cdc.html             ← your original file, kept byte-for-byte
│   └── index.html           ← the guide as it appears in the library
├── dbms/            (DBMS.html + index.html)
├── sad/             (SAD.html + index.html)
├── ai/              (bit353-ai-master-guide.html + index.html)
└── technopreneurship/(techno.html + index.html)
```

### How the original files are preserved

Each `index.html` in a subject folder is the **entire body of your original
file, copied verbatim**, wrapped in the library shell:

- The original `<style>` block is included, with every selector mechanically
  prefixed by a wrapper class (e.g. `.src-dbms …`). No rule was rewritten, so
  each guide keeps its exact original look and typography.
- The only elements removed from the content are the file-level `<nav>`
  table-of-contents blocks — their links are recreated in the library sidebar.
  (DBMS's "↑ Back to Table of Contents" links still work via a `#toc` anchor
  placed at the top of the page.)
- Your original files are also kept untouched in the same folder, so you can
  always diff or restore.
- `build.py` asserts on every run that the original body is present
  byte-for-byte in the generated page.

Code blocks keep their original hand-styled highlighting (e.g. DBMS's SQL
blocks), so no extra highlighting library is needed.

## Adding a new note in the future

**Easiest way — with `build.py` (Python 3, standard library only):**

1. Put the new HTML file into its subject folder, e.g. `networks/net.html`,
   and make sure it is a standalone page (its own `<style>`, content in
   `<body>`, chapter anchors/`<section id>` or `<h2 id>` if you have them).
2. Add a config block to `SUBJECTS` in `build.py` — copy an existing one and
   adjust:

   ```python
   dict(
       id="networks", folder="networks", src="net.html",
       title="Computer Networks", code="NET",
       color="#10b981", monogram="CN",
       blurb="One-line description shown on the dashboard.",
       title_mode="section",          # "section" = <section id=…> chapters,
                                      # "h2"      = chapters are <h2 id=…>
       nav_open='<nav id="toc">',     # exact opening tag of the file-level nav
                                      # to replace (use "<nav>" for a bare <nav>)
       groups=[("Chapters", ["ch1", "ch2"]),          # sidebar order
               ("Exam prep & revision", ["qbank"])],
       sub_tag="h3",                  # heading level used for fine search index
   ),
   ```

3. Run `python3 build.py` (or `python3 build.py networks` for one subject).
   It regenerates the subject page, `site-data.js` (sidebar) and
   `search-data.js` (search), and updates the dashboard automatically.

The `groups` list is where you decide which sections count as "Chapters" vs
"Exam prep" in the sidebar; any ids you don't list are appended to the first
group. `TITLE_OVERRIDES` in `build.py` fixes any heading text that extracts
weirdly.

**Manual way (no Python):** duplicate an existing subject folder, replace the
content between the `content-inner` divs (and that folder's scoped `<style>`),
add one entry to `window.SITE_DATA` in `site-data.js` and matching entries to
`window.SEARCH_DATA` in `search-data.js`. The dashboard and sidebar read those
two files, so nothing else needs to change.

## Notes & small print

- **Theme:** the AI guide (BIT 353) has its own built-in dark theme; the
  library toggle keeps it in sync. Compiler Design's guide is natively
  dark-themed and stays that way by design; the other three guides receive
  dark-mode colour overrides from `styles.css`.
- **Fonts:** the AI guide references Google Fonts; offline it simply falls
  back to system fonts.
- **Progress data** lives in your browser's `localStorage` under the keys
  `slib-theme`, `slib-progress`, `slib-lastvisit`. Clearing site data resets
  it.
- **Search** works by opening `index.html` directly *and* when hosted (the
  index is pre-built into `search-data.js`, so no network/fetch is involved).
