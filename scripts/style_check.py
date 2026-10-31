#!/usr/bin/env python3
"""Count writing-style patterns in a draft (see the skill's references/writing-style.md).

Usage: style_check.py drafts/ch3-nbfi-v2.md [--max-flags N]

Checks body text only: footnote definitions, citation markers, headings, the draft
header block and the "Notes for you" section are ignored. Prints one line of JSON.
The counts are prompts to look again, not verdicts - a flagged word can be right in context.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

STOCK = [
    r"it is (?:important|worth|crucial|essential) to (?:note|mention|emphasi[sz]e|highlight)",
    r"it (?:should|must) be noted",
    r"it is worth noting", r"(?:plays?|played|playing) an? (?:crucial|pivotal|key|vital|significant|important) role",
    r"in today'?s\b", r"in an (?:increasingly|ever[- ]changing|ever[- ]evolving)", r"rapidly evolving",
    r"a testament to", r"sheds? light on", r"paves? the way", r"at the heart of", r"in the realm of",
    r"serves as a (?:reminder|testament)", r"a double-edged sword", r"stands? as a", r"the intricate interplay",
    r"when it comes to", r"in order to", r"it goes without saying", r"needless to say",
]
INFLATED = [
    r"delv(?:e|es|ed|ing)", r"landscapes?", r"navigat(?:e|es|ed|ing)", r"tapestry", r"multifaceted",
    r"robust(?:ly|ness)?", r"leverag(?:es|ing)", r"to leverage", r"underscor(?:e|es|ed|ing)", r"pivotal", r"intricat(?:e|ely|acies)",
    r"realms?", r"holistic(?:ally)?", r"myriad", r"nuanced", r"meticulous(?:ly)?", r"seamless(?:ly)?",
    r"embark(?:s|ed|ing)?", r"foster(?:s|ed|ing)?", r"bolster(?:s|ed|ing)?", r"showcas(?:e|es|ed|ing)",
    r"commendabl[ey]", r"noteworthy", r"paramount",
]
GRAND = [
    r"revolutionary", r"unprecedented", r"paradigm[- ]shift", r"fundamentally (?:transforms?|reshap\w+|chang\w+)",
    r"game[- ]chang\w+", r"groundbreaking", r"transformative", r"seismic", r"profound(?:ly)? (?:impact|implications)",
]
TRANSITIONS = r"(?:Moreover|Furthermore|Additionally|In addition|In conclusion|Ultimately|Notably|Crucially|Importantly|Indeed|Consequently|Thus|Hence|Overall|In essence|To summari[sz]e)\b,?"
RESTATE_OPENERS = r"(?:This (?:shows|demonstrates|highlights|illustrates|underscores|suggests)|Thus,|Therefore,? it (?:is|becomes) clear|In sum|In short|Overall,|Ultimately,|Clearly,|In essence,|Taken together)"
CONTRAST = [r"\bnot only\b[^.;:]{1,80}\bbut(?: also)?\b", r"\bnot (?:just|merely|simply)?\s*[^.;:,]{1,50},? but\b"]
TRIPLET = r"\b(\w+), (\w+),? and (\w+)\b"
DASHES = r"\u2014|\u2013| -- | - "
STOP = set("the a an of to in and or for on by with as is are was were be been that this these those it its their his her at from which who than into not but also can may must should would will".split())

PROTECT = ["e.g.", "i.e.", "etc.", "cf.", "viz.", "No.", "no.", "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "St.", "v.", "vs.",
           "Art.", "art.", "s.", "ss.", "para.", "paras.", "p.", "pp.", "ch.", "Ch.", "ed.", "eds.", "edn.", "Ltd.", "Inc.", "Co."]


def body_text(md: str) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"^```.*?^```[ \t]*$", "", md, flags=re.S | re.M)
    m = re.search(r"^#{1,6}\s*Notes for you.*$", md, flags=re.M | re.I)
    if m:
        md = md[:m.start()]
    lines = []
    for ln in md.splitlines():
        s = ln.strip()
        if re.match(r"^\[\^[^\]]+\]:", s):                     # footnote definition
            continue
        if s.startswith("#") or s.startswith("|") or s.startswith(">") or s == "---":
            lines.append("")
            continue
        if re.match(r"^[-*]?\s*\**(chapter|version|date|word count|words|based on|status)\**\s*:", s, re.I):
            continue
        lines.append(ln)
    text = "\n".join(lines)
    text = re.sub(r"\[\^[^\]]+\]", "", text)                    # footnote refs
    text = re.sub(r"\[(CITATION NEEDED|PINPOINT NEEDED)[^\]]*\]", "", text)
    text = re.sub(r"\*\*|__|(?<!\w)[*_](?!\s)|(?<!\s)[*_](?!\w)", "", text)
    return text


def sentences(par: str) -> list[str]:
    tmp = par
    for i, abbr in enumerate(PROTECT):
        tmp = re.sub(rf"(?<!\w){re.escape(abbr)}", abbr.replace(".", f"\x00{i}\x01"), tmp)
    tmp = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", "\\1\x00I\x01", tmp)   # initials: J. Smith
    parts = re.split(r"(?<=[.!?])[\"'\u201d\u2019)]?\s+(?=[A-Z0-9\"'\u201c\u2018(])", tmp)
    out = []
    for p in parts:
        p = re.sub(r"\x00\d+\x01|\x00I\x01", ".", p).strip()
        if p:
            out.append(p)
    return out


def words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", s)


def content(s: str) -> set[str]:
    return {w.lower() for w in words(s) if len(w) > 3 and w.lower() not in STOP}


def excerpt(text: str, start: int, end: int, pad: int = 35) -> str:
    a, b = max(0, start - pad), min(len(text), end + pad)
    return ("..." if a else "") + re.sub(r"\s+", " ", text[a:b]).strip() + ("..." if b < len(text) else "")


def check(md: str, max_flags: int) -> dict:
    text = body_text(md)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(words(p)) >= 8]
    counts = {k: 0 for k in ("stock_phrases", "inflated_words", "grand_framing", "formulaic_transitions",
                             "forced_contrast", "reflex_triplets", "dash_heavy_paragraphs",
                             "colon_semicolon_heavy_paragraphs", "restating_endings", "long_sentences")}
    flags: list[dict] = []

    spans: list[tuple[int, int, int]] = []   # (paragraph, start, end) already flagged

    def flag(kind: str, pi: int, par: str, m) -> None:
        if any(p == pi and m.start() < e and s < m.end() for p, s, e in spans):
            return  # one problem, one flag ("pivotal" inside "plays a pivotal role")
        spans.append((pi, m.start(), m.end()))
        counts[kind] += 1
        flags.append({"type": kind, "paragraph": pi, "match": m.group(0), "context": excerpt(par, m.start(), m.end())})

    all_lengths: list[int] = []
    n_words = 0
    for pi, par in enumerate(paras, start=1):
        n_words += len(words(par))
        for pats, kind in ((STOCK, "stock_phrases"), (INFLATED, "inflated_words"), (GRAND, "grand_framing"),
                           (CONTRAST, "forced_contrast")):
            for pat in pats:
                rx = pat if kind == "forced_contrast" else rf"\b{pat}\b"
                for m in re.finditer(rx, par, flags=re.I):
                    flag(kind, pi, par, m)
        sents = sentences(par)
        for s in sents:
            m = re.match(TRANSITIONS, s)
            if m:
                flag("formulaic_transitions", pi, par, re.search(re.escape(m.group(0)), par))
            n = len(words(s))
            all_lengths.append(n)
            if n > 45:
                counts["long_sentences"] += 1
                flags.append({"type": "long_sentences", "paragraph": pi, "match": f"{n} words",
                              "context": " ".join(s.split()[:12]) + " ..."})
        for m in re.finditer(TRIPLET, par):
            if not any(w.lower() in STOP for w in m.groups()):
                flag("reflex_triplets", pi, par, m)
        dashes = len(re.findall(DASHES, par))
        if dashes > 1:
            counts["dash_heavy_paragraphs"] += 1
            flags.append({"type": "dash_heavy_paragraphs", "paragraph": pi, "match": f"{dashes} dashes",
                          "context": " ".join(par.split()[:12]) + " ..."})
        punct = par.count(";") + len(re.findall(r":(?!\d)", par))
        if punct >= 3:
            counts["colon_semicolon_heavy_paragraphs"] += 1
            flags.append({"type": "colon_semicolon_heavy_paragraphs", "paragraph": pi,
                          "match": f"{punct} colons/semicolons", "context": " ".join(par.split()[:12]) + " ..."})
        if len(sents) >= 3:
            last, first = sents[-1], sents[0]
            a, b = content(first), content(last)
            overlap = len(a & b) / max(1, min(len(a), len(b)))
            if re.match(RESTATE_OPENERS, last) or (len(b) >= 4 and overlap >= 0.6):
                counts["restating_endings"] += 1
                flags.append({"type": "restating_endings", "paragraph": pi, "match": "last sentence repeats the opening",
                              "context": " ".join(last.split()[:14]) + " ..."})

    # reflex triplets only matter when they become a habit
    if counts["reflex_triplets"] <= max(2, n_words // 400):
        flags = [f for f in flags if f["type"] != "reflex_triplets"]
        counts["reflex_triplets"] = 0

    rhythm = {}
    if len(all_lengths) >= 8:
        mean = statistics.mean(all_lengths)
        sd = statistics.pstdev(all_lengths)
        rhythm = {"mean_sentence_words": round(mean, 1), "variation": round(sd / mean, 2) if mean else 0}
        rhythm["monotone"] = rhythm["variation"] < 0.3

    issues = sum(counts.values()) + (1 if rhythm.get("monotone") else 0)
    per_k = issues / max(1, n_words) * 1000
    verdict = "clean" if issues == 0 else ("minor" if per_k < 8 else "needs work")
    return {
        "ok": True, "words": n_words, "paragraphs": len(paras), "sentences": len(all_lengths),
        "issues": issues, "issues_per_1000_words": round(per_k, 1), "verdict": verdict,
        "counts": {k: v for k, v in counts.items() if v}, "rhythm": rhythm,
        "flags": flags[:max_flags], "more_flags": max(0, len(flags) - max_flags),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="draft (.md or .txt)")
    ap.add_argument("--max-flags", type=int, default=40)
    args = ap.parse_args(argv)
    try:
        md = Path(args.input).read_text(encoding="utf-8")
        result = {"file": Path(args.input).name, **check(md, args.max_flags)}
    except FileNotFoundError:
        result = {"ok": False, "error": "not_found", "message": f"File not found: {args.input}"}
    except Exception as e:  # noqa: BLE001 - always answer in one JSON line
        result = {"ok": False, "error": "unexpected", "message": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
