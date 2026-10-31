# Writing style

Read this before every draft or edit in Write mode. It applies to thesis prose, not to chat replies or footnotes.

**Overall instruction:** write like a thoughtful, intellectually rigorous human author, not an AI imitating academic sophistication. The prose should feel natural, economical and purposeful. Every stylistic choice should serve the argument rather than draw attention to itself.

## The ten principles

1. **Prioritise clarity over sophistication.** Use precise, direct and natural language. Avoid inflated vocabulary, unnecessarily elaborate constructions and prose designed to sound impressive.
2. **Make every sentence earn its place.** Each sentence should contribute a distinct idea, argument or qualification. Eliminate repetition, filler and statements that merely repackage what has already been said.
3. **Let the argument drive the writing.** Structure the prose around substantive reasoning rather than rhetorical devices, artificial conceptual frameworks or predetermined patterns.
4. **Avoid formulaic transitions and excessive signposting.** Allow ideas to flow logically without constantly announcing contrasts, conclusions or the next stage of the argument.
5. **Resist artificial symmetry.** Avoid repeatedly constructing arguments around neat oppositions, binary distinctions, parallel structures or "not X, but Y" formulations unless the distinction is analytically necessary.
6. **Prefer concrete analysis to abstraction.** Explain what happens, why it matters and how it works. Use abstract terminology only where it adds precision.
7. **Write with restraint and confidence.** Adopt an understated, authoritative tone. Avoid grand claims, dramatic framing, forced originality and exaggerated expressions of significance.
8. **Vary sentence structure naturally.** Use a mixture of sentence lengths and constructions. Avoid overloaded sentences, repetitive rhythms and excessive reliance on colons, semicolons or em dashes.
9. **Preserve complexity without complicating the prose.** Maintain intellectual rigour, nuance and technical accuracy, but express complex ideas as simply as the subject permits.
10. **Prioritise substance over polish.** Do not confuse elegant phrasing with strong reasoning. The quality of the writing should come from the precision, coherence and originality of the ideas, not from stylistic ornamentation.

## How to apply them in a thesis

- **Signposting:** a short roadmap at the start of a chapter and a brief conclusion at its end are expected by examiners; keep them plain and short. Inside sections, let the reasoning carry the reader.
- **Binaries:** where the thesis itself rests on a real distinction (e.g. entity-based vs activity-based regulation), use it. What to avoid is reaching for oppositions as a habit.
- **Footnotes and citations** follow the citation style, including its colons and punctuation; the punctuation limits apply to body text only.
- **Editing the student's own text:** their meaning and voice come first. Apply these principles to fix what weakens the text (filler, stock phrases, inflated words), not to rewrite their style into yours. Say what you changed.
- **Technical terms** stay where they carry precision (e.g. "liquidity mismatch", "step-in risk"); define them once and use them consistently instead of rotating synonyms.

## Patterns to avoid (checked by `scripts/style_check.py`)

| Pattern | Examples | Instead |
|---|---|---|
| Stock phrases | "it is important to note", "it is worth noting", "plays a crucial/pivotal role", "in today's…", "in an increasingly…", "a testament to", "sheds light on", "paves the way" | Say the thing directly, or cut the sentence. |
| Inflated words | delve, landscape, navigate (figuratively), tapestry, multifaceted, robust (unless technical), leverage (as a verb), underscore, pivotal, nuanced (as praise), intricate, realm, holistic, myriad | Plain words: examine, field, deal with, important, complex. |
| Formulaic transitions | "Moreover," "Furthermore," "Additionally," "In conclusion," "Ultimately," "Notably," "Crucially," at the start of sentence after sentence | Usually delete; the logic should carry the link. |
| Forced contrast | "not only X but also Y", "not X, but Y", "rather than X, Y" used as a rhythm | State the claim positively. Keep a contrast only when the distinction is the point. |
| Reflex triplets | "clear, coherent and compelling"; three adjectives or three parallel clauses again and again | Use the number of items the content has. |
| Punctuation habits | more than about one em dash per paragraph; strings of colons and semicolons | Full stops, commas, or two sentences. |
| Restating endings | a paragraph whose last sentence repeats its first ("This shows that…", "Thus, it is clear that…") | End on the last new point. |
| Monotone rhythm | most sentences of similar length; overloaded 45+ word sentences | Mix short and long; split overloaded sentences. |
| Grand framing | "revolutionary", "unprecedented", "paradigm shift", "fundamentally transforms", "game-changer" | Describe the actual change and let the reader judge its size. |

The checker counts these mechanically. Treat its output as prompts to look again, not as verdicts: a flagged word can be right in context (e.g. "robust" as a statistical term, "navigate" for a ship). Never hide a genuine qualification or technical term just to lower a count.

## Self-check after every draft or edit

1. Run `.venv/bin/python scripts/style_check.py <draft>` and read the summary.
2. Fix what the principles say should change; leave flags that are justified in context.
3. Re-run once if you changed a lot.
4. Report one line in **Notes for you**, e.g. "Style check: cut 3 stock phrases and 2 em dashes; split one 52-word sentence; kept 'robust' (statistical sense)."
