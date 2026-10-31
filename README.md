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
| `.claude/skills/draftly/` | The skill: `SKILL.md` + `references/perspectives.md` (the five Discuss lenses and the schools-of-thought presets) and `references/citation-styles.md` (OSCOLA, APA 7, Harvard). |
| `.claude/settings.json` | Pre-approved permissions so the student isn't flooded with prompts. |
| `scripts/ingest.py` | PDF / scanned PDF / .docx / web page / text → page-marked, chapter-split markdown. |
| `scripts/build_library.py` | `references/INDEX.md` → `library.html` (offline, searchable, with a gap panel). |
| `scripts/style_check.py` | Counts writing-style problems in a draft (stock phrases, inflated words, em dashes, restating endings, monotone rhythm). |
| `scripts/build_discussion.py` | Checks a Discuss session (JSON) against the library and writes a printable copy (HTML) in `sessions/`; the cards themselves appear in the chat. |
| `scripts/setup.sh` | One-time setup + self-test. `scripts/selftest.py --full` runs the extended test. |
| `references/INDEX.md` | The library map Claude maintains. |
| `references/inbox/` | Drop files here to have Claude add them. |
| `references/pdf/`, `references/text/` | Original files and extracted text (git-ignored). |
| `notes/`, `sessions/`, `drafts/` | Reading notes, brainstorm/discussion records, versioned drafts (git-ignored). |
| `My Thesis Drafts/` | The student's own Word document. Read-only for Claude; Draftly's exports go in as new files with "Draftly" in the name (git-ignored). |
| `scripts/thesis_doc.py` | Reads the student's Word document (headings, words, sections, footnotes), syncs it with the outline, exports drafts to `.docx`. |
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

**Option A: one command with npx** (needs [Node.js](https://nodejs.org) 18+; no git needed)

```bash
npx github:Mohamad-Sobhie/Draftly my-thesis
```

Once the package is published to npm, this also works: `npx create-draftly my-thesis` (or `npm init draftly my-thesis`).

It creates the `my-thesis` folder, copies the template in and runs the setup below. Pointing it at an **existing** folder (e.g. one that already holds the student's abstract) adds Draftly without touching any file that's already there. `--no-setup` copies the files only.

**Option B: git** (makes updates a simple `git pull`)

```bash
git clone https://github.com/Mohamad-Sobhie/Draftly.git draftly
cd draftly
bash scripts/setup.sh
```

To add Draftly to an existing folder with git: `git init -b main && git remote add origin https://github.com/Mohamad-Sobhie/Draftly.git && git pull origin main`, then `bash scripts/setup.sh`.

The setup script creates a local `.venv`, installs the Python packages, checks for poppler/tesseract (prints install hints, doesn't fail without them), creates any missing folders, and runs a self-test (it generates a tiny PDF, ingests it, builds a library page, checks the result, then cleans up). It ends with: *Open this folder in Claude Code and type menu*.

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

**Installed with npx:** from the folder that contains the thesis folder:

```bash
npx "github:Mohamad-Sobhie/Draftly#main" my-thesis --update
```

It replaces only the skill, scripts, settings, `CLAUDE.md` and `README.md`, then re-runs the setup. The library, notes, sessions, drafts, thesis brief and `settings.local.json` are never touched. (The `#main` makes npx fetch the latest version rather than a cached one; keep the quotes, since some shells treat `#` as a comment.)

**Installed with git:** from the student's folder:

```bash
git pull
bash scripts/setup.sh
```

(If they use a private copy, add this template as a second remote: `git remote add template https://github.com/Mohamad-Sobhie/Draftly.git`, then `git pull template main`.) Their brief, library, notes and drafts are git-ignored, so updates never touch them. Re-running `setup.sh` is safe.

To customise: edit `.claude/skills/draftly/SKILL.md` (keep it under ~500 lines), add field presets to `references/perspectives.md`, citation rules to `references/citation-styles.md`, or change the house style in `references/writing-style.md`.

### Publishing the npx installer (optional)

The repo is also the npm package `create-draftly` (`package.json` + `bin/create-draftly.js`). To publish a version: bump `version` in `package.json`, run `npm publish` (needs an npm account; `npm login` first). `npx github:...` works without publishing. npm never ships `.gitignore`, so the installer carries its own copy; the self-test checks it still matches the repo's `.gitignore`.

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

### The six things it does

1. 💡 **Brainstorm**: ideas, angles, research questions and possible gaps. *"Brainstorm angles for chapter 3."*
2. ⚖️ **Discuss**: your topic through five lenses: 🟦 the Practitioner, 🟥 the Skeptic, 🟩 the Economist, 🟨 the Historian and 🟪 the Academic. You see where they clash and what examiners might ask, shown as colour-coded cards right in the chat. Say *"save it as a page"* if you want a copy to keep or print. *"Discuss whether NBFIs should be regulated directly."* You can also say *"debate the Skeptic and the Historian"*, *"play the examiner"*, or *"use schools of thought instead"*.

   Then take it further, step by step (each step appears as new cards in the chat):
   - ⚔️ *"Map where they fight"*: direct contradictions, the strongest and weakest evidence, what they all agree on, and what nobody addressed.
   - 📋 *"Write the briefing"*: a one-paragraph summary for your supervisor, five key findings ranked by reliability, one hidden connection, and one thing to change in your thesis.
   - 🔍 *"Grade your work"*: a 1–10 confidence score per finding, the weakest claim and how to fix it, and a bias check showing which lens dominated.
3. ✍️ **Write**: turns **your** points into a draft, or polishes your own text. *"Here are my points for 3.2, draft it."* Before writing, Claude shows a short plan (one line per paragraph, with the sources it will use) and waits for you to say **go**. Every draft is saved as a new version, so nothing is lost, and opens beside the chat so you can read it while you talk. Drafts are written plainly and precisely, without AI-sounding filler, and each one ends with a short style check.
4. 📚 **Library**: your sources. *"What do my sources say about liquidity mismatch?"*
5. 📋 **Status**: where you are, what's missing, what to do next. *"Where am I?"*
6. 🗂️ **Outline**: plans your table of contents from your abstract (two options, with word budgets and which sources cover each section), and lets you change it any time. Type *"/draftly outline"* again later and it opens your outline as an editable board: change titles and word budgets, move, add or remove sections, then copy your changes into the chat. You can also just say *"merge 2.1 and 2.2"*.

You don't have to use the menu: just say what you need. Type **/draftly help** for the basics, or **/draftly help all** for everything you can ask, with examples.

### Your own Word document

Write your thesis in Word as usual, and keep the file in the **My Thesis Drafts** folder inside your thesis folder. Draftly only **reads** it and never changes it. Then you can ask:
- *"How many words have I written?"*: per chapter, against your outline.
- *"Review 2.2 in my thesis"*: feedback on what you wrote.
- *"Polish 2.2 from my thesis"*: a cleaned-up copy as a new Word file, so you can choose what to take.
- *"Sync my outline"*: if you renamed or added sections in Word, Draftly spots it and updates your outline (after you say go).

Use Word's **Heading 1** for chapters and **Heading 2** for sections so Draftly can follow your structure.

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
