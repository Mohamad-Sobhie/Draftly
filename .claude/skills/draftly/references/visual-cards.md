# In-chat visual cards (Discuss)

Discuss output is shown **inside the chat** as coloured cards, using the Claude app's built-in visual tool (`show_widget`, from the `visualize` tools). The student never has to open a browser.

## Rules

- **Once per session, before the first card,** call the visual tool's `read_me` (module `mockup`) silently. Never mention it.
- One `show_widget` call per stage. Give it a specific `title` (e.g. `discuss_nbfi_perspectives`, `discuss_nbfi_fight_map`).
- The tool's own rules apply: no emoji inside the widget, sentence case, font weights 400/500 only, colours only through CSS variables (they adapt to dark mode), no big headings inside the widget (use the small `.pl` labels).
- Keep the fixed colour per perspective (the chat emoji in the text match):

| Perspective | Accent `--a` | Tint `--t` | Icon | Chat emoji |
|---|---|---|---|---|
| practitioner | `var(--text-tint-blue)` | `var(--bg-tint-blue)` | `ti-tool` | 🟦 |
| skeptic | `var(--text-tint-red)` | `var(--bg-tint-red)` | `ti-help` | 🟥 |
| economist | `var(--text-tint-green)` | `var(--bg-tint-green)` | `ti-coin-pound` (`ti-coin` outside the UK) | 🟩 |
| historian | `var(--text-tint-yellow)` | `var(--bg-tint-yellow)` | `ti-hourglass` | 🟨 |
| academic | `var(--text-tint-violet)` | `var(--bg-tint-violet)` | `ti-books` | 🟪 |
| extra (schools of thought) | `aqua`, `magenta`, `orange` tints in that order | | `ti-scale`, `ti-building-bank`, `ti-flag` | ◻️ |

- Source tags: library-backed → class `ok` (`var(--bg-success)` / `var(--text-success)`), text `source-id, pinpoint`. Gap → class `nd` (`var(--bg-warning)` / `var(--text-warning)`), text `needs: kind of source` or `not in your library yet`. Only sources that are in INDEX.md may get an `ok` tag.
- **No buttons.** Clickable buttons (`sendPrompt`) don't work in the Claude Code app, so never add any. Next steps go in the reply's *Next:* line instead.
- **Everything goes in the cards; nothing is repeated in text.** The reply around a widget is exactly:
  1. one short intro line before it (e.g. "Here's your question through the five perspectives:"), and
  2. one *Next:* line after it (e.g. *Next: map where they fight · write the briefing · play the examiner*).
  Never restate, summarise or list the cards' content in text - the student sees it once, in the cards. (The tool itself warns against duplicating what it shows.)
- **If the visual tool isn't available** (e.g. the terminal version of Claude Code), give the same content as markdown with the chat emoji per perspective (layout in SKILL.md) - never paste raw HTML into the reply.

## Shared style block (start every widget with this)

```html
<h2 class="sr-only">ONE-SENTENCE SUMMARY OF THE WIDGET</h2>
<style>
.pc{background:var(--surface-2);border:0.5px solid var(--border);border-radius:12px;padding:14px 18px;margin:0 0 10px;position:relative;overflow:hidden}
.pc::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--a)}
.ph{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.pi{width:28px;height:28px;border-radius:8px;background:var(--t);color:var(--a);display:flex;align-items:center;justify-content:center;font-size:16px}
.pn{font-weight:500;font-size:15px}
.pt{margin-left:auto;font-size:13px;font-style:italic;color:var(--text-secondary)}
.pl{font-size:11px;letter-spacing:.04em;color:var(--a,var(--text-secondary));font-weight:500;margin:10px 0 2px}
.pc p,.bx p{margin:0;font-size:14px;line-height:1.6}
.pc ul,.bx ul,.bx ol{margin:2px 0 0;padding-left:18px;font-size:14px;line-height:1.6}
.tg{display:inline-block;font-size:12px;padding:0 8px;border-radius:6px;margin-left:4px}
.ok{background:var(--bg-success);color:var(--text-success)}
.nd{background:var(--bg-warning);color:var(--text-warning)}
.os{background:var(--t);border-radius:8px;padding:8px 12px;margin-top:10px}
.os p{color:var(--a)}
.bx{background:var(--surface-2);border:0.5px solid var(--border);border-radius:12px;padding:12px 16px;margin:0 0 10px}
.ch{display:inline-block;font-size:12px;padding:1px 9px;border-radius:999px;background:var(--t);color:var(--a);font-weight:500}
.dt{display:inline-block;width:10px;height:10px;border-radius:3px;background:var(--a);margin-right:3px}
.row{display:flex;gap:12px;padding:8px 0;border-bottom:0.5px solid var(--border);align-items:flex-start}
.row:last-child{border-bottom:none}
.g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
</style>
<div style="padding:.5rem 0">
  ... stage content ...
</div>
```

## Stage 1 · perspective card (repeat for each of the five)

```html
<div class="pc" style="--a:var(--text-tint-blue);--t:var(--bg-tint-blue)">
  <div class="ph"><div class="pi"><i class="ti ti-tool" aria-hidden="true"></i></div>
    <div class="pn">The practitioner</div><div class="pt">has done the job</div></div>
  <div class="pl">Core position</div><p>...</p>
  <div class="pl">Strongest evidence</div>
  <ul><li>Claim <span class="tg ok">fsma-2023, s 25</span></li>
      <li>Claim <span class="tg nd">needs: Bank of England report on 2022</span></li></ul>
  <div class="os"><div class="pl" style="margin-top:0">Only they'd say</div><p>...</p></div>
</div>
```
After the five cards, in the **same** widget:

```html
<div class="bx"><div class="pl">Where they clash</div>
  <div class="row"><div style="white-space:nowrap;padding-top:4px"><span class="dt" style="--a:var(--text-tint-blue)"></span><span class="dt" style="--a:var(--text-tint-red)"></span></div>
    <p><span style="font-weight:500">Practitioner vs skeptic:</span> ...</p></div>
</div>
<div class="bx"><div class="pl">What this means for your thesis</div><p>...</p></div>
<div class="bx"><div class="pl">Likely examiner questions</div><ol><li>...</li></ol></div>
```
Next line: *Next: map where they fight · write the briefing · play the examiner*.

## Stage 2 · fight map

```html
<div class="bx"><div class="pl">Direct contradictions</div>
  <div class="row"><div style="white-space:nowrap;padding-top:4px"><span class="dt" style="--a:var(--text-tint-red)"></span><span class="dt" style="--a:var(--text-tint-blue)"></span></div>
    <p><span style="font-weight:500">Skeptic vs practitioner:</span> ...</p></div>
</div>
<div class="g2">
  <div class="bx" style="border-top:3px solid var(--text-success);border-radius:0 0 12px 12px"><div class="pl">Strongest evidence</div>
    <span class="ch" style="--a:var(--text-tint-green);--t:var(--bg-tint-green)">Economist</span><p style="margin-top:6px">why ...</p></div>
  <div class="bx" style="border-top:3px solid var(--text-danger);border-radius:0 0 12px 12px"><div class="pl">Weakest evidence</div>
    <span class="ch" style="--a:var(--text-tint-yellow);--t:var(--bg-tint-yellow)">Historian</span><p style="margin-top:6px">why ...</p></div>
  <div class="bx"><div class="pl">What they all agree on</div><ul><li>...</li></ul></div>
  <div class="bx"><div class="pl">What nobody addressed</div><ul><li>To check: ...</li></ul></div>
</div>
```
Next line: *Next: write the briefing · debate the two strongest*.

## Stage 3 · briefing

```html
<div class="bx"><div class="pl">Supervisor summary</div><p>one paragraph</p></div>
<div class="bx"><div class="pl">Key findings · ranked by reliability</div>
  <div class="row">
    <div style="width:22px;height:22px;border-radius:50%;background:var(--text-primary);color:var(--surface-2);font-size:12px;display:flex;align-items:center;justify-content:center;flex:none">1</div>
    <div style="flex:1"><p>finding</p><span class="ch" style="--a:var(--text-tint-green);--t:var(--bg-tint-green)">Economist</span></div>
    <div style="font-size:12px;font-weight:500;color:var(--text-success)">High</div>
  </div>
  ... (Medium → var(--text-warning), Low → var(--text-danger))
</div>
<div class="bx" style="border-left:3px solid var(--text-tint-violet);border-radius:0"><div class="pl">Hidden connection</div><p>...</p></div>
<div class="bx" style="border-left:3px solid var(--text-success);border-radius:0;background:var(--bg-success)"><div class="pl">One thing to change in your thesis</div><p>...</p></div>
```
"High" only when a library source backs the finding; otherwise Medium at most. Next line: *Next: grade your work · draft the section*.

## Stage 4 · peer review

```html
<div class="bx"><div class="pl">Confidence per finding</div>
  <div class="row"><div style="flex:1"><p>1. finding (short)</p><p style="font-size:12px;color:var(--text-secondary)">why</p></div>
    <div style="display:flex;align-items:center;gap:8px"><div style="width:100px;height:6px;border-radius:3px;background:var(--border)"><div style="width:90%;height:6px;border-radius:3px;background:var(--text-primary)"></div></div><span style="font-size:12px;font-weight:500">9/10</span></div></div>
</div>
<div class="bx" style="border-left:3px solid var(--text-danger);border-radius:0"><div class="pl">Weakest claim</div><p style="font-weight:500">...</p><p style="color:var(--text-secondary)">Why: ... · Fix: ...</p></div>
<div class="bx"><div class="pl">Bias check · whose voice shaped the findings</div>
  <div style="display:flex;height:10px;border-radius:5px;overflow:hidden;gap:2px;margin:8px 0">
    <div style="flex:2;background:var(--text-tint-green)"></div><div style="flex:1;background:var(--text-tint-red)"></div> ...
  </div>
  <p>Economist drives 2 of 5 findings ... Not represented: Academic.</p>
</div>
```
Count the bar segments from the briefing's findings (one per finding, by perspective); flag any perspective behind 40%+ and name any that's missing. Scores: no library source → 6 at most; pure pattern or opinion → 4 at most.

## Outline (table of contents)

One card per chapter; sections as rows inside it. Use a neutral accent (`--a:var(--text-secondary)`) for chapters - the perspective colours are reserved for Discuss. When showing two alternative structures, put a small label above each set ("Structure A · thematic", "Structure B · comparative") using `.pl`, and one line on what each is good for inside a `.bx` above its chapters.

```html
<div class="pc" style="--a:var(--text-secondary);--t:var(--surface-1)">
  <div class="ph"><div class="pi" style="font-size:13px;font-weight:500">3</div>
    <div class="pn">Regulating through banks</div><div class="pt">4,500 words · RQ1</div></div>
  <p style="color:var(--text-secondary)">one-line purpose of the chapter</p>
  <div class="row"><div style="width:34px;font-size:13px;color:var(--text-secondary)">3.1</div>
    <div style="flex:1"><p>Entity-based tools</p><p style="font-size:12px;color:var(--text-secondary)">bank exposure limits and reporting</p></div>
    <div style="text-align:right;white-space:nowrap"><div style="font-size:12px">2,500 w</div><span class="tg ok">2 sources</span></div></div>
  <div class="row"><div style="width:34px;font-size:13px;color:var(--text-secondary)">3.2</div>
    <div style="flex:1"><p>Limits of the approach</p></div>
    <div style="text-align:right;white-space:nowrap"><div style="font-size:12px">2,000 w</div><span class="tg nd">needs: 2022 LDI analysis</span></div></div>
</div>
```

Budget bar (once, under the chapters) - one segment per chapter, proportional to its budget, with the total vs the limit:

```html
<div class="bx"><div class="pl">Word budget · 15,000 of 15,000</div>
  <div style="display:flex;height:10px;border-radius:5px;overflow:hidden;gap:2px;margin:8px 0">
    <div style="flex:1500;background:var(--border-strong)"></div><div style="flex:3000;background:var(--text-secondary)"></div> ...
  </div>
  <p style="font-size:13px;color:var(--text-secondary)">1 Intro 1,500 · 2 Risk 3,000 · 3 Banks 4,500 · 4 Backstops 4,000 · 5 Conclusion 2,000</p>
</div>
```

Checks card (only if there's something to flag), with `.nd` tags: "RQ3 has no section", "Chapter 2's sections add up to 3,500 of 3,000 words", "No comparison chapter for a comparative question".

When editing, mark changed rows with a small tag before the title: `<span class="tg nd">changed</span>`, `<span class="tg ok">new</span>`, `<span class="tg" style="background:var(--bg-danger);color:var(--text-danger)">removed</span>` (keep removed rows, struck through: `style="text-decoration:line-through;color:var(--text-secondary)"`), and show renumbering as "2.2 → 3.1" in the number column.

*Next:* line: creating → *Next: "use A" / "use B" · or tell me what to change*; editing → *Next: "go" to save · or tell me what else to change*.
