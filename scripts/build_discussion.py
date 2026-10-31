#!/usr/bin/env python3
"""Render a Discuss session (JSON) as a colour-coded perspectives board (HTML).

Usage: build_discussion.py sessions/2026-10-31-discuss-nbfi.json [--root DIR]
Writes the .html next to the .json and prints one line of JSON.

Input format:
{
  "question": "Should NBFI risk be regulated through banks or directly?",
  "date": "2026-10-31",                         (optional, default today)
  "intro": "one sentence",                      (optional)
  "perspectives": [
    {"key": "practitioner",                     practitioner|skeptic|economist|historian|academic
                                                 or any other key with "name" and "tagline"
     "position": "core position",
     "evidence": [{"claim": "...", "source": "fsma-2023", "pinpoint": "s 25"},   library-backed
                  {"claim": "...", "needed": "Bank of England data on LDI leverage"}],  gap
     "only": "what only this perspective would say"}
  ],
  "clashes": [{"between": ["practitioner", "skeptic"], "text": "..."}],
  "thesis": "what this means for the thesis",
  "examiner": ["question 1", "question 2"],

  "fight": {                                    stage 2 - "map where they fight" (optional)
    "contradictions": [{"between": ["skeptic", "practitioner"], "text": "..."}],
    "strongest": {"key": "academic", "why": "..."},
    "weakest": {"key": "historian", "why": "..."},
    "agree": ["what every perspective accepts"],
    "blind_spots": ["what none of them addressed"]
  },
  "briefing": {                                 stage 3 - "synthesise" (optional)
    "summary": "one paragraph you could send your supervisor",
    "findings": [{"text": "...", "key": "academic", "reliability": "high|medium|low",
                  "sources": ["fsma-2023"]}],   ranked, most reliable first
    "hidden_connection": "a link that only appears across the perspectives",
    "do_differently": "one specific change to the thesis"
  },
  "review": {                                   stage 4 - "grade your own work" (optional)
    "scores": [{"finding": 1, "score": 8, "why": "..."}],   1-10, finding = number in the briefing
    "weakest_claim": {"text": "...", "why": "...", "fix": "..."},
    "bias": "which perspective dominated the synthesis, and what that hides"
  }
}

Every "source" is checked against references/INDEX.md. A source that is not in the
library is shown as a gap (amber), never as backed (green), and reported in "unknown_sources".
The review's perspective balance is computed here from the findings' "key" fields, not taken
on trust; a perspective behind 40%+ of the findings is flagged as dominant.
A finding can only be rated "high" if at least one of its sources is in the library;
otherwise it is shown as "medium" and reported in "downgraded".
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

PRESETS = {
    "practitioner": ("The Practitioner", "has done the job", "P"),
    "skeptic": ("The Skeptic", "doubts the consensus", "?"),
    "economist": ("The Economist", "follows the money", "£"),
    "historian": ("The Historian", "has seen this before", "H"),
    "academic": ("The Academic", "read the studies", "§"),
}
ORDER = list(PRESETS)
N_COLOURS = 8
RELIABILITY = {"high": 0, "medium": 1, "low": 2}


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def library_ids(root: Path) -> set[str]:
    idx = root / "references" / "INDEX.md"
    if not idx.exists():
        return set()
    text = re.sub(r"```.*?```", "", idx.read_text(encoding="utf-8"), flags=re.S)
    return {m.group(1).strip("` ") for m in re.finditer(r"^##\s+(\S+)", text, flags=re.M)}


def colour_map(perspectives: list[dict]) -> dict[str, int]:
    """Preset perspectives keep fixed colours; others take the remaining ones in order."""
    used, out = set(), {}
    for p in perspectives:
        k = p.get("key", "")
        if k in PRESETS:
            out[k] = ORDER.index(k) + 1
            used.add(out[k])
    free = [i for i in range(1, N_COLOURS + 1) if i not in used]
    for p in perspectives:
        k = p.get("key", "")
        if k not in out:
            out[k] = free.pop(0) if free else 1
    return out


def chip(key: str, names: dict, colours: dict) -> str:
    if key not in colours:
        return ""
    return f'<span class="chip p{colours[key]}">{esc(names[key].replace("The ", ""))}</span>'


def clash_rows(items: list, names: dict, colours: dict) -> str:
    rows = []
    for c in items or []:
        pair = [k for k in (c.get("between") or []) if k in colours][:3]
        dots = "".join(f'<span class="dot p{colours[k]}"></span>' for k in pair)
        label = " vs ".join(esc(names[k].replace("The ", "")) for k in pair)
        rows.append(f'<div class="row"><div class="pair">{dots}</div><p>'
                    + (f"<b>{label}:</b> " if label else "") + f'{esc(c.get("text"))}</p></div>')
    return "".join(rows)


def render_briefing(b: dict, names: dict, colours: dict, ids: set[str], downgraded: list,
                    review: dict | None = None) -> str:
    scores = {}
    for sc in (review or {}).get("scores") or []:
        try:
            scores[int(sc.get("finding"))] = (max(1, min(10, int(sc.get("score")))), sc.get("why", ""))
        except (TypeError, ValueError):
            continue
    findings = []
    for n, f in enumerate(b.get("findings") or [], start=1):
        f = dict(f, _n=n)
        rel = (f.get("reliability") or "low").lower()
        rel = rel if rel in RELIABILITY else "low"
        if rel == "high" and not any(s in ids for s in f.get("sources") or []):
            rel = "medium"
            downgraded.append(f.get("text", "")[:60])
        findings.append((RELIABILITY[rel], rel, f))
    findings.sort(key=lambda t: t[0])  # stable: keeps the author's order within a level
    def score_html(n: int) -> str:
        if n not in scores:
            return ""
        val, why = scores[n]
        return (f'<div class="score" title="{esc(why)}"><div class="bar"><i style="width:{val * 10}%"></i></div>'
                f'<span>{val}/10</span></div>' + (f'<div class="why">{esc(why)}</div>' if why else ""))
    rows = "".join(
        f'<div class="finding"><div class="num">{i}</div><div class="ftext"><p>{esc(f.get("text"))}</p>'
        f'{chip(f.get("key", ""), names, colours)}{score_html(f["_n"])}</div>'
        f'<div class="rel r-{rel}">{rel.title()}</div></div>'
        for i, (_, rel, f) in enumerate(findings, start=1))
    out = '<section class="briefing"><div class="sec"><span>Research briefing</span></div>'
    if b.get("summary"):
        out += f'<div class="label plain">Supervisor summary</div><div class="box"><p>{esc(b["summary"])}</p></div>'
    if rows:
        out += f'<div class="label plain">Key findings · ranked by reliability</div><div class="box findings">{rows}</div>'
    if b.get("hidden_connection"):
        out += (f'<div class="callout hidden"><div class="label plain">Hidden connection</div>'
                f'<p>{esc(b["hidden_connection"])}</p></div>')
    if b.get("do_differently"):
        out += (f'<div class="callout act"><div class="label plain">One thing to change in your thesis</div>'
                f'<p>{esc(b["do_differently"])}</p></div>')
    return out + "</section>"


def render_review(r: dict, findings: list, names: dict, colours: dict) -> tuple[str, str | None]:
    counts: dict[str, int] = {}
    for f in findings:
        k = f.get("key", "")
        if k in colours:
            counts[k] = counts.get(k, 0) + 1
    total = sum(counts.values())
    dominant = None
    if total >= 3:
        top = max(counts, key=counts.get)
        if counts[top] / total >= 0.4:
            dominant = top
    out = '<section class="review"><div class="sec"><span>Peer review</span></div>'
    w = r.get("weakest_claim") or {}
    if w:
        out += ('<div class="callout weak"><div class="label plain">Weakest claim</div>'
                f'<p><b>{esc(w.get("text"))}</b></p>'
                + (f'<p class="muted">Why: {esc(w["why"])}</p>' if w.get("why") else "")
                + (f'<p class="muted">How to fix: {esc(w["fix"])}</p>' if w.get("fix") else "") + "</div>")
    if total:
        segs = "".join(f'<i class="p{colours[k]}" style="flex:{n}" title="{esc(names[k])}: {n}"></i>'
                       for k, n in sorted(counts.items(), key=lambda t: -t[1]))
        keys = "".join(f'<span class="chip p{colours[k]}">{esc(names[k].replace("The ", ""))} · {n}</span> '
                       for k, n in sorted(counts.items(), key=lambda t: -t[1]))
        missing = [names[k].replace("The ", "") for k in names if k not in counts]
        flag = (f'<p class="flag">⚠ {esc(names[dominant].replace("The ", ""))} drives '
                f'{counts[dominant]} of {total} findings - the synthesis leans that way.</p>') if dominant else                '<p class="muted">No single perspective dominates the findings.</p>'
        out += ('<div class="box bias"><div class="label plain">Bias check · whose voice shaped the findings</div>'
                f'<div class="balance">{segs}</div><div>{keys}</div>{flag}'
                + (f'<p class="muted">Not represented in any finding: {esc(", ".join(missing))}.</p>' if missing else "")
                + (f'<p>{esc(r["bias"])}</p>' if r.get("bias") else "") + "</div>")
    return out + "</section>", dominant


def render_fight(f: dict, fallback_clashes: list, names: dict, colours: dict) -> str:
    out = '<h2>Where they fight</h2>'
    rows = clash_rows(f.get("contradictions") or fallback_clashes, names, colours)
    if rows:
        out += f'<div class="label plain">Direct contradictions</div><div class="clash">{rows}</div>'
    tiles = ""
    for slot, title in (("strongest", "Strongest evidence"), ("weakest", "Weakest evidence")):
        t = f.get(slot) or {}
        if t:
            tiles += (f'<div class="tile t-{slot}"><div class="label plain">{title}</div>'
                      f'{chip(t.get("key", ""), names, colours)}<p>{esc(t.get("why"))}</p></div>')
    if tiles:
        out += f'<div class="tiles">{tiles}</div>'
    lists = ""
    for slot, title in (("agree", "What they all agree on"), ("blind_spots", "What nobody addressed")):
        items = "".join(f"<li>{esc(x)}</li>" for x in f.get(slot) or [])
        if items:
            lists += f'<div class="tile l-{slot}"><div class="label plain">{title}</div><ul>{items}</ul></div>'
    if lists:
        out += f'<div class="tiles">{lists}</div>'
    return out


def render(data: dict, ids: set[str]) -> tuple[str, list[str], list[str]]:
    persp = data.get("perspectives") or []
    colours = colour_map(persp)
    names = {}
    unknown: list[str] = []
    cards = []
    for p in persp:
        key = p.get("key", "")
        name, tagline, icon = PRESETS.get(key, (p.get("name") or key.title(), "", (p.get("name") or key or "?")[:1].upper()))
        name = p.get("name") or name
        tagline = p.get("tagline") or tagline
        icon = p.get("icon") or icon
        names[key] = name
        items = []
        for ev in p.get("evidence") or []:
            src = (ev.get("source") or "").strip()
            pin = (ev.get("pinpoint") or "").strip()
            if src and src in ids:
                tag = f'<span class="src ok" title="In your library">{esc(src)}{", " + esc(pin) if pin else ""}</span>'
            else:
                if src:
                    unknown.append(src)
                need = "needs: " + ev["needed"] if ev.get("needed") else "source needed"
                tag = f'<span class="src need" title="Not in your library yet">{esc(need)}</span>'
            items.append(f"<li>{esc(ev.get('claim'))} {tag}</li>")
        only = p.get("only")
        cards.append(
            f'<article class="card p{colours[key]}"><div class="head"><div class="icon">{esc(icon)}</div>'
            f'<div class="name">{esc(name)}</div><div class="tag">{esc(tagline)}</div></div>'
            f'<div class="label">Core position</div><p>{esc(p.get("position"))}</p>'
            + (f'<div class="label">Strongest evidence</div><ul>{"".join(items)}</ul>' if items else "")
            + (f'<div class="only"><div class="label">Only they\'d say</div><p>{esc(only)}</p></div>' if only else "")
            + "</article>")

    legend = "".join(f'<span class="p{colours[p.get("key", "")]}">{esc(names[p.get("key", "")].replace("The ", ""))}</span>'
                     for p in persp)
    downgraded: list[str] = []
    review = data.get("review") or None
    briefing = render_briefing(data["briefing"], names, colours, ids, downgraded, review) if data.get("briefing") else ""
    dominant = None
    if review and data.get("briefing"):
        review_html, dominant = render_review(review, data["briefing"].get("findings") or [], names, colours)
        briefing += review_html
    if data.get("fight"):
        fight = render_fight(data["fight"], data.get("clashes") or [], names, colours)
    else:
        rows = clash_rows(data.get("clashes") or [], names, colours)
        fight = f'<h2>Where they clash</h2><div class="clash">{rows}</div>' if rows else ""

    examiner = "".join(f"<li>{esc(q)}</li>" for q in data.get("examiner") or [])
    date = data.get("date") or dt.date.today().isoformat()
    try:
        d = dt.date.fromisoformat(date)
        date_h = f"{d.day} {d:%b %Y}"
    except ValueError:
        date_h = date
    body = (
        f'<div class="kicker">Discuss · {esc(date_h)}</div><h1>{esc(data.get("question") or "Perspectives")}</h1>'
        + (f'<p class="lede">{esc(data["intro"])}</p>' if data.get("intro") else "")
        + f'<div class="legend">{legend}</div>' + briefing
        + ('<h2>The perspectives</h2>' if briefing else "") + "".join(cards) + fight
        + (f'<h2>What this means for your thesis</h2><div class="box"><p>{esc(data["thesis"])}</p></div>' if data.get("thesis") else "")
        + (f'<h2>Likely examiner questions</h2><div class="box"><ol>{examiner}</ol></div>' if examiner else "")
        + '<p class="foot">Green tags are sources in your library · amber tags still need a source · '
          'no reference on this page is invented.</p>')
    title = "Perspectives - " + (data.get("question") or "")[:80]
    page = TEMPLATE.replace("__TITLE__", esc(title)).replace("__BODY__", body)
    return page, sorted(set(unknown)), downgraded, dominant


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --bg:#f6f5f2;--card:#ffffff;--text:#1f2328;--muted:#6b7079;--line:#e6e3dc;
  --ok:#2e7d4f;--okt:#e8f5ee;--need:#a86a12;--needt:#fbf2e2;
  --c1:#2f6fb0;--c1t:#eaf2fb;--c2:#c2453d;--c2t:#fcecea;--c3:#2e8a57;--c3t:#e8f5ee;--c4:#b7791f;--c4t:#fbf2e2;
  --c5:#6a4fb3;--c5t:#f0ecfa;--c6:#1f8a8a;--c6t:#e3f4f4;--c7:#b04a85;--c7t:#f8eaf2;--c8:#5a6472;--c8t:#eef0f3;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#141619;--card:#1c1f23;--text:#e6e7e9;--muted:#9aa1ab;--line:#2d3137;
    --ok:#5cc08a;--okt:#17301f;--need:#e2a94f;--needt:#35281a;
    --c1:#6aa6e3;--c1t:#1a2a3b;--c2:#ec7a72;--c2t:#3a1f1d;--c3:#5cc08a;--c3t:#17301f;--c4:#e2a94f;--c4t:#35281a;
    --c5:#a58ff0;--c5t:#272040;--c6:#5cc4c4;--c6t:#163030;--c7:#e07ab5;--c7t:#3a1d2e;--c8:#a3acb8;--c8t:#262a30;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --bg:#141619;--card:#1c1f23;--text:#e6e7e9;--muted:#9aa1ab;--line:#2d3137;
  --ok:#5cc08a;--okt:#17301f;--need:#e2a94f;--needt:#35281a;
  --c1:#6aa6e3;--c1t:#1a2a3b;--c2:#ec7a72;--c2t:#3a1f1d;--c3:#5cc08a;--c3t:#17301f;--c4:#e2a94f;--c4t:#35281a;
  --c5:#a58ff0;--c5t:#272040;--c6:#5cc4c4;--c6t:#163030;--c7:#e07ab5;--c7t:#3a1d2e;--c8:#a3acb8;--c8t:#262a30;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:32px 16px 64px}
.kicker{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
h1{font:600 1.7rem/1.25 "Iowan Old Style",Palatino,Georgia,serif;margin:6px 0 6px}
.lede{color:var(--muted);margin:0 0 22px}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 22px}
.legend span{font-size:.8rem;padding:3px 10px;border-radius:999px;background:var(--t);color:var(--a);font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--a);border-radius:12px;padding:16px 18px 18px;margin-bottom:14px}
.head{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.icon{width:30px;height:30px;border-radius:8px;background:var(--t);color:var(--a);display:grid;place-items:center;font-weight:700;font-size:.95rem;flex:none}
.name{font-weight:650;font-size:1.05rem}
.tag{margin-left:auto;font-style:italic;color:var(--muted);font-size:.85rem;text-align:right}
.label{font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--a);font-weight:700;margin:12px 0 2px;display:flex;align-items:center;gap:6px}
.label::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--a)}
p{margin:0}
ul{margin:2px 0 0;padding-left:18px}
li{margin:4px 0}
.src{display:inline-block;font-size:.75rem;padding:0 7px;border-radius:6px;margin-left:2px;line-height:1.7}
.src.ok{background:var(--okt);color:var(--ok)}
.src.need{background:var(--needt);color:var(--need)}
.only{background:var(--t);border-radius:10px;padding:10px 12px;margin-top:12px}
.only .label{margin-top:0}
.p1{--a:var(--c1);--t:var(--c1t)}.p2{--a:var(--c2);--t:var(--c2t)}.p3{--a:var(--c3);--t:var(--c3t)}.p4{--a:var(--c4);--t:var(--c4t)}
.p5{--a:var(--c5);--t:var(--c5t)}.p6{--a:var(--c6);--t:var(--c6t)}.p7{--a:var(--c7);--t:var(--c7t)}.p8{--a:var(--c8);--t:var(--c8t)}
h2{font:600 1.2rem/1.3 "Iowan Old Style",Palatino,Georgia,serif;margin:30px 0 10px}
.clash{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px 16px}
.row{display:grid;grid-template-columns:auto 1fr;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);align-items:start}
.row:last-child{border-bottom:none}
.pair{display:flex;gap:4px;padding-top:6px;min-width:12px}
.dot{width:12px;height:12px;border-radius:4px;background:var(--a)}
.box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px}
.box ol{margin:0;padding-left:20px}
.foot{color:var(--muted);font-size:.8rem;margin-top:26px}
.label.plain{color:var(--muted)}
.label.plain::before{background:var(--muted)}
.sec{display:flex;align-items:center;gap:10px;margin:6px 0 6px;font:600 1.2rem/1.3 "Iowan Old Style",Palatino,Georgia,serif}
.briefing{margin-bottom:26px}
.briefing .box{margin-bottom:6px}
.chip{display:inline-block;font-size:.75rem;padding:1px 9px;border-radius:999px;background:var(--t);color:var(--a);font-weight:600;margin-top:4px}
.findings{padding:4px 16px}
.finding{display:grid;grid-template-columns:28px 1fr auto;gap:12px;align-items:start;padding:12px 0;border-bottom:1px solid var(--line)}
.finding:last-child{border-bottom:none}
.num{width:24px;height:24px;border-radius:50%;background:var(--text);color:var(--bg);display:grid;place-items:center;font-size:.78rem;font-weight:700;margin-top:1px}
.rel{font-size:.78rem;font-weight:700;padding-top:2px}
.r-high{color:var(--ok)}.r-medium{color:var(--need)}.r-low{color:var(--c2)}
.callout{border-radius:12px;padding:12px 16px;margin-top:10px;border:1px solid var(--line);background:var(--card)}
.callout.hidden{border-left:4px solid var(--c5)}
.callout.act{border-left:4px solid var(--ok);background:var(--okt)}
.callout .label{margin-top:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px}
.tile .label{margin-top:0}
.tile p{margin-top:6px}
.t-strongest{border-top:3px solid var(--ok)}.t-weakest{border-top:3px solid var(--c2)}
.l-agree{border-top:3px solid var(--c1)}.l-blind_spots{border-top:3px solid var(--c8)}
.review{margin-bottom:26px}
.callout.weak{border-left:4px solid var(--c2)}
.muted{color:var(--muted);font-size:.9rem;margin-top:4px}
.score{display:flex;align-items:center;gap:8px;margin-top:6px;font-size:.78rem;color:var(--muted);font-weight:600}
.bar{width:120px;height:6px;border-radius:3px;background:var(--line);overflow:hidden}
.bar i{display:block;height:100%;background:var(--text);opacity:.7}
.why{font-size:.8rem;color:var(--muted);margin-top:2px}
.bias{margin-top:10px}
.balance{display:flex;height:10px;border-radius:5px;overflow:hidden;margin:8px 0 8px;gap:2px}
.balance i{display:block;background:var(--a)}
.flag{color:var(--c2);font-weight:600;margin-top:8px}
@media (max-width:520px){.tag{display:none}h1{font-size:1.45rem}}
@media print{body{background:#fff}.card,.clash,.box{break-inside:avoid}}
</style>
</head>
<body>
<div class="wrap">
__BODY__
</div>
</body>
</html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="discussion JSON file")
    ap.add_argument("--root", help="project root (default: folder above scripts/)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    src = Path(args.input)
    if not src.is_absolute():
        src = (Path.cwd() / src).resolve()
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
        page, unknown, downgraded, dominant = render(data, library_ids(root))
        out = src.with_suffix(".html")
        out.write_text(page, encoding="utf-8")
        try:
            shown = out.relative_to(root).as_posix()
        except ValueError:
            shown = str(out)
        result = {"ok": True, "output": shown, "perspectives": len(data.get("perspectives") or [])}
        if unknown:
            result["unknown_sources"] = unknown
            result["warning"] = "these sources are not in INDEX.md and were shown as gaps"
        if dominant:
            result["dominant_perspective"] = dominant
        if downgraded:
            result["downgraded"] = downgraded
            result["downgrade_note"] = "'high' findings without a library source were shown as 'medium'"
    except FileNotFoundError:
        result = {"ok": False, "error": "not_found", "message": f"File not found: {src}"}
    except json.JSONDecodeError as e:
        result = {"ok": False, "error": "bad_json", "message": f"The discussion file isn't valid JSON: {e}"}
    except Exception as e:  # noqa: BLE001 - always answer in one JSON line
        result = {"ok": False, "error": "unexpected", "message": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
