#!/usr/bin/env python3
"""Work with the student's own Word document in "My Thesis Drafts/". Read-only: never modifies it.

Usage:
  thesis_doc.py find                       which document is current (newest .docx)
  thesis_doc.py read [--section 2.2]       headings + words per section; with --section, writes that
                                           section's text (footnotes as [^n]) to sessions/.thesis-doc/
  thesis_doc.py sync [--record]            compare the document's headings with the outline in
                                           thesis-brief.md, using the last-sync snapshot to tell which
                                           side changed; --record saves a new snapshot (after approval)
  thesis_doc.py export <draft.md> [--name "..."]
                                           save a Draftly draft as a new .docx in the folder
                                           (footnotes become numbered notes at the end)

Prints one line of JSON.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

FOLDER = "My Thesis Drafts"
SNAPSHOT = "sessions/.outline-sync.json"
NOT_CHAPTERS = re.compile(r"^(abstract|acknowledg|table of contents|contents|declaration|list of |abbreviations|"
                          r"table of (cases|legislation|statutes)|bibliography|references|appendix|annex)", re.I)
NUMBERED = re.compile(r"^\s*((?:\d{1,2})(?:\.\d{1,2}){0,2})\.?\s+(\S.{1,150})$")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9À-ɏ][\w'’\-]*", text))


def norm(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", title.lower().replace("–", " ").replace("-", " ")).strip()


# ------------------------------------------------------------------ find

def find_doc(root: Path) -> Path:
    folder = root / FOLDER
    folder.mkdir(exist_ok=True)  # older thesis folders may not have it yet
    docs = [p for p in folder.glob("*.docx")
            if not p.name.startswith(("~$", ".")) and "draftly" not in p.name.lower()]
    if not docs:
        raise DocError("no_document", f'No Word document in "{FOLDER}" yet.')
    return max(docs, key=lambda p: p.stat().st_mtime)


def doc_info(p: Path, root: Path) -> dict:
    st = p.stat()
    return {"file": p.name, "modified": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"),
            "others": sorted(x.name for x in p.parent.glob("*.docx")
                             if x != p and not x.name.startswith(("~$", ".")))}


# ------------------------------------------------------------------ read

def footnotes(path: Path) -> dict[str, str]:
    out = {}
    try:
        with zipfile.ZipFile(path) as z:
            if "word/footnotes.xml" not in z.namelist():
                return out
            from lxml import etree
            tree = etree.fromstring(z.read("word/footnotes.xml"))
            for fn in tree.iter(W + "footnote"):
                fid = fn.get(W + "id")
                text = "".join(t.text or "" for t in fn.iter(W + "t")).strip()
                if fid and text and int(fid) > 0:
                    out[fid] = text
    except Exception:  # noqa: BLE001 - footnotes are a bonus
        pass
    return out


def para_text(p) -> str:
    parts = []
    for el in p._p.iter():
        if el.tag == W + "t":
            parts.append(el.text or "")
        elif el.tag == W + "tab":
            parts.append(" ")
        elif el.tag == W + "footnoteReference":
            parts.append(f"[^{el.get(W + 'id')}]")
    return "".join(parts)


def heading_level(p) -> int | None:
    name = (p.style.name if p.style is not None else "") or ""
    m = re.match(r"(?:Heading|Überschrift|Titre|Titolo|Kop|Encabezado)\s*(\d)", name, re.I)
    if m:
        return int(m.group(1))
    sid = (p.style.style_id if p.style is not None else "") or ""
    m = re.match(r"Heading(\d)", sid)
    return int(m.group(1)) if m else None


def read_structure(path: Path) -> dict:
    import docx
    d = docx.Document(str(path))
    paras = [(heading_level(p), para_text(p).strip()) for p in d.paragraphs]
    styled = any(lvl in (1, 2, 3) for lvl, t in paras if t)
    blocks: list[dict] = []          # {"level", "num", "title", "text": [...]}
    pre: list[str] = []
    ch = sec = sub = 0
    for lvl, text in paras:
        if not text:
            continue
        head = None
        if styled and lvl in (1, 2, 3):
            m = NUMBERED.match(text)
            title = m.group(2).strip() if m else text
            given = m.group(1) if m else None
            if NOT_CHAPTERS.match(title) and lvl == 1:
                head = {"level": 1, "num": None, "title": title}
            else:
                if lvl == 1:
                    ch, sec, sub = ch + 1, 0, 0
                    auto = f"{ch}"
                elif lvl == 2:
                    sec, sub = sec + 1, 0
                    auto = f"{ch}.{sec}"
                else:
                    sub += 1
                    auto = f"{ch}.{sec}.{sub}"
                head = {"level": lvl, "num": given or auto, "title": title}
        elif not styled:
            m = NUMBERED.match(text)
            if m and len(text) < 160 and not text.rstrip().endswith((".", ";", ":")) and words(m.group(2)) <= 18:
                num = m.group(1)
                head = {"level": num.count(".") + 1, "num": num, "title": m.group(2).strip()}
        if head:
            head["text"] = []
            blocks.append(head)
        elif blocks:
            blocks[-1]["text"].append(text)
        else:
            pre.append(text)

    heads = []
    for i, b in enumerate(blocks):
        own = sum(words(re.sub(r"\[\^\d+\]", "", t)) for t in b["text"])
        total = own
        for nxt in blocks[i + 1:]:
            if nxt["level"] <= b["level"]:
                break
            total += sum(words(re.sub(r"\[\^\d+\]", "", t)) for t in nxt["text"])
        heads.append({"num": b["num"], "level": b["level"], "title": b["title"], "words": total})
    body = sum(h["words"] for h in heads if h["level"] == 1 and h["num"]) or \
        sum(words(t) for b in blocks for t in b["text"])
    return {"blocks": blocks, "headings": heads, "detected_by": "heading styles" if styled else "numbered lines",
            "words_in_chapters": body, "footnotes": footnotes(path)}


def section_text(struct: dict, num: str) -> tuple[dict, str] | None:
    blocks = struct["blocks"]
    for i, b in enumerate(blocks):
        if b["num"] == num:
            out = [f"{'#' * min(b['level'] + 1, 6)} {b['num']} {b['title']}", ""] + [t + "\n" for t in b["text"]]
            for nxt in blocks[i + 1:]:
                if nxt["level"] <= b["level"]:
                    break
                out += [f"{'#' * min(nxt['level'] + 1, 6)} {nxt['num'] or ''} {nxt['title']}".replace("  ", " "), ""]
                out += [t + "\n" for t in nxt["text"]]
            text = "\n".join(out)
            refs = sorted(set(re.findall(r"\[\^(\d+)\]", text)), key=int)
            if refs:
                text += "\n\n" + "\n".join(f"[^{r}]: {struct['footnotes'].get(r, '(footnote text not found)')}" for r in refs)
            return b, text
    return None


# ------------------------------------------------------------------ outline + sync

def read_outline(root: Path) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_library import parse_outline
    return [{"num": o["num"], "title": o["title"], "words": o["words"], "level": o["num"].count(".") + 1}
            for o in parse_outline(root / "thesis-brief.md")]


def shape(items: list[dict]) -> list[list]:
    return [[i["num"], norm(i["title"])] for i in items if i.get("num")]


STOP = set("the a an of and in as to for on at by with from its their after before between under".split())


def similar(a: str, b: str, same_num: bool) -> float:
    """0 = unrelated. Sequence similarity and shared content words; a shared number needs a shared word."""
    seq = difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
    wa, wb = set(norm(a).split()) - STOP, set(norm(b).split()) - STOP
    shared = len(wa & wb) / max(1, min(len(wa), len(wb)))
    if same_num:
        return max(seq, shared) if (shared > 0 or seq >= 0.5) else 0
    score = max(seq, shared)
    return score if score >= 0.6 else 0


def match(outline: list[dict], doc: list[dict], before: set[str] | None = None) -> list[dict]:
    doc = [d for d in doc if d.get("num")]
    used_o, used_d, pairs = set(), set(), []
    # 1) identical titles
    for oi, o in enumerate(outline):
        for di, d in enumerate(doc):
            if di not in used_d and norm(o["title"]) == norm(d["title"]) and o["level"] == d["level"]:
                pairs.append((oi, di)); used_o.add(oi); used_d.add(di); break
    # 2) similar titles, preferring the same number
    cands = []
    for oi, o in enumerate(outline):
        if oi in used_o:
            continue
        for di, d in enumerate(doc):
            if di in used_d or o["level"] != d["level"]:
                continue
            same_num = o["num"] == d["num"]
            r = similar(o["title"], d["title"], same_num)
            if r:
                cands.append((r + (0.3 if same_num else 0), oi, di))
    for _, oi, di in sorted(cands, reverse=True):
        if oi not in used_o and di not in used_d:
            pairs.append((oi, di)); used_o.add(oi); used_d.add(di)
    diffs = []
    for oi, di in pairs:
        o, d = outline[oi], doc[di]
        if norm(o["title"]) != norm(d["title"]):
            diffs.append({"type": "renamed", "num": o["num"], "doc_num": d["num"], "title": o["title"], "doc_title": d["title"]})
        if o["num"] != d["num"]:
            diffs.append({"type": "moved", "num": o["num"], "doc_num": d["num"], "title": d["title"]})
        if o.get("words") and d["words"] > o["words"] * 1.1:
            diffs.append({"type": "over_budget", "num": o["num"], "title": d["title"], "words": d["words"], "budget": o["words"]})
    for di, d in enumerate(doc):
        if di not in used_d:
            diffs.append({"type": "added_in_doc", "doc_num": d["num"], "title": d["title"], "words": d["words"]})
    for oi, o in enumerate(outline):
        if oi not in used_o:
            # in the document at the last sync and now gone = removed; never there = not written yet
            kind = "removed_in_doc" if before and norm(o["title"]) in before else "not_started"
            diffs.append({"type": kind, "num": o["num"], "title": o["title"]})
    return diffs


def sync(root: Path, record: bool) -> dict:
    path = find_doc(root)
    struct = read_structure(path)
    outline = read_outline(root)
    snap_path = root / SNAPSHOT
    snap = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else None
    doc_shape, out_shape = shape(struct["headings"]), shape(outline)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    if record:
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(json.dumps({"synced": dt.datetime.now().isoformat(timespec="minutes"), "file": path.name,
                                         "sha256": digest, "doc": doc_shape, "outline": out_shape}, indent=1),
                             encoding="utf-8")
        return {"ok": True, "recorded": True, **doc_info(path, root)}

    before = {t for _, t in snap.get("doc", [])} if snap else None
    diffs = match(outline, struct["headings"], before) if outline else []
    structural = [x for x in diffs if x["type"] not in ("over_budget", "not_started")]
    res = {"ok": True, **doc_info(path, root), "detected_by": struct["detected_by"],
           "doc_headings": len([h for h in struct["headings"] if h["num"]]), "outline_sections": len(outline),
           "in_sync": not structural, "differences": diffs}
    if not outline:
        res["note"] = "no outline in the thesis brief yet"
    if not struct["headings"]:
        res["note"] = "no headings found: use Heading 1/2 styles or numbered headings like '2.1 Title'"
    if snap:
        res["last_sync"] = snap.get("synced")
        res["doc_changed"] = snap.get("sha256") != digest and snap.get("doc") != doc_shape
        res["outline_changed"] = snap.get("outline") != out_shape
        res["direction"] = ("none" if not structural else
                            "both" if res["doc_changed"] and res["outline_changed"] else
                            "doc" if res["doc_changed"] else
                            "outline" if res["outline_changed"] else "none")
    else:
        res["last_sync"] = None
        res["direction"] = "first_sync" if structural else "none"
    return res


# ------------------------------------------------------------------ export

def add_runs(par, text: str, notes: dict[str, int]) -> None:
    from docx.enum.text import WD_COLOR_INDEX
    for tok in re.split(r"(\[\^[^\]]+\]|\*\*[^*]+\*\*|\*[^*]+\*|\[(?:CITATION|PINPOINT) NEEDED[^\]]*\])", text):
        if not tok:
            continue
        if tok.startswith("[^"):
            key = tok[2:-1]
            notes.setdefault(key, len(notes) + 1)
            par.add_run(str(notes[key])).font.superscript = True
        elif tok.startswith("**"):
            par.add_run(tok[2:-2]).bold = True
        elif tok.startswith("*") and len(tok) > 2:
            par.add_run(tok[1:-1]).italic = True
        elif tok.startswith("[CITATION") or tok.startswith("[PINPOINT"):
            par.add_run(tok).font.highlight_color = WD_COLOR_INDEX.YELLOW
        else:
            par.add_run(tok)


def export(root: Path, src: Path, name: str | None) -> dict:
    import docx
    md = src.read_text(encoding="utf-8")
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    m = re.search(r"^#{1,6}\s*Notes for you.*$", md, flags=re.M | re.I)
    if m:
        md = md[:m.start()]
    markers = len(re.findall(r"\[(?:CITATION|PINPOINT) NEEDED", md))
    defs = dict(re.findall(r"^\[\^([^\]]+)\]:\s*(.+)$", md, flags=re.M))
    md = re.sub(r"^\[\^[^\]]+\]:.*$", "", md, flags=re.M)
    d = docx.Document()
    notes: dict[str, int] = {}
    para_lines: list[str] = []

    def flush():
        if para_lines:
            add_runs(d.add_paragraph(), " ".join(x.strip() for x in para_lines), notes)
            para_lines.clear()

    for line in md.splitlines():
        s = line.strip()
        if re.match(r"^[-*]?\s*\**(chapter|version|date|word count|words|based on|status)\**\s*:", s, re.I):
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", s)
        b = re.match(r"^[-*]\s+(.*)$", s)
        if h:
            flush(); d.add_heading(h.group(2).strip(), level=min(len(h.group(1)), 4))
        elif b:
            flush(); add_runs(d.add_paragraph(style="List Bullet"), b.group(1), notes)
        elif not s or s == "---":
            flush()
        else:
            para_lines.append(s)
    flush()
    if notes:
        d.add_heading("Notes", level=2)
        for key, n in sorted(notes.items(), key=lambda kv: kv[1]):
            p = d.add_paragraph()
            p.add_run(f"{n}. ").bold = True
            add_runs(p, defs.get(key, "(missing footnote text)"), {})
    folder = root / FOLDER
    folder.mkdir(exist_ok=True)
    stem = name or f"{src.stem} - Draftly {dt.date.today().isoformat()}"
    stem = re.sub(r'[\\/:*?"<>|]', "-", stem)
    if "draftly" not in stem.lower():
        stem += " - Draftly"
    out = folder / f"{stem}.docx"
    k = 2
    while out.exists():
        out = folder / f"{stem} ({k}).docx"; k += 1
    d.save(str(out))
    return {"ok": True, "output": f"{FOLDER}/{out.name}", "notes": len(notes),
            "open_markers": markers}


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["find", "read", "sync", "export"])
    ap.add_argument("draft", nargs="?", help="for export: the draft .md")
    ap.add_argument("--section", help="for read: a section number, e.g. 2.2")
    ap.add_argument("--record", action="store_true", help="for sync: save the current state as the new baseline")
    ap.add_argument("--name", help="for export: file name (without .docx)")
    ap.add_argument("--root", help="project root (default: folder above scripts/)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    try:
        if args.command == "find":
            res = {"ok": True, **doc_info(find_doc(root), root)}
        elif args.command == "read":
            path = find_doc(root)
            struct = read_structure(path)
            res = {"ok": True, **doc_info(path, root), "detected_by": struct["detected_by"],
                   "words_in_chapters": struct["words_in_chapters"], "footnotes": len(struct["footnotes"]),
                   "headings": struct["headings"]}
            if args.section:
                hit = section_text(struct, args.section)
                if not hit:
                    raise DocError("no_section", f"No section {args.section} in the document.")
                b, text = hit
                out = root / "sessions" / ".thesis-doc" / f"section-{args.section}.md"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
                res = {"ok": True, **doc_info(path, root), "section": args.section, "title": b["title"],
                       "words": next((h["words"] for h in struct["headings"] if h["num"] == args.section), 0),
                       "footnotes": len(re.findall(r"^\[\^\d+\]:", text, flags=re.M)),
                       "text_file": out.relative_to(root).as_posix()}
        elif args.command == "sync":
            res = sync(root, args.record)
        else:
            if not args.draft:
                raise DocError("no_input", "Give the draft to export.")
            res = export(root, Path(args.draft).resolve(), args.name)
    except DocError as e:
        res = {"ok": False, "error": e.code, "message": e.message}
    except ImportError as e:
        res = {"ok": False, "error": "missing_dependency", "message": f"{e}. Run scripts/setup.sh."}
    except Exception as e:  # noqa: BLE001 - always answer in one JSON line
        res = {"ok": False, "error": "unexpected", "message": f"{type(e).__name__}: {e}"}
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
