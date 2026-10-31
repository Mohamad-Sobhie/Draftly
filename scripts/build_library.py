#!/usr/bin/env python3
"""Build library.html from references/INDEX.md (plus drafts/ and the thesis brief).

The page is a single self-contained file: no server, no CDN, works offline.
Prints one line of JSON with counts for Claude to read.

Usage: build_library.py [--root DIR] [--out FILE]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

STATUSES = ["unread", "skimmed", "notes taken", "cited in draft", "not used"]
MARKER_RE = re.compile(r"\[(CITATION NEEDED|PINPOINT NEEDED)(?::\s*([^\]]*))?\]")
SECTION_RE = re.compile(r"(?<![\d.])(\d{1,2}(?:\.\d{1,2}){0,3})(?![\d.]*\d)")


def strip_noise(md: str) -> str:
    """Remove fenced code blocks and HTML comments (the INDEX template lives there)."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"^```.*?^```[ \t]*$", "", md, flags=re.S | re.M)
    return md


def parse_index(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries, cur = [], None
    for line in strip_noise(path.read_text(encoding="utf-8")).splitlines():
        m = re.match(r"^##\s+(\S.*?)\s*$", line)
        if m:
            cur = {"id": m.group(1).strip("` "), "fields": {}}
            entries.append(cur)
            continue
        if line.startswith("# "):
            cur = None
            continue
        m = re.match(r"^\s*[-*]\s*([A-Za-z/ ]+?)\s*:\s*(.*)$", line)
        if cur is not None and m:
            key = m.group(1).strip().lower()
            cur["fields"][key] = m.group(2).strip()
        elif cur is not None and line.strip() and cur["fields"]:
            last = list(cur["fields"])[-1]  # wrapped continuation line
            cur["fields"][last] += " " + line.strip()
    return entries


def sections_of(text: str) -> list[str]:
    text = re.sub(r"\([^)]*\)", " ", text)            # drop "(pp. 12-15)"
    text = re.sub(r"\b(pp?|paras?|ss?|ch|chs)\.?\s*[\d\-–, ]+", " ", text, flags=re.I)
    return sorted(set(SECTION_RE.findall(text)), key=lambda s: [int(x) for x in s.split(".")])


def to_source(e: dict, root: Path) -> dict:
    f = e["fields"]
    status = (f.get("status") or "unread").lower().strip()
    tags = [t.strip() for t in re.split(r"[,;]", f.get("jurisdiction/tags", f.get("tags", ""))) if t.strip()]
    files = f.get("files", "")
    pdf = ""
    m = re.search(r"pdf/([^,\s]+)", files)
    if m:
        cand = root / "references" / "pdf" / m.group(1)
        pdf = f"references/pdf/{m.group(1)}"
        pdf_exists = cand.exists()
    else:
        pdf_exists = False
    return {
        "id": e["id"],
        "citation": f.get("citation", ""),
        "type": (f.get("type") or "").lower().strip(),
        "tags": tags,
        "about": f.get("about", ""),
        "concepts": f.get("key concepts", ""),
        "relevant": f.get("relevant for", ""),
        "sections": sections_of(f.get("relevant for", "")),
        "status": status,
        "pdf": pdf,
        "pdf_exists": pdf_exists,
        "has_text": (root / "references" / "text" / e["id"]).is_dir(),
    }


def parse_outline(brief: Path) -> list[dict]:
    if not brief.exists():
        return []
    text = re.sub(r"<!--.*?-->", "", brief.read_text(encoding="utf-8"), flags=re.S)
    m = re.search(r"^##\s+Outline\s*$(.*?)(?=^##\s|\Z)", text, flags=re.S | re.M)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        mm = re.match(r"^\s*(?:[-*]\s*)?(?:Chapter\s+)?(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(.+?)\s*$", line, re.I)
        if not mm:
            continue
        # "3.1 Title · 1,500 words · RQ1, RQ2 · purpose"
        parts = [x.strip() for x in re.split(r"\s+[\u00b7|]\s+", mm.group(2))]
        item = {"num": mm.group(1), "title": parts[0], "words": None, "rqs": [], "purpose": ""}
        for part in parts[1:]:
            w = re.match(r"^~?([\d,]+)\s*words?$", part, re.I)
            if w:
                item["words"] = int(w.group(1).replace(",", ""))
            elif re.match(r"^RQ\s*\d", part, re.I):
                item["rqs"] = [f"RQ{n}" for n in re.findall(r"RQ\s*(\d+)", part, re.I)]
            else:
                item["purpose"] = part
        out.append(item)
    return out


def parse_brief_numbers(brief: Path) -> tuple[int | None, int]:
    """Word limit and number of research questions from the thesis brief."""
    if not brief.exists():
        return None, 0
    text = brief.read_text(encoding="utf-8")
    limit = None
    m = re.search(r"Word limit[^:]*:\s*([^\n]*)", text, re.I)
    if m:
        nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", m.group(1)) if int(n.replace(",", "")) >= 1000]
        limit = nums[0] if nums else None
    rq = 0
    m = re.search(r"Research question\(?s?\)?:[^\n]*\n((?:[ \t]+\S[^\n]*\n?)*)", text, re.I)
    if m:
        rq = len(re.findall(r"^[ \t]+(?:RQ)?\d+[.):]\s*\S", m.group(1), re.M | re.I))
    return limit, rq


def parse_bibliography(root: Path, brief: Path) -> list[str]:
    lines = []
    bib = root / "references" / "bibliography.md"
    if bib.exists():
        lines += bib.read_text(encoding="utf-8").splitlines()
    if brief.exists():
        text = re.sub(r"<!--.*?-->", "", brief.read_text(encoding="utf-8"), flags=re.S)
        m = re.search(r"^##\s+Bibliography\s*$(.*?)(?=^##\s|\Z)", text, flags=re.S | re.M)
        if m:
            lines += m.group(1).splitlines()
    return [re.sub(r"^\s*[-*]\s+", "", ln).strip() for ln in lines if re.match(r"^\s*[-*]\s+\S", ln)]


def scan_drafts(drafts: Path) -> list[dict]:
    out = []
    if not drafts.is_dir():
        return out
    for p in sorted(drafts.rglob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        marks = MARKER_RE.findall(text)
        out.append({
            "file": p.relative_to(drafts).as_posix(),
            "citation_needed": sum(1 for k, _ in marks if k == "CITATION NEEDED"),
            "pinpoint_needed": sum(1 for k, _ in marks if k == "PINPOINT NEEDED"),
            "kinds": [d.strip() for k, d in marks if k == "CITATION NEEDED" and d.strip()][:12],
            "words": len(re.sub(r"\[\^?\d+\]:?", "", text).split()),
        })
    return out


def covered(num: str, sources: list[dict]) -> int:
    n = 0
    for s in sources:
        if s["status"] == "not used":
            continue
        if any(sec == num or sec.startswith(num + ".") for sec in s["sections"]):
            n += 1
    return n


def build(root: Path, out: Path) -> dict:
    brief = root / "thesis-brief.md"
    sources = [to_source(e, root) for e in parse_index(root / "references" / "INDEX.md")]
    ids = {s["id"] for s in sources}
    outline = parse_outline(brief)
    for sec in outline:
        sec["sources"] = covered(sec["num"], sources)
    drafts = scan_drafts(root / "drafts")
    bib = parse_bibliography(root, brief)
    bib_missing = []
    for entry in bib:
        m = re.search(r"\{#([a-z0-9\-]+)\}", entry)
        src = next((s for s in sources if m and s["id"] == m.group(1)), None)
        if not src or not src["pdf_exists"]:
            bib_missing.append(re.sub(r"\s*\{#[^}]*\}", "", entry))

    title = ""
    if brief.exists():
        m = re.search(r"Working title:\s*(.+)", brief.read_text(encoding="utf-8"))
        title = m.group(1).strip() if m else ""

    data = {
        "generated": dt.datetime.now().strftime("%d %b %Y, %H:%M"),
        "title": title,
        "sources": sources,
        "statuses": STATUSES,
        "outline": outline,
        "drafts": drafts,
        "bib_total": len(bib),
        "bib_missing": bib_missing,
        "unknown_bib_ids": sorted({m for e in bib for m in re.findall(r"\{#([a-z0-9\-]+)\}", e)} - ids),
    }
    out.write_text(render(data), encoding="utf-8")

    by_status: dict[str, int] = {}
    for s in sources:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1
    return {
        "ok": True,
        "output": out.name,
        "sources": len(sources),
        "by_status": by_status,
        "citation_needed": sum(d["citation_needed"] for d in drafts),
        "pinpoint_needed": sum(d["pinpoint_needed"] for d in drafts),
        "drafts": len(drafts),
        "sections_without_sources": [s["num"] for s in outline if not s["sources"]],
        **outline_checks(outline, brief),
        "maybe": [s["id"] for s in sources if any(t.lower() == "maybe" for t in s["tags"])],
        "bibliography_without_pdf": len(bib_missing),
    }


def outline_checks(outline: list[dict], brief: Path) -> dict:
    if not outline:
        return {}
    limit, n_rq = parse_brief_numbers(brief)
    chapters = [s for s in outline if "." not in s["num"]]
    budgeted = [s for s in chapters if s["words"]] or [s for s in outline if s["words"]]
    total = sum(s["words"] for s in budgeted) if budgeted else None
    used = {r for s in outline for r in s["rqs"]}
    res = {"outline_sections": len(outline), "outline_words": total, "word_limit": limit}
    if total and limit:
        res["outline_vs_limit"] = total - limit
    if n_rq:
        res["research_questions_without_section"] = [f"RQ{i}" for i in range(1, n_rq + 1) if f"RQ{i}" not in used]
    for ch in chapters:  # sections that add up to more than their chapter's budget
        subs = [s["words"] or 0 for s in outline if s["num"].startswith(ch["num"] + ".") and s["num"].count(".") == 1]
        if ch["words"] and subs and sum(subs) > ch["words"]:
            res.setdefault("chapters_over_budget", []).append(ch["num"])
    return res


def render(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page_title = "Thesis library" + (f" - {html.escape(data['title'])}" if data["title"] else "")
    return TEMPLATE.replace("__TITLE__", page_title).replace("__DATA__", payload)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --bg:#fbfaf7;--surface:#ffffff;--text:#1d1f23;--muted:#5f6670;--line:#e4e1da;--accent:#2f5d8a;
  --chip:#f1efe9;--warn:#9a5b00;--warn-bg:#fff4e0;
  --s-unread:#8a8f98;--s-skimmed:#2f6fb0;--s-notes:#6a4fb3;--s-cited:#2e7d4f;--s-notused:#b0b4ba;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#15171a;--surface:#1d2024;--text:#e7e8ea;--muted:#a1a7b0;--line:#30343a;--accent:#7fb0e0;
    --chip:#272b30;--warn:#f0b35a;--warn-bg:#3a2c14;
    --s-unread:#8a8f98;--s-skimmed:#5b9ad8;--s-notes:#9b84e0;--s-cited:#58b882;--s-notused:#5d636b;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --bg:#15171a;--surface:#1d2024;--text:#e7e8ea;--muted:#a1a7b0;--line:#30343a;--accent:#7fb0e0;
  --chip:#272b30;--warn:#f0b35a;--warn-bg:#3a2c14;
  --s-unread:#8a8f98;--s-skimmed:#5b9ad8;--s-notes:#9b84e0;--s-cited:#58b882;--s-notused:#5d636b;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font:16px/1.55 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
.ui{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 60px}
header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px 16px;margin-bottom:20px}
h1{font-size:1.8rem;margin:0;font-weight:600;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:.9rem}
button.theme{background:var(--chip);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:.85rem}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:18px}
.gaps{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.gap h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 6px;font-weight:600}
.gap .big{font-size:1.6rem;font-weight:600;line-height:1.1}
.gap ul{margin:6px 0 0;padding-left:18px;font-size:.88rem}
.gap li{margin:2px 0}
.ok{color:var(--s-cited)}
.warn{color:var(--warn)}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:12px}
.controls input,.controls select{font:inherit;font-size:.9rem;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--text)}
.controls input{flex:1 1 260px;min-width:0}
.controls select{flex:0 1 auto;max-width:100%}
.count{color:var(--muted);font-size:.85rem;margin-left:auto}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;min-width:760px}
th,td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--line)}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600;background:var(--surface);position:sticky;top:0}
tr:last-child td{border-bottom:none}
td.cit{min-width:320px}
.id{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.78rem;color:var(--muted)}
.about{font-size:.86rem;color:var(--muted);margin-top:4px}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:1px 9px;margin:2px 4px 2px 0;font-size:.78rem;white-space:nowrap}
.chip.maybe{background:var(--warn-bg);color:var(--warn)}
.badge{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.78rem;font-weight:600;color:#fff;white-space:nowrap}
.b-unread{background:var(--s-unread)}.b-skimmed{background:var(--s-skimmed)}.b-notes-taken{background:var(--s-notes)}
.b-cited-in-draft{background:var(--s-cited)}.b-not-used{background:var(--s-notused);color:var(--text)}
a{color:var(--accent)}
.empty{padding:28px;text-align:center;color:var(--muted)}
.missing{color:var(--muted);font-size:.8rem}
footer{margin-top:26px;color:var(--muted);font-size:.82rem}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1 id="title">Thesis library</h1>
      <div class="sub ui" id="subtitle"></div>
    </div>
    <button class="theme ui" id="theme" type="button" aria-label="Switch light or dark mode">Light / dark</button>
  </header>

  <section class="panel ui" aria-label="Gaps">
    <div class="gaps" id="gaps"></div>
    <div class="stats" id="stats"></div>
  </section>

  <div class="controls ui">
    <input id="q" type="search" placeholder="Search citation, topic, concept..." aria-label="Search">
    <select id="f-status" aria-label="Filter by status"><option value="">All statuses</option></select>
    <select id="f-type" aria-label="Filter by type"><option value="">All types</option></select>
    <select id="f-tag" aria-label="Filter by tag"><option value="">All tags</option></select>
    <select id="f-section" aria-label="Filter by thesis section"><option value="">All sections</option></select>
    <span class="count" id="count"></span>
  </div>

  <div class="tablewrap">
    <table class="ui">
      <thead><tr><th>Source</th><th>Type</th><th>Jurisdiction / tags</th><th>Relevant for</th><th>Status</th><th>File</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="empty ui" id="empty" hidden>No sources match.</div>
  </div>
  <footer class="ui">Refresh this tab after Claude updates your library. Generated <span id="gen"></span>.</footer>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
(function(){
  var D = JSON.parse(document.getElementById('data').textContent);
  var $ = function(id){ return document.getElementById(id); };
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function slug(s){ return String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-'); }
  function cmpSec(a,b){ var x=a.split('.').map(Number), y=b.split('.').map(Number);
    for (var i=0;i<Math.max(x.length,y.length);i++){ var d=(x[i]||0)-(y[i]||0); if(d) return d; } return 0; }

  // theme toggle (remembered per browser when storage is available)
  var root = document.documentElement;
  try { var saved = localStorage.getItem('draftly-theme'); if (saved) root.setAttribute('data-theme', saved); } catch(e){}
  $('theme').addEventListener('click', function(){
    var dark = root.getAttribute('data-theme') ? root.getAttribute('data-theme') === 'dark'
             : window.matchMedia('(prefers-color-scheme: dark)').matches;
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('draftly-theme', next); } catch(e){}
  });

  if (D.title) { $('title').textContent = D.title; document.title = 'Library - ' + D.title; }
  $('subtitle').textContent = D.sources.length + (D.sources.length === 1 ? ' source' : ' sources') + ' in your library';
  $('gen').textContent = D.generated;

  // ---- gap panel
  var totalCN = 0, totalPN = 0;
  D.drafts.forEach(function(d){ totalCN += d.citation_needed; totalPN += d.pinpoint_needed; });
  var draftItems = D.drafts.filter(function(d){ return d.citation_needed || d.pinpoint_needed; })
    .map(function(d){ return '<li>' + esc(d.file.replace(/\.md$/,'')) + ': ' + d.citation_needed + ' citation, ' + d.pinpoint_needed + ' page</li>'; });
  var emptySecs = D.outline.filter(function(s){ return !s.sources; });
  var maybe = D.sources.filter(function(s){ return s.tags.some(function(t){ return t.toLowerCase() === 'maybe'; }); });
  function gap(title, big, cls, items, emptyMsg){
    return '<div class="gap"><h2>' + esc(title) + '</h2><div class="big ' + cls + '">' + big + '</div>' +
      (items.length ? '<ul>' + items.slice(0, 8).join('') + (items.length > 8 ? '<li>... and ' + (items.length - 8) + ' more</li>' : '') + '</ul>'
                    : '<div class="sub">' + esc(emptyMsg) + '</div>') + '</div>';
  }
  $('gaps').innerHTML =
    gap('Open citation markers', totalCN + totalPN, (totalCN + totalPN) ? 'warn' : 'ok', draftItems,
        D.drafts.length ? 'No open markers in your drafts.' : 'No drafts yet.') +
    gap('Sections without sources', D.outline.length ? emptySecs.length : '-', emptySecs.length ? 'warn' : 'ok',
        emptySecs.map(function(s){ return '<li>' + esc(s.num + ' ' + s.title) + '</li>'; }),
        D.outline.length ? 'Every section has at least one source.' : 'No outline in the thesis brief yet.') +
    gap('Tagged "maybe"', maybe.length, maybe.length ? 'warn' : 'ok',
        maybe.map(function(s){ return '<li>' + esc(s.id) + '</li>'; }), 'Nothing waiting for a decision.') +
    gap('Bibliography without PDF', D.bib_total ? D.bib_missing.length : '-', D.bib_missing.length ? 'warn' : 'ok',
        D.bib_missing.map(function(b){ return '<li>' + esc(b.length > 110 ? b.slice(0, 107) + '...' : b) + '</li>'; }),
        D.bib_total ? 'Every bibliography entry has a file.' : 'No bibliography added yet.');

  var counts = {};
  D.sources.forEach(function(s){ counts[s.status] = (counts[s.status] || 0) + 1; });
  $('stats').innerHTML = D.statuses.map(function(st){
    return '<span class="badge b-' + slug(st) + '">' + esc(st) + ': ' + (counts[st] || 0) + '</span>';
  }).join(' ');

  // ---- filters
  function fill(sel, values){ values.forEach(function(v){ var o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o); }); }
  var uniq = function(a){ return a.filter(function(v, i){ return v && a.indexOf(v) === i; }); };
  fill($('f-status'), uniq(D.statuses.concat(D.sources.map(function(s){ return s.status; }))));
  fill($('f-type'), uniq(D.sources.map(function(s){ return s.type; })).sort());
  var tags = []; D.sources.forEach(function(s){ s.tags.forEach(function(t){ tags.push(t); }); });
  fill($('f-tag'), uniq(tags).sort(function(a,b){ return a.localeCompare(b); }));
  var secs = D.outline.map(function(s){ return s.num; });
  D.sources.forEach(function(s){ s.sections.forEach(function(x){ secs.push(x); }); });
  secs = uniq(secs).sort(cmpSec);
  secs.forEach(function(n){
    var o = document.createElement('option'); o.value = n;
    var t = D.outline.filter(function(s){ return s.num === n; })[0];
    o.textContent = n + (t ? ' ' + t.title : ''); $('f-section').appendChild(o);
  });

  function row(s){
    var tagsHtml = s.tags.map(function(t){ return '<span class="chip' + (t.toLowerCase() === 'maybe' ? ' maybe' : '') + '">' + esc(t) + '</span>'; }).join('');
    var file = s.pdf ? (s.pdf_exists ? '<a href="' + esc(encodeURI(s.pdf)) + '" target="_blank" rel="noopener">Open</a>'
                                     : '<span class="missing">file missing</span>')
                     : '<span class="missing">none</span>';
    return '<tr><td class="cit"><div>' + esc(s.citation || s.id) + '</div><div class="id">' + esc(s.id) + '</div>' +
      (s.about ? '<div class="about">' + esc(s.about) + '</div>' : '') + '</td>' +
      '<td>' + esc(s.type) + '</td><td>' + tagsHtml + '</td><td>' + esc(s.relevant) + '</td>' +
      '<td><span class="badge b-' + slug(s.status) + '">' + esc(s.status) + '</span></td><td>' + file + '</td></tr>';
  }

  function apply(){
    var q = $('q').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var st = $('f-status').value, ty = $('f-type').value, tg = $('f-tag').value, sc = $('f-section').value;
    var list = D.sources.filter(function(s){
      if (st && s.status !== st) return false;
      if (ty && s.type !== ty) return false;
      if (tg && s.tags.indexOf(tg) < 0) return false;
      if (sc && !s.sections.some(function(x){ return x === sc || x.indexOf(sc + '.') === 0; })) return false;
      var hay = [s.id, s.citation, s.about, s.concepts, s.relevant, s.type, s.tags.join(' ')].join(' ').toLowerCase();
      return q.every(function(w){ return hay.indexOf(w) >= 0; });
    });
    $('rows').innerHTML = list.map(row).join('');
    $('empty').hidden = list.length > 0;
    if (!D.sources.length) $('empty').textContent = 'Your library is empty. Drag a PDF into the chat and say "add it".';
    $('count').textContent = list.length + ' of ' + D.sources.length;
  }
  ['q','f-status','f-type','f-tag','f-section'].forEach(function(id){ $(id).addEventListener('input', apply); });
  apply();
})();
</script>
</body>
</html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", help="project root (default: folder above scripts/)")
    ap.add_argument("--out", help="output file (default: <root>/library.html)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    out = Path(args.out) if args.out else root / "library.html"
    try:
        result = build(root, out)
    except Exception as e:  # noqa: BLE001 - always answer in one JSON line
        result = {"ok": False, "error": "unexpected", "message": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
