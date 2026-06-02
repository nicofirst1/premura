# Research — frameworks for auditing immokalkul

## Purpose

`immokalkul` serves a specific persona: a **first-time property buyer living in Germany who is not assumed to be German-native**. The audit has to simultaneously satisfy two goals that pull in opposite directions:

- **Goal A — don't overwhelm.** If the user disengages on opening the page, we've failed before any number is read.
- **Goal B — teach transparently.** Every value shown must be traceable to a German rule, law, or common practice the user can learn.

A useful audit framework for this app must therefore (1) have something to say about *entry cognitive load*, (2) have something to say about *in-context learning*, and (3) be actionable at the level of tooltip copy, section order, and visual hierarchy — **not** architectural refactoring. The app is ~1341 lines in a single `app.py`; frameworks that require a multi-page IA, analytics pipeline, or usability-lab studies are out of scope.

Below is the shortlist. Each entry states the framework, why it fits this specific app and persona, the concrete audit questions it unlocks, and canonical citations.

---

## 1. Nielsen's 10 Usability Heuristics (NN/g, 1994, rev. 2024)

**Summary.** Ten general principles for interaction design, derived from factor analysis of usability problems. The most widely used heuristic-evaluation backbone in the industry. Refreshed by NN/g in January 2024 (language clarified; the ten heuristics themselves unchanged since 1994).

**Why it fits.** The canonical spine for any heuristic audit. Four heuristics map directly onto our goals: *Match between system and the real world* (H2) tests whether German legal terms are spoken in the user's language; *Recognition rather than recall* (H6) tests whether users have to remember what Kaltmiete vs. Warmmiete means between sections; *Flexibility and efficiency of use* (H7) speaks to the beginner/expert split; *Aesthetic and minimalist design* (H8) is the direct hammer for Goal A (don't overwhelm). NN/g also publishes a specialized adaptation for complex, data-heavy applications that we'll apply to the tabs + KPI cluster.

**Audit questions.**
- Does the first screen tell the user where they are, what this app does, and what to do next (H1 Visibility, H7 Help-and-documentation)?
- Is any German term (AfA, Bodenrichtwert, Petersche) displayed without an adjacent plain-language gloss (H2 Real-world match)?
- Does the user have to recall a value defined in the sidebar in order to interpret a metric in the main area (H6 Recognition vs recall)?
- Can a novice ignore expert-only controls (adaptive loan ceiling, Bodenrichtwert, Anschaffungsnaher flag) without penalty (H7 Flexibility)?
- Is there any visible non-essential information above the fold (H8 Minimalist)?

**Citations.**
- [Jakob Nielsen — 10 Usability Heuristics for User Interface Design (NN/g, updated 2024)](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [NN/g — 10 Usability Heuristics Applied to Complex Applications](https://www.nngroup.com/articles/usability-heuristics-complex-applications/)

---

## 2. Cognitive Load Theory (Sweller, 1988)

**Summary.** Learning is constrained by working memory. Three load types: *intrinsic* (inherent difficulty of the subject), *extraneous* (load added by how material is presented), *germane* (effort that builds durable schemas). The instructional-design goal is: minimize extraneous load, manage intrinsic load, encourage germane load.

**Why it fits.** This is the theoretical backbone for Goal A. German property finance has **high intrinsic complexity** — a novice cannot collapse AfA, Annuitätendarlehen, Grunderwerbsteuer, Mietpreisbremse, and the live-vs-rent trade-off into one glance. We cannot lower intrinsic load without dumbing down the tool; we can only (a) chunk it so working memory isn't overwhelmed, and (b) eliminate extraneous load (redundant labels, visual clutter, split-attention across screen regions). CLT also gives us a principled reason to prefer *worked examples* over blank forms — hence why the app's pre-loaded Bonn scenario is a good decision that should be *amplified*, not removed.

**Audit questions.**
- Where does the design force users to hold information in working memory across screen regions (split-attention effect)? E.g., does a KPI on top reference a sidebar input far below?
- Are redundant labels forcing the user to read the same concept twice (redundancy effect)?
- Does the default scenario function as a worked example, or does it look like a generic placeholder the user must replace?
- Which sidebar inputs carry high intrinsic load that should be chunked / deferred / disclosed on demand?
- Does any visual element (chart, pie, table) add germane load (supports a schema the user should build) or merely extraneous decoration?

**Citations.**
- [Cognitive Load Theory — overview (ScienceDirect)](https://www.sciencedirect.com/topics/psychology/cognitive-load-theory)
- [The Decision Lab — Cognitive Load Theory reference guide](https://thedecisionlab.com/reference-guide/psychology/cognitive-load-theory)

---

## 3. Progressive Disclosure (Nielsen, 1995; NN/g)

**Summary.** Show the essentials first, reveal advanced options on demand. Nielsen's 1995 pattern for complex apps. NN/g guidance: two disclosure levels max — three or more levels breaks usability.

**Why it fits.** The app has 30+ inputs across 8 sidebar expanders, 9 main tabs, and a "Start here" onboarding tab. Progressive disclosure is the operational translation of CLT into concrete UI moves (collapse, expand, defer). Critically, NN/g's "Few Guesses, More Success" article explicitly ties progressive disclosure to form-completion rates: multi-step forms beat single-step forms by 14 %. Our sidebar is a single-step form with every section visible at once.

**Audit questions.**
- Which of the 8 sidebar expanders are open by default? Are those the ones a first-time user needs?
- Does the current disclosure depth exceed 2 levels anywhere (e.g., sidebar → expander → nested expander)?
- Are "always safe to leave at default" fields clearly labeled as such, or do they visually compete with fields the user *must* set?
- Do expert-only flags (Adaptive loan, Denkmal, Bodenrichtwert override, auto-schedule capex) appear before the user has made the fundamental decision?
- Does the tab bar progressively disclose, or does it dump 9 parallel destinations on the user at once?

**Citations.**
- [Jakob Nielsen — Progressive Disclosure (NN/g)](https://www.nngroup.com/articles/progressive-disclosure/)
- [NN/g — 4 Principles to Reduce Cognitive Load in Forms](https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/)

---

## 4. Steve Krug — "Don't Make Me Think" (2000, rev. 2014)

**Summary.** Three laws: *Don't make me think*, *It doesn't matter how many clicks if each is mindless*, *Get rid of half the words, then half again*. Users **scan, they don't read**; they **satisfice** (click the first plausible option). Anchoring technique: the **5-second test** — can the user answer "what is this page, what can I do here, why should I care?" within five seconds?

**Why it fits.** This is the operational translation of Goal A. The first-open experience is the single most audit-critical moment in the app — if the user can't answer "can I afford this house?" inside five seconds, every other improvement is downstream noise. Krug's scanning model also tells us our users will not read tooltips unless signalled explicitly to do so; hence educational content hidden in `help=` props is effectively invisible to Krug's average scanner.

**Audit questions.**
- 5-second test: on landing, can a first-time user state (a) what this app is for, (b) the headline verdict for the pre-loaded scenario, (c) what to edit to try their own?
- Which headings and labels fail the "halve the words" test?
- Are there mindless clicks the user must perform before reaching useful information (e.g., expand an expander, open a tab)?
- Does satisficing hurt us — will a user click the first "plausible" tab and stay there, missing the actual answer?
- Is the visual hierarchy on the Summary tab strong enough that a scanner lands on the verdict, not on decorative detail?

**Citations.**
- [Steve Krug — Don't Make Me Think, Revisited (sensible.com)](https://sensible.com/)
- [Don't Make Me Think — Wikipedia overview](https://en.wikipedia.org/wiki/Don%27t_Make_Me_Think)

---

## 5. Explorable Explanations (Bret Victor, 2011; Nicky Case)

**Summary.** A genre of interactive learning where the reader manipulates the parameters of a simulation to discover a concept, guided by prose. Victor's 2011 essay (*Explorable Explanations*) argued reading is a passive activity that fails complex material; active manipulation + feedback builds schemas faster. Nicky Case's blog posts catalogue design patterns: *reactive documents*, *parameterizable diagrams*, *guided tours*, *question-prompt mode*.

**Why it fits.** This is the framework that turns Goal B from "dense reference material" into "the tool itself is the teacher." A property calculator is already a parameterized simulation — the rent slider, the debt budget, the horizon slider all invite exploration. The gap is *guidance*: users can change inputs but aren't told what to try or what to observe. Explorable-explanation design patterns give us moves ranging from cheap (add a "try this" caption under each chart) to structural (a narrative walk-through that drives the inputs for the user) — all within the scope of Streamlit primitives.

**Audit questions.**
- When the user changes an input, is the consequence visible without scrolling / tab-switching (reactive document)?
- Does any chart or metric answer a *question* the user would have asked, or is it just data served without prompt?
- Is there any guided-tour moment that says "try raising the horizon from 30 to 50 — watch the cumulative line"?
- Is the pre-loaded Bonn scenario used to *teach*, or is it just a convenient default?
- Does the app ever invite a counterfactual ("what if rent escalates at 3% instead of 2%")?

**Citations.**
- [Bret Victor — Explorable Explanations (2011)](http://worrydream.com/ExplorableExplanations/)
- [Nicky Case — Explorable Explanations: 4 More Design Patterns](https://blog.ncase.me/explorable-explanations-4-more-design-patterns/)
- [Explorable Explanation — Wikipedia](https://en.wikipedia.org/wiki/Explorable_explanation)

---

## 6. Plain Language + Microcopy Principles (plainlanguage.gov, CFPB, NN/g)

**Summary.** Federal-US plain-language movement: prefer short sentences, active voice, everyday words over legalese, "you" over abstract subjects. The SEC's 1998 Plain English Rule and the CFPB's Plain Writing programme directly govern financial-product disclosure. NN/g translates these into *microcopy* guidance for buttons, labels, error messages, tooltips.

**Why it fits.** Goal B is fundamentally a content problem, not a layout problem. Every German statute cited in the app (§7 EStG, §6 EStG, §19 WEG, §28 II. BV) is written in the most opaque register of legal German. The user's need isn't to *read the statute* — it's to understand in a sentence what rule is being applied to their number. Plain-language principles and financial microcopy conventions give us a direct rubric: is each term introduced before use? Is the voice consistent? Does every tooltip explain why the value matters, not just what it is?

**Audit questions.**
- Is each German legal term introduced with a plain-English one-liner on first appearance?
- Does the voice shift between "you" (good) and passive/abstract ("the engine computes") within the same screen?
- Do tooltips explain *what the number is* only, or also *why it matters for the decision*?
- Where do we use jargon we could replace (burden, LTV, marginal rate, AfA basis) with either a plainer phrase or an adjacent definition?
- Are input labels self-sufficient, or do they require a tooltip hover to understand?

**Citations.**
- [plainlanguage.gov — Plain Language in Finance](https://www.plainlanguage.gov/resources/content-types/finance/)
- [CFPB — Plain Writing programme](https://www.consumerfinance.gov/plain-writing/)
- [Digital.gov — Principles of plain language](https://digital.gov/guides/plain-language/principles)

---

## 7. Dual Coding Theory (Paivio, 1971/1986)

**Summary.** Cognition has two channels — verbal and visual — each with independent limited capacity. Pairing a visual with relevant prose creates two retrieval paths to the same concept; recall and transfer are measurably better than either channel alone. Foundational basis for Mayer's Multimedia Learning principles.

**Why it fits.** The app is chart-heavy: Plotly line charts, stacked bars, pies, Gantt-like bubble scatter, dual-axis amortization charts. Dual coding predicts these visuals fail to build durable understanding *unless* they are paired with verbal structure — a title that asks a question, a caption that names the insight, a one-sentence conclusion that tells the user what this chart is supposed to prove. A chart without prose is pure visual channel; a number without a visual is pure verbal. We lose half the bandwidth either way.

**Audit questions.**
- For each chart, is there a caption stating what insight to extract?
- For each table, is there a narrative sentence preceding it that tells the user what to look for?
- Do titles act as questions the chart answers, or are they generic labels ("Annual payment breakdown")?
- Does any number have a visual analog, and vice versa, so both channels reinforce?
- Where does the app force dual attention (read the KPI, then look at the chart, then read the legend) in a way split-attention would hurt?

**Citations.**
- [Dual-coding theory — Wikipedia](https://en.wikipedia.org/wiki/Dual-coding_theory)
- [Paivio — Dual Coding Theory (InstructionalDesign.org)](https://www.instructionaldesign.org/theories/dual-coding/)

---

## 8. Jobs-to-be-Done (Christensen / Ulwick)

**Summary.** Users don't buy products; they *hire* them to make progress on a specific job in a specific context. A JTBD statement has the form *"When [situation], I want to [motivation], so I can [expected outcome]"*. Product decisions follow from the job, not from feature wishlists.

**Why it fits.** Applying JTBD to our user crystallizes the audit's priority. The job is **"when I'm considering a specific property in Germany, I want to know whether my finances can absorb it, so I can decide whether to pursue it or keep looking."** That is the five-word summary the Summary tab must deliver. Every other surface (cashflow, debt, tax) is either scaffolding for that decision or post-decision due diligence. JTBD is the lens that tells us *which* improvements are load-bearing vs. nice-to-have.

**Audit questions.**
- Within 5 seconds of landing, does the UI answer the core job statement above?
- Is there a surface that does *not* serve the core job and isn't clearly labelled as advanced/optional?
- What are the *related jobs* a first-time buyer might have ("what's a realistic rent to charge", "how much down payment do I need") and are they visibly addressed?
- Is the live-vs-rent comparison framed as *a decision the user needs to make*, or as parallel data?
- Does the app help the user take the *next step* after learning their verdict (e.g., "if yes, go talk to a Bank about a Finanzierungszusage")?

**Citations.**
- [Strategyn (Tony Ulwick) — Jobs to Be Done: The Original Framework](https://strategyn.com/jobs-to-be-done/)
- [ProductPlan — Jobs-To-Be-Done Framework glossary](https://www.productplan.com/glossary/jobs-to-be-done-framework/)

---

## How the audit will apply these

The eight frameworks compose into a layered audit lens:

- **Entry load (5 seconds):** Krug + JTBD + Nielsen H1/H8 — is the core job answered at a glance?
- **Per-surface review:** Nielsen 10 heuristics, each tab + the sidebar + the header
- **Education surface:** Plain language + Explorable Explanations + Dual Coding — does each term get taught, and does each chart have prose?
- **Global IA:** Progressive Disclosure + CLT — is the information architecture load-appropriate for a novice?
- **Coverage audit:** Plain Language applied exhaustively to every German legal term used — is each one defined in-context on first appearance?

Severity scale used in `audit.md`:

- **1 — Cosmetic:** minor polish, no user impact
- **2 — Minor:** confusing but recoverable
- **3 — Major:** likely to cause a Goal A or Goal B failure for the target persona
- **4 — Blocker:** directly causes first-open disengagement or outright misunderstanding of a German legal rule

---

## Frameworks deliberately excluded

- **Bloom's Taxonomy, Gagné's 9 Events, ADDIE.** Formal instructional-design frameworks aimed at course-length material. Too heavy for a calculator interface.
- **Formal WCAG accessibility audit.** Important, but a separate body of work and orthogonal to the Goal A / Goal B brief. Surface-level contrast + keyboard issues will be noted where relevant, but full WCAG 2.2 conformance is out of scope.
- **Quantitative A/B testing / funnel analytics.** Requires deployment + traffic the app doesn't have.
- **Full ethnographic / JTBD interview study.** JTBD is used here as a *design lens*, not as a research method.

## Sources

- [Jakob Nielsen — 10 Usability Heuristics for User Interface Design (NN/g)](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [NN/g — 10 Usability Heuristics Applied to Complex Applications](https://www.nngroup.com/articles/usability-heuristics-complex-applications/)
- [Jakob Nielsen — Progressive Disclosure (NN/g)](https://www.nngroup.com/articles/progressive-disclosure/)
- [NN/g — 4 Principles to Reduce Cognitive Load in Forms](https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/)
- [Cognitive Load Theory — ScienceDirect overview](https://www.sciencedirect.com/topics/psychology/cognitive-load-theory)
- [The Decision Lab — Cognitive Load Theory](https://thedecisionlab.com/reference-guide/psychology/cognitive-load-theory)
- [Steve Krug — sensible.com](https://sensible.com/)
- [Don't Make Me Think — Wikipedia](https://en.wikipedia.org/wiki/Don%27t_Make_Me_Think)
- [Bret Victor — Explorable Explanations](http://worrydream.com/ExplorableExplanations/)
- [Nicky Case — Explorable Explanations design patterns](https://blog.ncase.me/explorable-explanations-4-more-design-patterns/)
- [Explorable Explanation — Wikipedia](https://en.wikipedia.org/wiki/Explorable_explanation)
- [plainlanguage.gov — Plain Language in Finance](https://www.plainlanguage.gov/resources/content-types/finance/)
- [CFPB — Plain Writing](https://www.consumerfinance.gov/plain-writing/)
- [Digital.gov — Principles of plain language](https://digital.gov/guides/plain-language/principles)
- [Dual-coding theory — Wikipedia](https://en.wikipedia.org/wiki/Dual-coding_theory)
- [Paivio — Dual Coding Theory (InstructionalDesign.org)](https://www.instructionaldesign.org/theories/dual-coding/)
- [Strategyn — Jobs to Be Done: The Original Framework](https://strategyn.com/jobs-to-be-done/)
- [ProductPlan — Jobs-To-Be-Done Framework](https://www.productplan.com/glossary/jobs-to-be-done-framework/)
