# premura — Prior-Art Research Brief

> Status: proposal/archive. Research brief used to generate `PRIOR_ART_RESULTS.md`.
>
> Self-contained brief for a deep-research agent with `WebSearch` + `WebFetch` access.
> Output → `docs/history/research/PRIOR_ART_RESULTS.md` in the same repo.
>
> **Partial completion is acceptable and expected.** Each phase below produces a section of the final document. Write what you have at the end of every phase before starting the next. Even Phase 1 alone is useful output — do not refuse to write the document because later phases are incomplete.

---

## Agent prompt — what to do

You are a deep-research analyst with two tools: `WebSearch` (returns title + snippet + URL) and `WebFetch` (fetches and summarizes a URL given a question). Use them. Do not refuse the task because a single search didn't return what you wanted — that's normal. Iterate: refine the query, try a different phrasing, fall back to fetching a known URL directly.

**Hard rules:**
- Verify every claim you write by visiting an actual URL with `WebFetch`. Cite the URL inline.
- If a `WebSearch` returns junk, refine the query (be specific, add operators like `site:github.com`, `inurl:`, `-tag` to exclude noise) and retry up to 3× before giving up on that candidate.
- If a candidate is genuinely impossible to verify after 3 search attempts, write `"⚠️ could not verify within time budget"` in its row and move on. Do not let one unknown block the others.
- After every phase, **save the document with what you have so far**, even if subsequent phases will overwrite/extend it.
- Total time budget: 60–90 minutes of tool calls. Stop and synthesize when you hit that.
- Do not write code. Do not change any file other than `docs/history/research/PRIOR_ART_RESULTS.md`.

**Acceptable minimum output:** Phase 1 results + a recommendation (build vs adopt vs fork) supported by the verified evidence. Phases 2–4 are bonus.

---

## §1 Project context (so you can score relevance)

`premura` is a Python project at `~/repos/personal/premura/`. v1 (already built) ingests **monthly dumps** from 4 sources — Garmin GDPR `.zip`, Android Health Connect `.db`, Sleep as Android `.csv`, Body Measurement Tracker `.csv` — into a single locally-encrypted DuckDB. v2 wants to grow this into an **extensible, vendor-agnostic, AI-tutor health warehouse**:

- **Pillar 1 — Plugin parsers.** Community-contributed parsers for any vendor (Withings, Oura, Apple Health, Whoop, Fitbit, Nightscout, etc.), discoverable as Claude Code skills.
- **Pillar 2 — One DB, many sources.** Long-format star schema (`fact_measurement`, `fact_interval`, `dim_metric`, `dim_source`) already in v1.
- **Pillar 3 — AI tools that don't lie.** MCP server with deterministic stat tools (correlation, t-test, change-point) + PubMed citation round-trip (no hallucinated DOIs).
- **Pillar 4 — Interview-driven onboarding.** User picks a health direction (sleep, cardio, metabolic, stress, mental, overview) and gets routed into a learning track.
- **Pillar 5 — Teach, don't just inform.** Apply Nielsen heuristics, Cognitive Load Theory, Progressive Disclosure, Krug's 5-second test, Bret Victor's Explorable Explanations, Plain Language principles, Dual Coding, Jobs-to-be-Done.
- **Pillar 6 — Privacy.** Local-first. `age`-encrypted. User holds the key. No telemetry, no upsell, GDPR-safe.

**Deferred (not part of this research):** GUI, hosted/multi-user, live-API scraping, write-back to vendor apps.

---

## §2 The question we're answering

> **Does an open, self-hostable, vendor-agnostic, locally-encrypted personal-health warehouse with an AI-tutor analytical layer already exist?**

- **Yes, completely** → adopt + contribute, retire this repo.
- **Yes, partially** → identify the gap; fork/extend/build alongside.
- **No** → proceed with v2 as planned, citing this document.

---

## §3 Adoption rubric — score every candidate against these 5

Mark each criterion as ✅ / ⚠️ / ❌ with a 1-sentence justification + a verifying URL:

1. **Open / self-hostable** — code license permits private deployment; not SaaS-only.
2. **Locally encrypted at rest** — `age` or equivalent; user holds the key.
3. **Vendor-agnostic schema** — not Apple-only, not Garmin-only; designed for arbitrary new sources.
4. **User-extensible** — documented mechanism to add a new vendor without forking the core.
5. **No telemetry, no upsell, GDPR-compatible** — user is not the product.

A candidate that hits **all 5** means we should seriously consider adopting it.
A candidate that hits **3–4** means we learn from it and build alongside.
A candidate that hits **≤ 2** is informational only.

---

## §4 PHASE 1 — Verify the three Tier-A candidates (required)

These three are the closest plausible overlaps. **Investigate them first.** For each: start with `WebFetch` on the listed URL with the listed question, then refine with `WebSearch` if needed.

### Candidate A1: Open Humans

- **Start URL:** https://www.openhumans.org/ — fetch and ask: "What does Open Humans do? Is it self-hostable? Can a user store their own health data privately, encrypted at rest? What sources does it ingest?"
- **Backup:** https://github.com/OpenHumans (search if 404) — fetch and ask: "Is there a self-hostable server component? What's the license?"
- **Probe queries if WebFetch is thin:**
  - `Open Humans self-host` (search)
  - `Open Humans Garmin export` (search)
  - `Open Humans license github` (search)
- **Score against §3 rubric. Write evidence URLs.**

### Candidate A2: Open mHealth

- **Start URL:** https://www.openmhealth.org/ — fetch and ask: "What is the Open mHealth schema? Is there a reference implementation that ingests Garmin / Apple Health / Fitbit dumps? Is the project still active in 2025-2026?"
- **Backup:** https://github.com/openmhealth — fetch and ask: "What repos are most actively maintained? When was the last commit?"
- **Probe queries:**
  - `Open mHealth schema 2025` (search)
  - `Open mHealth deprecated OR archived` (search)
  - `openmhealth shimmer` (search) — Shimmer is their reference parser
- **Score against §3 rubric.**

### Candidate A3: Gadgetbridge

- **Start URL:** https://gadgetbridge.org/ — fetch and ask: "What devices does Gadgetbridge support? Does it have a queryable database the user can extract? Is it Garmin-compatible? Does it handle non-wearable health sources?"
- **Backup:** https://codeberg.org/Freeyourgadget/Gadgetbridge — fetch and ask: "Where does Gadgetbridge store data, and in what format? Can data be exported to a vendor-agnostic schema?"
- **Probe queries:**
  - `Gadgetbridge SQLite export` (search)
  - `Gadgetbridge Garmin Forerunner` (search)
- **Score against §3 rubric.**

### After Phase 1: write Section 1 of the output file

Write `docs/history/research/PRIOR_ART_RESULTS.md` with at least:

```markdown
# Prior-Art Research — Results

## TL;DR (Phase 1 only)
[1–3 sentences based on what you verified]

## Competitive matrix — Tier A

| Candidate | Open? | Local-encrypted? | Vendor-agnostic? | User-extensible? | No-telemetry? | Verdict |
|---|:---:|:---:|:---:|:---:|:---:|---|
| Open Humans | ? | ? | ? | ? | ? | adopt / fork / inform / dismiss |
| Open mHealth | ? | ? | ? | ? | ? | … |
| Gadgetbridge | ? | ? | ? | ? | ? | … |

## Per-candidate notes
[For each, a paragraph: what it does, criterion scores with cited URL evidence, license, last commit/release date]
```

**Save the file at this point even if you have time for more phases.** Subsequent phases append sections; they do not invalidate this one.

---

## §5 PHASE 2 — GitHub topic crawl (~20 min, optional)

Goal: find any community-maintained vendor-agnostic personal-health DB we missed.

- **Specific search queries** (run each with `WebSearch`, look at first 10 results, follow up with `WebFetch` on anything that looks promising):
  - `site:github.com "personal health" database open source` 
  - `site:github.com health data unification OR aggregator self-hosted`
  - `site:github.com topic:quantified-self stars:>50`
  - `site:github.com topic:health-data stars:>50`
  - `site:github.com "Garmin GDPR" parser OR ingest`
  - `site:github.com "Apple Health" XML parser warehouse`
  - `site:github.com fitbit takeout parser`
  - `site:github.com Withings sync python`

For any project that scores ≥3 ✅ on the §3 rubric, add it to the competitive matrix and write a per-candidate paragraph. Don't deep-dive single-vendor parsers (e.g. `withings-sync`) — those are *plugin candidates*, not competitors; just list their existence in a "Plugin ecosystem signal" subsection.

Add **Section 2** to the results document.

---

## §6 PHASE 3 — Analytical-layer + MCP scan (~15 min, optional)

Goal: confirm whether the AI / MCP layer (Pillar 3) is solved.

- **Specific searches:**
  - `site:github.com mcp-server health OR medical OR biology`
  - `site:github.com modelcontextprotocol health`
  - `"mcp-server" duckdb` (we already know `motherduck/mcp-server-motherduck` exists; confirm it speaks local DuckDB)
  - `"mcp-server" pubmed OR entrez`
  - `Whoop Coach AI hallucination` (does the vendor solve it? confirm it's closed)
  - `Oura Advisor open source` (confirm closed)
- **Per-vendor coaching products** — note their existence but don't deep-dive; they're closed-ecosystem, can't be adopted.
- For each *open* MCP-style candidate found, score and add to matrix.

Add **Section 3** to the results document.

---

## §7 PHASE 4 — Synthesis + recommendation (always do this last)

- Pick **one** of four recommendations:
  1. **Adopt [candidate].** Justification + migration plan (1 paragraph).
  2. **Fork [candidate].** Justification + what we'd change.
  3. **Build alongside [candidate].** Justification + integration plan.
  4. **Build standalone.** Justification (no candidate close enough); list 3–5 most relevant projects we'll learn from.
- Add a "Per-pillar coverage" table — for each of the 6 pillars, list which candidates address it and how well (1–5).
- Add "Open questions / could not verify" — anything that needs follow-up.

Append **Section 4: Recommendation** and **Section 5: Open questions** to the results document.

---

## §8 Final output template

`docs/history/research/PRIOR_ART_RESULTS.md` should look like:

```markdown
# Prior-Art Research — Results
> Generated: <date>
> Time budget used: <minutes>
> Phases completed: 1 / 2 / 3 / 4

## TL;DR
<1–3 sentences>

## Section 1: Tier-A competitive matrix
<table + per-candidate notes>

## Section 2: GitHub topic crawl (if Phase 2 completed)
<additional matrix rows + plugin-ecosystem signal subsection>

## Section 3: Analytical layer (if Phase 3 completed)
<additional candidates>

## Section 4: Per-pillar coverage
| Pillar | Best candidate | Score (1-5) | Gap if we build it ourselves |
|---|---|:---:|---|
| 1 — Plugin parsers | … | … | … |
| 2 — Common DB | … | … | … |
| 3 — AI tools | … | … | … |
| 4 — Interview UX | … | … | … |
| 5 — Teaching layer | … | … | … |
| 6 — Privacy | … | … | … |

## Section 5: Recommendation
**Choice: <adopt | fork | build alongside | build standalone>**
<1–2 paragraphs>

## Section 6: Open questions
- <item>
- <item>
```

Keep the document under ~5 pages of markdown. Link to sources; do not paste full repo READMEs.

---

## §9 Anti-goals

- Don't write code.
- Don't fall in love with one candidate before scoring all of Tier A.
- Don't dismiss commercial products without confirming they're SaaS-only.
- Don't expand scope to clinical EHR / FHIR / OpenEHR — we are a *personal* warehouse, not a clinical one. Note them in "Open questions" if you encounter them.
- Don't refuse to write the document because evidence is incomplete. Write what you verified, mark the rest as `"⚠️ could not verify within time budget"`.
