/* ==========================================================================
   My Study Library — shared script
   Works on the dashboard (body.page-dashboard) and subject pages
   (body.page-subject with data-subject). No dependencies.
   ========================================================================== */
(function () {
  "use strict";

  var DATA = window.SITE_DATA || { subjects: [] };
  var SEARCH = window.SEARCH_DATA || [];
  var LS_THEME = "slib-theme";
  var LS_PROGRESS = "slib-progress";
  var LS_VISIT = "slib-lastvisit";

  /* ---------------------------------------------------------------- utils */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function store(key, fallback) {
    try {
      var v = localStorage.getItem(key);
      return v ? JSON.parse(v) : fallback;
    } catch (e) { return fallback; }
  }
  function save(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { /* private mode */ }
  }
  function progress() { return store(LS_PROGRESS, {}); }
  function subjectById(id) {
    for (var i = 0; i < DATA.subjects.length; i++) if (DATA.subjects[i].id === id) return DATA.subjects[i];
    return null;
  }
  function allItems(sub) {
    var out = [];
    sub.groups.forEach(function (g) { g.items.forEach(function (it) { out.push(it); }); });
    return out;
  }
  function subjectProgress(sub) {
    var items = allItems(sub), done = 0;
    var p = progress()[sub.id] || {};
    items.forEach(function (it) { if (p[it.id]) done++; });
    return { done: done, total: items.length };
  }
  function relTime(ts) {
    var d = Date.now() - ts;
    if (d < 90e3) return "just now";
    if (d < 36e5) return Math.round(d / 6e4) + " min ago";
    if (d < 864e5) return Math.round(d / 36e5) + " h ago";
    return Math.round(d / 864e5) + " d ago";
  }

  /* ------------------------------------------------------------- theme */
  var themeBtn = $("#theme-toggle");
  var ICONS = {
    moon: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M20.4 14.2A8.5 8.5 0 0 1 9.8 3.6a8.5 8.5 0 1 0 10.6 10.6Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    sun: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="4.4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2.8v2.4M12 18.8v2.4M21.2 12h-2.4M5.2 12H2.8M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7M18.5 18.5l-1.7-1.7M7.2 7.2 5.5 5.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  };

  function currentTheme() {
    var t = store(LS_THEME, null);
    if (t === "light" || t === "dark") return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    // The AI guide has its own built-in dark theme — keep it in sync.
    $all(".src-ai").forEach(function (el) { el.setAttribute("data-theme", t); });
    if (themeBtn) {
      themeBtn.innerHTML = t === "dark" ? ICONS.sun : ICONS.moon;
      themeBtn.setAttribute("aria-label", t === "dark" ? "Switch to light mode" : "Switch to dark mode");
    }
    save(LS_THEME, t);
  }
  if (themeBtn) {
    applyTheme(currentTheme());
    themeBtn.addEventListener("click", function () {
      applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
    if (window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
        if (store(LS_THEME, null) === null) applyTheme(e.matches ? "dark" : "light");
      });
    }
  } else {
    applyTheme(currentTheme());
  }

  /* ------------------------------------------------------- mobile drawer */
  var navToggle = $("#nav-toggle"), sidebar = $("#sidebar"), scrim = $("#scrim");
  function setDrawer(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("open", open);
    if (scrim) scrim.hidden = !open;
    if (navToggle) navToggle.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (navToggle && sidebar) {
    navToggle.addEventListener("click", function () { setDrawer(!sidebar.classList.contains("open")); });
    if (scrim) scrim.addEventListener("click", function () { setDrawer(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setDrawer(false); });
  }

  /* ------------------------------------------------------------- search */
  var input = $("#search-input"), box = $("#search-results");

  function snippetFor(entry, terms) {
    var txt = entry.txt || "";
    var idx = -1;
    for (var i = 0; i < terms.length; i++) {
      idx = txt.indexOf(terms[i]);
      if (idx !== -1) break;
    }
    var start, end;
    if (idx === -1) { start = 0; end = 160; }
    else {
      start = Math.max(0, idx - 60);
      end = Math.min(txt.length, idx + 110);
    }
    var snip = (start > 0 ? "…" : "") + txt.slice(start, end).trim() + (end < txt.length ? "…" : "");
    snip = esc(snip);
    terms.forEach(function (t) {
      if (!t) return;
      var safe = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      snip = snip.replace(new RegExp(safe, "gi"), function (m) { return "<mark>" + m + "</mark>"; });
    });
    return snip;
  }

  function runSearch(query) {
    var q = query.trim().toLowerCase();
    if (!q) return [];
    var terms = q.split(/\s+/).filter(Boolean);
    if (!terms.length || q.length < 2) return [];
    var scored = [];
    for (var i = 0; i < SEARCH.length; i++) {
      var e = SEARCH[i];
      var score = 0, ok = true;
      for (var t = 0; t < terms.length; t++) {
        var term = terms[t];
        if (e.t.toLowerCase().indexOf(term) !== -1) score += 3;
        if (e.txt.indexOf(term) !== -1) score += 1;
        if (score === 0 && e.t.toLowerCase().indexOf(term) === -1 && e.txt.indexOf(term) === -1) { ok = false; break; }
      }
      if (ok) scored.push({ e: e, score: score });
    }
    scored.sort(function (a, b) { return b.score - a.score || a.e.t.length - b.e.t.length; });
    return scored.slice(0, 12).map(function (x) { return x.e; });
  }

  function resultUrl(entry, query) {
    var sub = subjectById(entry.s);
    if (!sub) return "#";
    var base = document.body.classList.contains("page-subject") ? "../" + sub.url : sub.url;
    // query MUST come before the hash, or location.search will be empty
    return base + "?q=" + encodeURIComponent(query.trim()) + "#" + entry.a;
  }

  var activeIdx = -1, currentResults = [];

  function renderResults(query) {
    if (!box) return;
    currentResults = runSearch(query);
    activeIdx = -1;
    if (!query.trim()) { box.hidden = true; box.innerHTML = ""; return; }
    var html = '<div class="search-hint">' + currentResults.length +
      " result" + (currentResults.length === 1 ? "" : "s") + " · Enter ↵ opens · Esc closes</div>";
    if (!currentResults.length) {
      html += '<div class="res-empty">Nothing found for “' + esc(query) + '” — try a shorter keyword.</div>';
    } else {
      currentResults.forEach(function (entry, i) {
        var sub = subjectById(entry.s) || { code: entry.s, color: "#888" };
        html += '<a class="res-item" data-i="' + i + '" href="' + esc(resultUrl(entry, query)) + '">' +
          '<span class="res-sub"><span class="res-dot" style="background:' + sub.color + '"></span>' +
          esc(sub.code) + " · " + esc(entry.g) + "</span>" +
          '<span class="res-title">' + esc(entry.t) + "</span>" +
          '<span class="res-snip">' + snippetFor(entry, query.trim().toLowerCase().split(/\s+/)) + "</span>" +
          "</a>";
      });
    }
    box.innerHTML = html;
    box.hidden = false;
  }

  function moveActive(delta) {
    if (!currentResults.length) return;
    activeIdx = (activeIdx + delta + currentResults.length) % currentResults.length;
    $all(".res-item", box).forEach(function (el, i) {
      el.classList.toggle("active", i === activeIdx);
    });
    var act = $(".res-item.active", box);
    if (act && act.scrollIntoView) act.scrollIntoView({ block: "nearest" });
  }

  if (input && box) {
    var debounce;
    input.addEventListener("input", function () {
      clearTimeout(debounce);
      debounce = setTimeout(function () { renderResults(input.value); }, 120);
    });
    input.addEventListener("focus", function () { if (input.value) renderResults(input.value); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); moveActive(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveActive(-1); }
      else if (e.key === "Enter") {
        var pick = activeIdx >= 0 ? currentResults[activeIdx] : currentResults[0];
        if (pick) location.href = resultUrl(pick, input.value);
      } else if (e.key === "Escape") { box.hidden = true; input.blur(); }
    });
    box.addEventListener("mousedown", function (e) {
      var item = e.target.closest ? e.target.closest(".res-item") : null;
      if (!item) return;
      e.preventDefault();
      location.href = item.getAttribute("href");
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest || !e.target.closest(".topbar-search")) box.hidden = true;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== input &&
          !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
        e.preventDefault();
        input.focus();
      }
    });
  }

  /* ------------------------------------- highlight the match inside page */
  function highlightInPage(query) {
    var scope = $(".src");
    if (!scope || !query || query.length < 3) return;
    var q = query.toLowerCase();
    var walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var p = node.parentElement;
        while (p && p !== scope) {
          if (p.nodeName.toLowerCase() === "svg" || p.nodeName.toLowerCase() === "script" ||
              p.nodeName.toLowerCase() === "style") return NodeFilter.FILTER_REJECT;
          p = p.parentElement;
        }
        return node.nodeValue.toLowerCase().indexOf(q) !== -1
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var node, found = null, count = 0;
    while ((node = walker.nextNode()) && count < 4000) {
      count++;
      var idx = node.nodeValue.toLowerCase().indexOf(q);
      if (idx === -1) continue;
      found = { node: node, idx: idx, len: query.length };
      break;
    }
    if (!found) return;
    var mark = document.createElement("mark");
    mark.className = "found";
    var text = found.node.nodeValue;
    var after = found.node.splitText(found.idx);       // [match…rest]
    after.splitText(found.len);                        // [match][rest]
    after.parentNode.replaceChild(mark, after);
    mark.textContent = text.slice(found.idx, found.idx + found.len);
    try { mark.scrollIntoView({ block: "center", behavior: "smooth" }); }
    catch (e) { mark.scrollIntoView(); }
    setTimeout(function () {
      var parent = mark.parentNode;
      if (!parent) return;
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      parent.normalize();
    }, 6000);
  }

  /* -------------------------------------------------------- dashboard */
  function renderDashboard() {
    var grid = $("#subject-grid"), stats = $("#dash-stats"), cc = $("#continue-card");
    if (!grid) return;

    var totalSections = 0, totalDone = 0;
    DATA.subjects.forEach(function (sub) {
      var p = subjectProgress(sub);
      totalSections += p.total; totalDone += p.done;
    });
    if (stats) {
      stats.innerHTML =
        '<span class="stat"><b>' + DATA.subjects.length + "</b> subjects</span>" +
        '<span class="stat"><b>' + totalSections + "</b> sections</span>" +
        '<span class="stat"><b>' + totalDone + " / " + totalSections + '</b> marked reviewed</span>' +
        (DATA.updated ? '<span class="stat">last rebuilt ' + esc(DATA.updated) + "</span>" : "");
    }

    grid.innerHTML = DATA.subjects.map(function (sub) {
      var p = subjectProgress(sub);
      var pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
      var chaps = sub.groups.length > 1 ? sub.groups[0].items.length : p.total;
      return '<a class="card" style="--sc:' + sub.color + '" href="' + esc(sub.url) + '">' +
        '<div class="card-top"><div class="mono">' + esc(sub.monogram) + "</div>" +
        '<div class="card-titleblock"><span class="card-code">' + esc(sub.code) + "</span>" +
        "<h2>" + esc(sub.title) + "</h2></div></div>" +
        '<p class="blurb">' + esc(sub.blurb) + "</p>" +
        '<div class="card-meta"><span class="m">' + chaps + " " +
        (sub.groups[0] && sub.groups[0].name === "Topics" ? "topics" : "chapters") +
        '</span><span class="m">' + p.total + ' sections</span></div>' +
        '<div class="card-progress"><div class="bar"><span style="width:' + pct + '%"></span></div>' +
        "<em><span>Reviewed</span><b>" + p.done + " / " + p.total + "</b></em></div>" +
        '<div class="card-open"><span>Open guide</span><span class="arrow">→</span></div>' +
        "</a>";
    }).join("");

    // Continue where you left off
    if (cc) {
      var visit = store(LS_VISIT, null);
      var sub = visit && subjectById(visit.subject);
      if (visit && sub) {
        var chapTitle = visit.anchor ? chapterTitle(sub, visit.anchor) : null;
        cc.hidden = false;
        cc.innerHTML =
          '<span class="cc-dot" style="background:' + sub.color + '"></span>' +
          '<span class="cc-text">Pick up where you left off — <b>' + esc(sub.title) + "</b>" +
          (chapTitle ? ' · ' + esc(chapTitle) : "") +
          ' <span>· ' + relTime(visit.ts) + "</span></span>" +
          '<a class="cc-open" href="' + esc(sub.url) + (visit.anchor ? "#" + visit.anchor : "") + '">Continue →</a>' +
          '<button class="cc-clear" type="button">clear</button>';
        $(".cc-clear", cc).addEventListener("click", function () {
          try { localStorage.removeItem(LS_VISIT); } catch (e) { /* noop */ }
          cc.hidden = true;
        });
      } else {
        cc.hidden = true;
      }
    }
  }

  function chapterTitle(sub, id) {
    for (var i = 0; i < sub.groups.length; i++)
      for (var j = 0; j < sub.groups[i].items.length; j++)
        if (sub.groups[i].items[j].id === id) return sub.groups[i].items[j].title;
    return null;
  }

  /* -------------------------------------------------------- subject page */
  function renderSubjectPage(subjectId) {
    var sub = subjectById(subjectId);
    var chapNav = $("#side-chapters"), others = $("#side-others");
    var p = sub ? subjectProgress(sub) : { done: 0, total: 0 };

    if (chapNav) {
      if (!sub) {
        chapNav.innerHTML = '<div class="res-empty">Subject not found in site-data.js — run build.py.</div>';
      } else {
        var storeMap = progress()[sub.id] || {};
        var html = "";
        sub.groups.forEach(function (g) {
          html += '<div class="grp-label">' + esc(g.name) + "</div>";
          g.items.forEach(function (it) {
            var done = !!storeMap[it.id];
            html += '<div class="chap' + (done ? " done" : "") + '" data-chap="' + it.id + '">' +
              '<input type="checkbox" id="chk-' + it.id + '" data-chap="' + it.id + '"' +
              (done ? " checked" : "") + ' aria-label="Mark ' + esc(it.title) + ' as reviewed">' +
              '<a href="#' + it.id + '">' + esc(it.title) + "</a></div>";
          });
        });
        chapNav.innerHTML = html;

        // checkboxes
        $all("input[type=checkbox]", chapNav).forEach(function (chk) {
          chk.addEventListener("click", function (e) { e.stopPropagation(); });
          chk.addEventListener("change", function () {
            var all = progress();
            var map = all[sub.id] || (all[sub.id] = {});
            if (chk.checked) map[chk.dataset.chap] = true;
            else delete map[chk.dataset.chap];
            save(LS_PROGRESS, all);
            refreshSubjectUI(sub);
          });
        });

        // other subjects
        if (others) {
          others.innerHTML = DATA.subjects
            .filter(function (s) { return s.id !== sub.id; })
            .map(function (s) {
              return '<li><a href="../' + esc(s.url) + '"><span class="dot" style="background:' +
                s.color + '"></span>' + esc(s.title) + "</a></li>";
            }).join("");
        }
        refreshSubjectUI(sub);

        // scrollspy
        var links = {};
        $all(".chap", chapNav).forEach(function (el) { links[el.dataset.chap] = el; });
        var anchors = Object.keys(links).map(function (id) { return document.getElementById(id); })
          .filter(Boolean);
        var spyTick = false;
        function spy() {
          spyTick = false;
          var pos = window.scrollY + window.innerHeight * 0.32;
          var current = null;
          anchors.forEach(function (a) {
            var top = a.getBoundingClientRect().top + window.scrollY;
            if (top <= pos) current = a.id;
          });
          if (!current && anchors.length) current = anchors[0].id;
          $all(".chap.active", chapNav).forEach(function (el) { el.classList.remove("active"); });
          if (current && links[current]) links[current].classList.add("active");
        }
        window.addEventListener("scroll", function () {
          if (!spyTick) { spyTick = true; window.requestAnimationFrame(spy); }
        }, { passive: true });
        spy();
      }
    }

    // mark-all button
    var markAll = $("#mark-all");
    if (markAll && sub) {
      markAll.addEventListener("click", function () {
        var all = progress();
        var map = all[sub.id] || (all[sub.id] = {});
        var allDone = allItems(sub).every(function (it) { return map[it.id]; });
        allItems(sub).forEach(function (it) {
          if (allDone) delete map[it.id]; else map[it.id] = true;
        });
        save(LS_PROGRESS, all);
        refreshSubjectUI(sub);
      });
    }
  }

  function refreshSubjectUI(sub) {
    var p = subjectProgress(sub);
    var bar = $("#prog-bar"), label = $("#prog-label"), markAll = $("#mark-all");
    if (bar) bar.style.width = (p.total ? Math.round((p.done / p.total) * 100) : 0) + "%";
    if (label) label.textContent = p.done + " of " + p.total + " reviewed";
    var map = progress()[sub.id] || {};
    $all("#side-chapters .chap").forEach(function (el) {
      var done = !!map[el.dataset.chap];
      el.classList.toggle("done", done);
      var chk = $("input", el);
      if (chk) chk.checked = done;
    });
    if (markAll) {
      var allDone = p.total > 0 && p.done === p.total;
      markAll.classList.toggle("on", allDone);
      markAll.textContent = allDone ? "✓ all reviewed" : "✓ mark all";
    }
  }

  function trackVisit(subjectId) {
    var sub = subjectById(subjectId);
    if (!sub) return;
    var hash = location.hash.replace(/^#/, "").split("?")[0];
    save(LS_VISIT, {
      subject: subjectId,
      anchor: chapterTitle(sub, hash) ? hash : null,
      ts: Date.now()
    });
  }

  /* ------------------------------------------------------------- boot */
  function boot() {
    if (document.body.classList.contains("page-subject")) {
      var sid = document.body.dataset.subject;
      renderSubjectPage(sid);
      trackVisit(sid);
      window.addEventListener("hashchange", function () { trackVisit(sid); });
      // ?q= deep-link: jump straight to the matching passage
      var params = new URLSearchParams(location.search);
      var q = params.get("q");
      if (q) setTimeout(function () { highlightInPage(q); }, 350);
    } else {
      renderDashboard();
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
