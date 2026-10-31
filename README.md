# Draftly

A Claude Code project folder that turns Claude into a thesis assistant for a master's student: brainstorming, discussing viewpoints, drafting from the student's own points, and keeping a searchable library of sources with page-accurate citations.

The student never runs commands or edits files. They open the folder in Claude Code and talk in plain language; Claude does the file work and replies in plain words.

Defaults are set for a UK law student (LLM) writing on UK/EU bank regulation and systemic risk from non-bank financial intermediaries (NBFIs), with OSCOLA citations. Everything is configurable for any field during the first-run setup.

- [Part 1: Setup guide (for the setup person)](#part-1-setup-guide-for-the-setup-person)
- [Part 2: Student guide (one page)](#part-2-student-guide)

---

## Part 1: Setup guide (for the setup person)

### What's inside

| Path | What it is |
|---|---|
| `CLAUDE.md` | Project rules for Claude + the thesis brief template. Imports `thesis-brief.md`. |
| `thesis-brief.md` | The student's filled brief (created at first run, git-ignored). |
| `.claude/skills/draftly/` | The skill: `SKILL.md` + `references/perspectives.md` (Discuss presets) and `references/citation-styles.md` (OSCOLA, APA 7, Harvard). |
| `.claude/settings.json` | Pre-approved permissions so the student isn't flooded with prompts. |
| `scripts/ingest.py` | PDF / scanned PDF / .docx / web page / text → page-marked, chapter-split markdown. |
| `scripts/build_library.py` | `references/INDEX.md` → `library.html` (offline, searchable, with a gap panel). |
| `scripts/build_discussion.py` | Discuss session (JSON) → colour-coded perspectives board (HTML) in `sessions/`. |
| `scripts/setup.sh` | One-time setup + self-test. `scripts/selftest.py --full` runs the extended test. |
| `references/INDEX.md` | The library map Claude maintains. |
| `references/inbox/` | Drop files here to have Claude add them. |
| `references/pdf/`, `references/text/` | Original files and extracted text (git-ignored). |
| `notes/`, `sessions/`, `drafts/` | Reading notes, brainstorm/discussion records, versioned drafts (git-ignored). |
| `library.html` | Generated library page (git-ignored). |

### Prerequisites

- [Claude Code](https://claude.com/claude-code) (desktop app or CLI) signed in on the student's machine.
- Python 3.10 or newer.
- Optional but recommended:
  - **poppler** (cleaner PDF text): macOS `brew install poppler` · Windows `winget install oschwartz10612.Poppler`
  - **tesseract** (reading scanned PDFs): macOS `brew install tesseract` · Windows `winget install UB-Mannheim.TesseractOCR`
  - **ocrmypdf** (best OCR): macOS `brew install ocrmypdf`
- Windows: run `setup.sh` from **Git Bash** (comes with Git for Windows) or WSL.

### Install (once, on the student's machine)

```bash
git clone https://github.com/Mohamad-Sobhie/Draftly.git draftly
cd draftly
bash scripts/setup.sh
```

The script creates a local `.venv`, installs the Python packages, checks for poppler/tesseract (prints install hints, doesn't fail without them), creates any missing folders, and runs a self-test (it generates a tiny PDF, ingests it, builds a library page, checks the result, then cleans up). It ends with: *Open this folder in Claude Code and type menu*.

### First run (do this together with the student)

1. Open the `draftly` folder in Claude Code.
2. Type `menu`. Claude notices there's no thesis brief yet and asks the setup questions in one message (field, university, title, research questions, method, language, citation style, stage and deadline, word limit, AI-use rules, optional outline and bibliography).
3. Let the student answer in their own words. Claude writes `thesis-brief.md`.
   - Encourage them to give a numbered outline (e.g. `3.1 Entity-based regulation`). The library page uses it to show which sections have no sources yet.
   - If they have a reading list, paste it: Claude saves it as the bibliography and can run a bibliography check.
4. Add the first sources: drag 2-3 PDFs into the chat and say "add these", or put files in `references/inbox/` and say "add the new files".
5. Check that it worked:
   - `references/INDEX.md` has well-formed entries.
   - Open `library.html` in a browser (double-click it). Bookmark it for the student; they just refresh the tab after changes.
6. Show the student the menu and Part 2 below.

### Permissions (`.claude/settings.json`)

- Default mode `acceptEdits`: Claude can create and edit files inside the project without asking each time.
- Pre-approved: the helper scripts via the project `.venv` Python, reading/editing within the project, reading `~/Downloads` (added as an additional directory, so "the PDF I just downloaded" works), web search, and fetches from DOI/Crossref and the main UK/EU legal and regulator sites (for bibliography checks).
- Pre-approved too: opening `library.html` and discussion boards in the browser.
- Denied: `rm`, `sudo`, and editing anything in `~/Downloads`. The skill tells Claude never to edit its own `.claude/` or `scripts/` files.
- Claude Code only applies these project permissions once the folder is **trusted**: the first time you open it, accept the "trust this folder" prompt.
- Nothing destructive outside the project is pre-approved. Downloads are only read; the original file is copied by default.
- Machine-specific tweaks go in `.claude/settings.local.json` (git-ignored).

### Privacy and version history

The template repo never contains PDFs, extracted text, notes, drafts, the brief or the bibliography: they're all in `.gitignore`. Copyrighted sources must stay out of any public repo.

If the student wants version history of their own work, make a **private** copy:

1. Create a new **private** repository (e.g. on GitHub).
2. In the student's folder: `git remote set-url origin <private-repo-url>`.
3. Remove the lines for `notes/*`, `sessions/*`, `drafts/*`, `thesis-brief.md`, `references/bibliography.md` (and, only if the repo is private and they're comfortable with it, `references/pdf/*` and `references/text/*`) from `.gitignore`.
4. Commit and push to the private repo.

### Updating the skill later

From the student's folder:

```bash
git pull
bash scripts/setup.sh
```

(If they use a private copy, add this template as a second remote: `git remote add template https://github.com/Mohamad-Sobhie/Draftly.git`, then `git pull template main`.) Their brief, library, notes and drafts are git-ignored, so updates never touch them. Re-running `setup.sh` is safe.

To customise: edit `.claude/skills/draftly/SKILL.md` (keep it under ~500 lines), add field presets to `references/perspectives.md`, or citation rules to `references/citation-styles.md`.

### Script reference (for you, not the student)

```bash
.venv/bin/python scripts/ingest.py <file-or-url> --id fsb-2023-nbfi [--store copy|move|none] [--force]
.venv/bin/python scripts/ingest.py <file> --check-only     # duplicate check
.venv/bin/python scripts/ingest.py --list-downloads        # recent files in ~/Downloads
.venv/bin/python scripts/build_library.py
.venv/bin/python scripts/build_discussion.py sessions/<file>.json
.venv/bin/python scripts/selftest.py --full                # extended test with generated fixtures
```

`ingest.py` writes `references/text/<id>/NN-<slug>.md` with `[p. N]` markers at every page (printed page labels such as `iv` when the PDF has them) plus `_meta.json`. It splits by PDF bookmarks, otherwise by detected headings, otherwise every 15 pages, and cuts very long chapters into 15-page parts. Scanned PDFs are OCR'd if ocrmypdf or tesseract+poppler is installed. It is idempotent, never deletes the original, and always prints one JSON line.

---

## Part 2: Student guide

**Draftly is your thesis assistant.** You talk to it in normal sentences. It keeps your sources, notes and drafts organised for you.

### Opening it

Open the **Claude** app, go to **Code**, and open your **draftly** thesis folder. (Your setup person will show you once.) Then type **menu**.

### The five things it does

1. 💡 **Brainstorm**: ideas, angles, research questions and possible gaps. *"Brainstorm angles for chapter 3."*
2. ⚖️ **Discuss**: your topic through five lenses: 🟦 the Practitioner, 🟥 the Skeptic, 🟩 the Economist, 🟨 the Historian and 🟪 the Academic. You see where they clash and what examiners might ask, and Claude opens a colour-coded board in your browser that you can keep or print. *"Discuss whether NBFIs should be regulated directly."* You can also say *"debate the Skeptic and the Historian"*, *"play the examiner"*, or *"use schools of thought instead"*.

   Then take it further, step by step (each step is added to the same board):
   - ⚔️ *"Map where they fight"*: direct contradictions, the strongest and weakest evidence, what they all agree on, and what nobody addressed.
   - 📋 *"Write the briefing"*: a one-paragraph summary for your supervisor, five key findings ranked by reliability, one hidden connection, and one thing to change in your thesis.
   - 🔍 *"Grade your work"*: a 1–10 confidence score per finding, the weakest claim and how to fix it, and a bias check showing which perspective dominated.
3. ✍️ **Write**: turns **your** points into a draft, or polishes your own text. *"Here are my points for 3.2, draft it."* Every draft is saved as a new version, so nothing is lost.
4. 📚 **Library**: your sources. *"What do my sources say about liquidity mismatch?"*
5. 📋 **Status**: where you are, what's missing, what to do next. *"Where am I?"*

You don't have to use the menu: just say what you need.

### Adding a source

- **Drag a PDF into the chat** and say **"add it"**.
- Or say **"add the PDF I just downloaded"**.
- Or paste a **web link** and say **"add this"**.

Claude reads the important parts, files it in your library, and tells you what it's useful for.

### Seeing your library

Open **library.html** in your thesis folder (your setup person may have bookmarked it). You can search and filter your sources there, and see what's still missing. After Claude adds something, just **refresh** the page.

### Good to know

- **Claude never invents references.** If a source is missing, the draft says *[CITATION NEEDED]*; if a page number is missing, *[PINPOINT NEEDED]*. Still double-check the important references yourself before you submit.
- **You are the author.** Claude helps you think and write, but the argument is yours. If your university asks you to declare AI use, Claude will remind you.
- Your drafts, notes and sources stay on your computer.
