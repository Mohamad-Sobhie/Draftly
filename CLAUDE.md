# Draftly - thesis assistant project

This folder is a master's student's thesis workspace. The student is **not technical**: they talk in plain language and never run commands or edit files themselves.

## Rules for Claude

- For **any** thesis work (brainstorming, discussing viewpoints, drafting, sources, library, status, "menu", "help"), use the **draftly** skill (`.claude/skills/draftly/SKILL.md`) and follow it.
- Reply in plain words. Never show file paths, commands, script output or error traces to the student. Say "I added the book to your library", not where you put it.
- Never invent references, page numbers, DOIs, cases or legislation. Use `[CITATION NEEDED: ...]` / `[PINPOINT NEEDED]` instead.
- Never delete the student's files. Drafts are versioned (`-v1`, `-v2`, ...) and never overwritten.
- Run helper scripts with the project virtual environment: `.venv/bin/python scripts/<name>.py` (Windows: `.venv\Scripts\python.exe`).
- Read `references/INDEX.md` and `notes/` before opening any full source text.

## Thesis brief

The filled-in brief lives in `thesis-brief.md` (kept private, not in the template repo). It is imported here:

@thesis-brief.md

If `thesis-brief.md` does not exist yet, run **Setup** from the skill and create it from this template:

```markdown
# Thesis brief

- Student name (optional):
- Field / subject:
- University and programme:
- Working title:
- Research question(s):
  1.
- Method:
- Thesis language: English
- Citation style: OSCOLA
- Stage:
- Deadline (YYYY-MM-DD):
- Word limit (footnotes counted?):
- University AI-use rules:
- AI-use declaration required: yes | no | unclear

## Outline
<!-- Written by "/draftly outline". One line per chapter or section: "- 3 Title · 4,000 words · RQ1, RQ2 · purpose", sections indented as "  - 3.1 Title · 1,500 words · RQ1 · purpose". Only the number and title are required. The library page and Status use these numbers. -->

## Key terms and definitions

## Supervisor feedback / decisions log

## Bibliography
<!-- Optional. Longer bibliographies go in references/bibliography.md (one "- " entry per line). -->
```

### Defaults for the first user (change freely)
Field: law (LLM) · Topic area: UK/EU bank regulation and systemic risk from non-bank financial intermediaries (NBFIs) · Citation style: OSCOLA · Discuss preset: "Law - financial regulation".
