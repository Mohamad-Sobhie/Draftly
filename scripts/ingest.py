#!/usr/bin/env python3
"""Turn a source (PDF, scanned PDF, .docx, .html/URL, .txt/.md) into page-marked,
chapter-split markdown for the Draftly library.

Usage:
  ingest.py <input> [--id SOURCE_ID] [--store copy|move|none] [--force]
  ingest.py <input> --check-only          # duplicate check, writes nothing
  ingest.py --list-downloads [--limit N]   # recent candidate files in ~/Downloads

Output:  references/text/<source-id>/NN-<slug>.md  +  _meta.json
Always prints exactly one line of JSON on stdout (for Claude to read).
Never deletes the original; --store move is only used when asked to move it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

PAGES_PER_CHUNK = 15
MAX_CHAPTER_PAGES = 30           # longer outline/heading chapters are cut into 15-page parts
MIN_CHARS_PER_PAGE = 25          # below this on average, treat the PDF as scanned
SUPPORTED = {".pdf", ".docx", ".html", ".htm", ".txt", ".md", ".markdown"}
logging.getLogger("pypdf").setLevel(logging.ERROR)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


class IngestError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ----------------------------------------------------------------- helpers

def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def slugify(text: str, maxlen: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:maxlen].rstrip("-")) or "section"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s, re.I))


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ------------------------------------------------------- list downloads

def list_downloads(limit: int) -> dict:
    dl = Path.home() / "Downloads"
    if not dl.is_dir():
        return {"ok": False, "error": "no_downloads_folder", "message": "No Downloads folder found."}
    now = dt.datetime.now().timestamp()
    files = []
    for p in dl.iterdir():
        if p.is_file() and p.suffix.lower() in SUPPORTED | {".doc", ".epub"} and not p.name.startswith("."):
            st = p.stat()
            files.append({
                "name": p.name,
                "path": str(p),
                "modified": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"),
                "age_minutes": int((now - st.st_mtime) / 60),
                "size_kb": st.st_size // 1024,
            })
    files.sort(key=lambda f: f["age_minutes"])
    return {"ok": True, "files": files[:limit]}


# ------------------------------------------------------------- download

def _ssl_context() -> ssl.SSLContext:
    # python.org builds on macOS ship without system certificates; certifi fixes that
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def download(url: str, inbox: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            cdisp = resp.headers.get("Content-Disposition") or ""
            final_url = resp.geturl()
    except Exception as e:  # noqa: BLE001 - any network failure is reported the same way
        raise IngestError("download_failed", f"Could not download {url}: {e}")

    name = ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cdisp, re.I)
    if m:
        name = urllib.parse.unquote(m.group(1))
    if not name:
        name = urllib.parse.unquote(Path(urllib.parse.urlparse(final_url).path).name) or "download"
    stem, ext = os.path.splitext(name)
    if data[:5] == b"%PDF-" or "pdf" in ctype:
        ext = ".pdf"
    elif "html" in ctype or (not ext and b"<html" in data[:2000].lower()):
        ext = ".html"
    elif "wordprocessingml" in ctype:
        ext = ".docx"
    elif ext.lower() not in SUPPORTED:
        ext = ".html" if b"<" in data[:200] else ".txt"
    inbox.mkdir(parents=True, exist_ok=True)
    target = inbox / f"{slugify(stem or 'download', 60)}{ext}"
    target.write_bytes(data)
    if ext == ".html":
        # remember where it came from, for the citation
        target.with_suffix(".url").write_text(final_url, encoding="utf-8")
    return target


# ------------------------------------------------------------------ PDF

def _pypdf_reader(path: Path):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            raise IngestError("encrypted", "The PDF is password-protected.")
    return reader


def _avg_chars(texts: list[str]) -> float:
    return sum(len(t.strip()) for t in texts) / max(1, len(texts))


def _pdftotext_pages(path: Path, n: int, layout: bool = False) -> list[str] | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        cmd = ["pdftotext", "-enc", "UTF-8"] + (["-layout"] if layout else []) + [str(path), "-"]
        out = subprocess.run(cmd,
                             capture_output=True, timeout=600, check=True).stdout.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    if len(pages) < n:
        pages += [""] * (n - len(pages))
    return pages[:n]


def _ocr_pages(path: Path, n: int) -> tuple[list[str], str]:
    """OCR a scanned PDF. Prefers ocrmypdf, then tesseract CLI + pdftoppm."""
    if shutil.which("ocrmypdf"):
        with tempfile.TemporaryDirectory() as tmp:
            out_pdf = Path(tmp) / "ocr.pdf"
            r = subprocess.run(["ocrmypdf", "--quiet", "--skip-text", str(path), str(out_pdf)],
                               capture_output=True, timeout=3600)
            if r.returncode == 0 and out_pdf.exists():
                reader = _pypdf_reader(out_pdf)
                return [p.extract_text() or "" for p in reader.pages], "ocrmypdf"
    if shutil.which("tesseract") and shutil.which("pdftoppm"):
        texts = []
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(1, n + 1):
                prefix = Path(tmp) / f"p{i}"
                subprocess.run(["pdftoppm", "-r", "300", "-gray", "-f", str(i), "-l", str(i),
                                "-png", "-singlefile", str(path), str(prefix)],
                               capture_output=True, timeout=600)
                img = prefix.with_suffix(".png")
                if not img.exists():
                    texts.append("")
                    continue
                r = subprocess.run(["tesseract", str(img), "stdout"], capture_output=True, timeout=600)
                texts.append(r.stdout.decode("utf-8", "replace"))
                img.unlink(missing_ok=True)
        return texts, "tesseract"
    raise IngestError(
        "scanned_no_ocr",
        "This PDF has no text layer (it is a scan) and no OCR tool is installed. "
        "Install tesseract + poppler (or ocrmypdf) and run ingest again.")


def _outline_starts(reader) -> list[tuple[int, str]]:
    try:
        outline = reader.outline
    except Exception:  # noqa: BLE001
        return []

    def entries(items):
        """Return [(dest, children)] for one outline level."""
        res = []
        for it in items:
            if isinstance(it, list):
                if res:
                    res[-1] = (res[-1][0], it)
            else:
                res.append((it, []))
        return res

    level = entries(outline or [])
    if len(level) == 1 and level[0][1]:
        level = entries(level[0][1])
    starts: dict[int, str] = {}
    for dest, _ in level:
        try:
            page = reader.get_destination_page_number(dest)
        except Exception:  # noqa: BLE001
            continue
        if page is None or page < 0:
            continue
        title = str(getattr(dest, "title", "") or "").strip() or f"Section at page {page + 1}"
        starts.setdefault(page, title)
    return sorted(starts.items())


HEADING_PATTERNS = [
    re.compile(r"^(chapter|part)\s+([0-9]+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)\b.*$", re.I),
    re.compile(r"^(?:section\s+)?([1-9][0-9]?)\.?\s+[A-Z][A-Za-z0-9 ,:;()'’\-–&]{3,80}$"),
    re.compile(r"^(introduction|executive summary|summary|abstract|conclusions?|concluding remarks|"
               r"references|bibliography|annex(es)?(\s+[a-z0-9]+)?|appendix(\s+[a-z0-9]+)?|glossary)\s*$", re.I),
]


def _heading_starts(texts: list[str]) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    for i, t in enumerate(texts):
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()][:6]
        for ln in lines:
            ln = re.sub(r"\s{2,}", " ", ln)
            if len(ln) > 90:
                continue
            if any(p.match(ln) for p in HEADING_PATTERNS):
                if not starts or i - starts[-1][0] >= 2:
                    starts.append((i, ln))
                break
    return starts if len(starts) >= 2 else []


def _cut_long(starts: list[tuple[int, str]], n: int) -> list[tuple[int, str]]:
    out = []
    for idx, (start, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else n
        if end - start <= MAX_CHAPTER_PAGES:
            out.append((start, title))
            continue
        for k, s in enumerate(range(start, end, PAGES_PER_CHUNK), start=1):
            out.append((s, f"{title} (part {k})"))
    return out


JUNK_TITLE = re.compile(r"(\.(book|docx?|indd|pdf|qxd|tex|rtf)$)|^(microsoft word|untitled|title)\b|^\W*$", re.I)


def extract_pdf(path: Path) -> dict:
    reader = _pypdf_reader(path)
    n = len(reader.pages)
    if n == 0:
        raise IngestError("empty", "The PDF has no pages.")
    # poppler's pdftotext keeps words intact more reliably than pypdf (better for search)
    texts, extractor, ocr = _pdftotext_pages(path, n) or [], "pdftotext", False
    if _avg_chars(texts) < MIN_CHARS_PER_PAGE:
        texts, extractor = [], "pypdf"
        for p in reader.pages:
            try:
                texts.append(p.extract_text() or "")
            except Exception:  # noqa: BLE001
                texts.append("")
    if _avg_chars(texts) < MIN_CHARS_PER_PAGE:
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                alt = [(pg.extract_text() or "") for pg in pdf.pages]
            if _avg_chars(alt) > _avg_chars(texts):
                texts, extractor = alt, "pdfplumber"
        except Exception:  # noqa: BLE001
            pass
    if _avg_chars(texts) < MIN_CHARS_PER_PAGE:
        alt = _pdftotext_pages(path, n, layout=True)
        if alt and _avg_chars(alt) > _avg_chars(texts):
            texts, extractor = alt, "pdftotext-layout"
    if _avg_chars(texts) < MIN_CHARS_PER_PAGE:
        texts, extractor = _ocr_pages(path, n)
        ocr = True

    try:
        labels = list(reader.page_labels)
    except Exception:  # noqa: BLE001
        labels = []
    if len(labels) != n:
        labels = [str(i + 1) for i in range(n)]

    meta = reader.metadata or {}
    title = str(meta.get("/Title") or "").strip()
    if JUNK_TITLE.search(title):
        title = ""
    author = str(meta.get("/Author") or "").strip()
    date = str(meta.get("/CreationDate") or "")
    m = re.match(r"D:(\d{4})", date)

    starts, method = _outline_starts(reader), "outline"
    if len(starts) < 2:
        starts, method = _heading_starts(texts), "headings"
    if len(starts) < 2:
        if n <= PAGES_PER_CHUNK:
            starts, method = [(0, "Full text")], "single"
        else:
            starts = [(i, f"Pages {labels[i]}-{labels[min(i + PAGES_PER_CHUNK, n) - 1]}")
                      for i in range(0, n, PAGES_PER_CHUNK)]
            method = "fixed-15-pages"
    if starts[0][0] > 0:
        starts.insert(0, (0, "Front matter"))
    if method in ("outline", "headings"):
        starts = _cut_long(starts, n)

    chapters = []
    for idx, (start, ctitle) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else n
        if end <= start:
            continue
        body = []
        for i in range(start, end):
            body.append(f"[p. {labels[i]}]\n\n{clean_text(texts[i])}")
        chapters.append({
            "title": ctitle,
            "pages": f"{labels[start]}-{labels[end - 1]}" if end - 1 > start else labels[start],
            "body": "\n\n".join(body),
        })

    return {
        "title": title, "author": author, "metadata_year": m.group(1) if m else "",
        "page_count": n, "split_method": method, "ocr": ocr, "extractor": extractor,
        "page_labels": "printed" if labels != [str(i + 1) for i in range(n)] else "physical",
        "chapters": chapters,
    }


# ------------------------------------------------- block-based formats

def _blocks_to_chapters(blocks: list[dict], has_pages: bool) -> tuple[list[dict], str]:
    """blocks: {"kind": "heading"|"text", "level": int, "text": str, "page": int}"""
    heads = [b["level"] for b in blocks if b["kind"] == "heading"]
    split_level = None
    for lvl in sorted(set(heads)):
        if heads.count(lvl) >= 2:
            split_level = lvl
            break
    groups: list[list[dict]] = [[]]
    titles = ["Front matter" if split_level else "Full text"]
    for b in blocks:
        if split_level and b["kind"] == "heading" and b["level"] == split_level:
            groups.append([])
            titles.append(b["text"])
        groups[-1].append(b)
    if groups and not groups[0]:
        groups.pop(0)
        titles.pop(0)
    elif split_level and groups[0] and all(not b["text"].strip() for b in groups[0]):
        groups.pop(0)
        titles.pop(0)

    chapters = []
    for title, grp in zip(titles, groups):
        out, cur = [], None
        for b in grp:
            if has_pages and b["page"] != cur:
                cur = b["page"]
                out.append(f"[p. {cur}]")
            if b["kind"] == "heading":
                out.append("#" * min(6, b["level"] + 1) + " " + b["text"])
            elif b["text"].strip():
                out.append(b["text"])
        pages = sorted({b["page"] for b in grp}) if has_pages else []
        chapters.append({
            "title": title,
            "pages": (f"{pages[0]}-{pages[-1]}" if len(pages) > 1 else str(pages[0])) if pages else "",
            "body": "\n\n".join(out),
        })
    return chapters, ("headings" if split_level else "single")


def extract_docx(path: Path) -> dict:
    import docx
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(str(path))
    blocks, page, breaks = [], 1, 0
    body = d.element.body
    # Word records where it rendered page breaks; prefer those, else count explicit breaks
    rendered = bool(body.xpath(".//w:lastRenderedPageBreak"))
    for el in body.iterchildren():
        if el.tag == qn("w:p"):
            para = Paragraph(el, d)
            if rendered:
                n_breaks = len(el.xpath(".//w:lastRenderedPageBreak"))
            else:
                n_breaks = len(el.xpath('.//w:br[@w:type="page"]')) + len(el.xpath(".//w:pageBreakBefore"))
            text = para.text.strip()
            style = (para.style.name if para.style is not None else "") or ""
            # a break at the very start of a paragraph belongs before its text
            page += n_breaks
            breaks += n_breaks
            m = re.match(r"Heading (\d)", style)
            if m and text:
                blocks.append({"kind": "heading", "level": int(m.group(1)), "text": text, "page": page})
            elif style == "Title" and text:
                blocks.append({"kind": "heading", "level": 0, "text": text, "page": page})
            elif text:
                blocks.append({"kind": "text", "level": 0, "text": text, "page": page})
        elif el.tag == qn("w:tbl"):
            table = Table(el, d)
            rows = [" | ".join(c.text.strip() for c in r.cells) for r in table.rows]
            if rows:
                blocks.append({"kind": "text", "level": 0, "text": "\n".join(rows), "page": page})
    title_blocks = [b for b in blocks if b["kind"] == "heading" and b["level"] == 0]
    chapters, method = _blocks_to_chapters([b for b in blocks if b["level"] != 0 or b["kind"] != "heading"],
                                          has_pages=True)
    cp = d.core_properties
    return {
        "title": (cp.title or (title_blocks[0]["text"] if title_blocks else "")).strip(),
        "author": (cp.author or "").strip(),
        "metadata_year": str(cp.created.year) if cp.created else "",
        "page_count": page, "split_method": method, "ocr": False, "extractor": "python-docx",
        "page_labels": "approximate (from page breaks)" if breaks else "none (docx has no fixed pages)",
        "chapters": chapters,
    }


def extract_html(path: Path) -> dict:
    from bs4 import BeautifulSoup
    raw = path.read_bytes().decode("utf-8", "replace")
    title, author, html = "", "", raw
    try:
        from readability import Document
        doc = Document(raw)
        title = doc.short_title() or doc.title() or ""
        html = doc.summary(html_partial=True)
    except Exception:  # noqa: BLE001 - readability is optional
        pass
    full = BeautifulSoup(raw, "html.parser")
    am = full.find("meta", attrs={"name": re.compile("^(author|citation_author|dc.creator)$", re.I)})
    if am and am.get("content"):
        author = am["content"].strip()
    if not title and full.title:
        title = full.title.get_text(" ", strip=True)
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre", "tr"]):
        if el.find_parent(["li", "blockquote", "tr"]) and el.name in ("p",):
            continue
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name[0] == "h":
            blocks.append({"kind": "heading", "level": int(el.name[1]), "text": text, "page": 1})
        elif el.name == "li":
            blocks.append({"kind": "text", "level": 0, "text": "- " + text, "page": 1})
        elif el.name == "tr":
            cells = [c.get_text(" ", strip=True) for c in el.find_all(["td", "th"])]
            blocks.append({"kind": "text", "level": 0, "text": " | ".join(cells), "page": 1})
        elif el.name == "blockquote":
            blocks.append({"kind": "text", "level": 0, "text": "> " + text, "page": 1})
        else:
            blocks.append({"kind": "text", "level": 0, "text": text, "page": 1})
    if not blocks:
        txt = clean_text(root.get_text("\n", strip=True))
        blocks = [{"kind": "text", "level": 0, "text": txt, "page": 1}] if txt else []
    if not blocks:
        raise IngestError("empty", "No readable text found on that page.")
    # h1 is usually the page title: split on the next level down
    if sum(1 for b in blocks if b["kind"] == "heading" and b["level"] == 1) == 1:
        blocks = [b for b in blocks if not (b["kind"] == "heading" and b["level"] == 1)]
    chapters, method = _blocks_to_chapters(blocks, has_pages=False)
    url_file = path.with_suffix(".url")
    return {
        "title": title.strip(), "author": author, "metadata_year": "",
        "page_count": 0, "split_method": method, "ocr": False, "extractor": "readability+bs4",
        "page_labels": "none (web page)", "chapters": chapters,
        "source_url": url_file.read_text(encoding="utf-8").strip() if url_file.exists() else "",
    }


def extract_text(path: Path) -> dict:
    raw = path.read_bytes().decode("utf-8", "replace")
    blocks, page = [], 1
    has_ff = "\f" in raw
    for chunk in re.split(r"(\f)|\n\s*\n", raw):
        if chunk is None:
            continue
        if chunk == "\f":
            page += 1
            continue
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        m = re.match(r"^(#{1,6})\s+(.+)$", chunk.strip())
        if m and "\n" not in chunk.strip():
            blocks.append({"kind": "heading", "level": len(m.group(1)), "text": m.group(2).strip(), "page": page})
        else:
            blocks.append({"kind": "text", "level": 0, "text": chunk.strip(), "page": page})
    if not blocks:
        raise IngestError("empty", "The file is empty.")
    chapters, method = _blocks_to_chapters(blocks, has_pages=has_ff)
    first_head = next((b["text"] for b in blocks if b["kind"] == "heading"), "")
    return {
        "title": first_head, "author": "", "metadata_year": "",
        "page_count": page if has_ff else 0, "split_method": method, "ocr": False, "extractor": "text",
        "page_labels": "form feeds" if has_ff else "none (plain text)", "chapters": chapters,
    }


# ------------------------------------------------------------- ids/meta

def guess_id(path: Path, info: dict | None) -> str:
    if info:
        author = info.get("author") or ""
        year = info.get("metadata_year") or ""
        words = [w for w in re.findall(r"[A-Za-z]{4,}", info.get("title") or "")
                 if w.lower() not in {"with", "from", "that", "this", "their", "into", "report", "paper"}]
        last = re.findall(r"[A-Za-z]+", author.split(",")[0].split(";")[0])
        if last and year and words:
            return slugify(f"{last[-1]}-{year}-{words[0]}", 50)
    return slugify(path.stem, 50)


def find_duplicate(text_root: Path, digest: str, skip_id: str | None) -> str | None:
    if not text_root.is_dir():
        return None
    for meta in text_root.glob("*/_meta.json"):
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if m.get("sha256") == digest and meta.parent.name != skip_id:
            return meta.parent.name
    return None


def extract(path: Path) -> dict:
    ext = path.suffix.lower()
    with open(path, "rb") as f:
        head = f.read(5)
    if ext == ".pdf" or head == b"%PDF-":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext in (".html", ".htm"):
        return extract_html(path)
    if ext in (".txt", ".md", ".markdown"):
        return extract_text(path)
    if ext == ".doc":
        raise IngestError("unsupported", "Old .doc Word files aren't supported. Open it in Word and save as .docx.")
    raise IngestError("unsupported", f"Unsupported file type: {ext or 'unknown'}")


def store_original(src: Path, pdf_dir: Path, source_id: str, mode: str) -> Path:
    if mode == "none":
        return src
    pdf_dir.mkdir(parents=True, exist_ok=True)
    try:
        if src.resolve().parent == pdf_dir.resolve():
            return src
    except OSError:
        pass
    dest = pdf_dir / f"{source_id}{src.suffix.lower()}"
    if dest.exists() and sha256(dest) == sha256(src):
        if mode == "move" and src.resolve() != dest.resolve():
            src.unlink()  # identical copy already stored; move == drop the duplicate
        return dest
    k = 2
    while dest.exists():
        dest = pdf_dir / f"{source_id}-{k}{src.suffix.lower()}"
        k += 1
    if mode == "move":
        shutil.move(str(src), str(dest))
        sidecar = src.with_suffix(".url")
        if sidecar.exists():
            shutil.move(str(sidecar), str(dest.with_suffix(".url")))
    else:
        shutil.copy2(src, dest)
    return dest


# ------------------------------------------------------------------ main

def run(args) -> dict:
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    refs = root / "references"
    text_root, pdf_dir, inbox = refs / "text", refs / "pdf", refs / "inbox"

    store = args.store
    if is_url(args.input):
        src = download(args.input, inbox)
        if store == "copy":
            store = "move"  # the downloaded file is ours; move it out of the inbox
    else:
        src = Path(os.path.expanduser(args.input.strip().strip("'\""))).resolve()
        if not src.exists():
            raise IngestError("not_found", f"File not found: {src}")
        if src.is_dir():
            raise IngestError("is_directory", "That is a folder, not a file.")

    digest = sha256(src)
    if args.check_only:
        return {"ok": True, "check_only": True, "input": src.name,
                "duplicate_of": find_duplicate(text_root, digest, None)}

    dup = find_duplicate(text_root, digest, args.id)
    if dup and not args.force:
        return {"ok": False, "error": "duplicate", "duplicate_of": dup,
                "message": f"This exact file is already in the library as '{dup}'. Use --force to ingest anyway."}

    source_id = slugify(args.id, 60) if args.id else None
    out_dir = text_root / source_id if source_id else None
    if out_dir and (out_dir / "_meta.json").exists() and not args.force:
        old = json.loads((out_dir / "_meta.json").read_text(encoding="utf-8"))
        if old.get("sha256") == digest:
            stored = store_original(src, pdf_dir, source_id, store)
            return {"ok": True, "status": "unchanged", "id": source_id, "title": old.get("title", ""),
                    "author": old.get("author", ""), "pages": old.get("page_count"),
                    "split": old.get("split_method"), "ocr": old.get("ocr", False),
                    "chapters": [{k: c[k] for k in ("file", "title", "pages")} for c in old.get("chapters", [])],
                    "text_dir": rel(out_dir, root), "original": rel(stored, root)}

    info = extract(src)
    if not source_id:
        source_id = guess_id(src, info)
        out_dir = text_root / source_id
    status = "updated" if (out_dir / "_meta.json").exists() else "created"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("[0-9][0-9]-*.md"):
        old.unlink()  # only our own generated chapter files

    chapters_meta = []
    for i, ch in enumerate(info["chapters"], start=1):
        fname = f"{i:02d}-{slugify(ch['title'])}.md"
        header = f"# {ch['title']}\n\n<!-- source: {source_id}" + (f" | pages {ch['pages']}" if ch["pages"] else "") + " -->\n\n"
        (out_dir / fname).write_text(header + ch["body"].strip() + "\n", encoding="utf-8")
        words = len(ch["body"].split())
        chapters_meta.append({"file": fname, "title": ch["title"], "pages": ch["pages"], "words": words})

    stored = store_original(src, pdf_dir, source_id, store)
    now = dt.datetime.now().isoformat(timespec="seconds")
    meta = {
        "id": source_id,
        "title": info["title"] or src.stem,
        "author": info["author"],
        "metadata_year": info["metadata_year"],
        "page_count": info["page_count"],
        "page_labels": info["page_labels"],
        "split_method": info["split_method"],
        "ocr": info["ocr"],
        "extractor": info["extractor"],
        "source_file": src.name,
        "source_url": info.get("source_url") or (args.input if is_url(args.input) else ""),
        "original": rel(stored, root),
        "sha256": digest,
        "chapters": chapters_meta,
        "ingested": now,
    }
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total_words = sum(c["words"] for c in chapters_meta)
    return {
        "ok": True, "status": status, "id": source_id, "title": meta["title"], "author": meta["author"],
        "pages": meta["page_count"], "words": total_words, "split": meta["split_method"], "ocr": meta["ocr"],
        "chapters": [{k: c[k] for k in ("file", "title", "pages")} for c in chapters_meta],
        "text_dir": rel(out_dir, root), "original": rel(stored, root),
        "warning": "very little text extracted" if total_words < 50 else None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="file path or http(s) URL")
    ap.add_argument("--id", help="source-id, e.g. fsb-2023-nbfi")
    ap.add_argument("--store", choices=["copy", "move", "none"], default="copy",
                    help="put the original into references/pdf (default: copy; original stays where it was)")
    ap.add_argument("--check-only", action="store_true", help="only report whether this file is already in the library")
    ap.add_argument("--force", action="store_true", help="re-ingest even if unchanged or a duplicate")
    ap.add_argument("--list-downloads", action="store_true", help="list recent files in ~/Downloads")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--root", help="project root (default: folder above scripts/)")
    args = ap.parse_args(argv)

    try:
        if args.list_downloads:
            result = list_downloads(args.limit)
        elif not args.input:
            result = {"ok": False, "error": "no_input", "message": "Give a file path or URL."}
        else:
            result = run(args)
    except IngestError as e:
        result = {"ok": False, "error": e.code, "message": e.message}
    except ImportError as e:
        result = {"ok": False, "error": "missing_dependency",
                  "message": f"{e}. Run scripts/setup.sh to install the helper tools."}
    except Exception as e:  # noqa: BLE001 - always answer in one JSON line
        result = {"ok": False, "error": "unexpected", "message": f"{type(e).__name__}: {e}"}
    emit({k: v for k, v in result.items() if v is not None})
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
