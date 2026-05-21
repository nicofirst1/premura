# premura — Risk / Opportunity Matrix

> Status: proposal/archive. Strategy memo for prioritization, not a delivery contract.
>
> Companion to [VISION.md](VISION.md), [ROADMAP.md](ROADMAP.md), [PRIOR_ART_RESULTS.md](PRIOR_ART_RESULTS.md).
> Written 2026-05-20 to decide *how much time to invest* in v2 now that prior-art research confirms the gap.

## TL;DR

**Recommended: commit to Tier 2** (MCP analytical layer + skill-based parser ecosystem, CLI-first, no UI yet). The prior-art research found the structural gap is real and three of the hardest pieces (PubMed MCP, DuckDB MCP, schema patterns) can be adopted directly — meaning the marginal cost to reach a genuine product surface is lower than the v2 scope first suggested. Tier 1 leaves value on the table; Tier 3 is premature without traction.

This document lays out the reasoning. You may disagree with the tier — the data should support any of the three.

---

## Convergent evidence base

Both research passes (the Sonnet agent's full 4-phase scan + the external agent's Phase-1) reached compatible verdicts:

- **No existing project covers all 6 pillars.** Open Wearables is closest structurally (3/5 criteria, live-API not GDPR-dump). Open Humans is SaaS-shaped; Open mHealth tooling is dormant since 2017; Gadgetbridge is a data *source* not a warehouse.
- **Two MCP components are directly adoptable.** `healthcare-mcp-public` (PubMed search/fetch tools, MIT) and `mcp-server-duckdb` (DuckDB transport, MIT) collapse a large chunk of Pillar 3 work.
- **Schema references exist.** GarminDB (Garmin GDPR field mapping) and Open mHealth schemas (vendor-neutral metric vocabulary) reduce the cost of Pillar 2 vocabulary design.
- **Pillars 4 + 5 (interview UX + teaching layer) are completely absent from the market.** Vendor-locked AI coaches (Whoop Coach, Oura Advisor) prove the appetite but cannot be adopted.
- **Pillar 6 (local-first, `age`-encrypted, user-held-key) is unique in the surveyed ecosystem.**

The whitespace is real. The question is whether it's worth our time.

---

## Opportunity matrix

Scored: *Scale* (1 = personal, 5 = field-defining), *Confidence* (1 = speculative, 5 = verified), *Reuse leverage* (1 = build from scratch, 5 = adopt existing).

| # | Opportunity | Scale | Confidence | Reuse |
|---|---|:---:|:---:|:---:|
| O1 | Confirmed market gap — no open vendor-agnostic personal-health warehouse exists | 4 | 5 | n/a |
| O2 | `healthcare-mcp-public` + `mcp-server-duckdb` collapse Pillar 3 transport + citation tooling | 3 | 5 | 5 |
| O3 | GarminDB + Open mHealth = ready-made schema vocabulary; we don't reinvent metric naming | 3 | 4 | 4 |
| O4 | v1 is **already built and verified** against 900k real rows — sunk cost is now a foundation | 2 | 5 | 5 |
| O5 | Garmin's bridge gaps (HRV, stress, body battery) have been stable for 3+ years — the moat persists | 3 | 4 | n/a |
| O6 | Single-developer-is-also-the-user → tight feedback loop, no need for external validation early | 3 | 5 | n/a |
| O7 | AI-tutor angle is novel + timely (post-MCP-launch ecosystem moment) | 4 | 3 | 2 |
| O8 | Privacy-first positioning aligns with GDPR climate and 2025–2026 EU Data Act direction | 3 | 4 | n/a |
| O9 | Claude Code skills are an emerging extension surface — getting in early on a vertical (health) is cheap leverage | 3 | 3 | 4 |
| O10 | Quantified-self / longevity / biohacker / n-of-1 research communities are organized + hungry for tooling | 3 | 3 | n/a |
| O11 | Open Wearables + Gadgetbridge become potential *input adapters*, not competitors — more upstream than downstream | 2 | 4 | 3 |

---

## Risk matrix

Scored: *Severity* (1 = minor, 5 = project-killer), *Likelihood* (1 = improbable, 5 = near-certain), *Mitigatable* (1 = no, 5 = easy).

| # | Risk | Sev | Lik | Mitig |
|---|---|:---:|:---:|:---:|
| R1 | Vendor format drift — every Garmin/Apple/Withings export will surprise the parser | 3 | 5 | 4 |
| R2 | Skill ecosystem won't bootstrap if no community forms; we end up writing all parsers ourselves | 4 | 3 | 3 |
| R3 | LLM hallucination on health advice = real product-liability concern even with tool guardrails | 4 | 3 | 3 |
| R4 | "Teach, don't just inform" requires design + pedagogical talent we don't have on the team | 4 | 4 | 2 |
| R5 | Single-developer bus factor of 1; if you stop, the project dies | 3 | 4 | 2 |
| R6 | Personal-health data + AI sits in a sensitive regulatory zone (GDPR Art. 9, EU AI Act risk classes, medical-device-software lines) | 4 | 3 | 3 |
| R7 | Stats on n=1 personal data are statistically weak — most "findings" will be underpowered or confounded | 3 | 4 | 3 |
| R8 | PubMed quality is variable; many cited studies replicate poorly. Risk of teaching the user wrong things | 3 | 3 | 3 |
| R9 | Scope creep: "users want vendor X" never ends. Maintenance scales linearly with parser count | 3 | 5 | 3 |
| R10 | Big-player threat: Apple/Google/Whoop could ship an AI-tutor and erase the niche overnight | 4 | 2 | 1 |
| R11 | Time investment in v2 without monetization model means it's a hobby project competing with paid work | 3 | 4 | 4 |
| R12 | Interview-driven onboarding is UX-heavy — genuinely hard to nail in CLI; demands UI sooner than planned | 3 | 3 | 3 |

---

## Investment tiers — three concrete paths

Each tier is a self-contained commit. You can step up from one to the next; you cannot easily reverse direction without sunk-cost pain.

### Tier 1 — "Polish v1, ship to self" (~2–4 weeks part-time)

**Scope:**
- Close the v1 punch list: live `age` round-trip (FR-6), real-data SAA ingest, launchd bootstrap, wiki hub page.
- Run the monthly pipeline for 3 months personally, confirm it's robust.
- README + setup docs polished to "another nerd could run it on their Mac."
- **No MCP, no skill system, no teaching layer.**

**You walk away with:** a personal tool that solves *your* HC-bridge-gap problem. A handful of HN nerds use it.

**Pros:** Lowest cost, highest certainty of completion. Most of the work is already done.
**Cons:** Leaves all the actual differentiation on the table. The "personal pipeline" framing means you compete with `garmin-grafana` and `qs_ledger`, not with anything novel.

**Decide for Tier 1 if:** you're time-constrained, want the value for yourself only, and the AI-tutor vision was an interesting tangent rather than the goal.

---

### Tier 2 — "MCP + skill ecosystem, CLI-first" (~2–3 months part-time) — **recommended**

**Scope on top of Tier 1:**
- Adopt `healthcare-mcp-public` for PubMed; adopt `mcp-server-duckdb` for query transport.
- Build the **deterministic stats MCP tools** (Pillar 3 core): `correlate`, `paired_t_test`, `rolling_mean`, `change_point`, returning `{effect, n, p, ci}`.
- Define the **skill contract** for parsers (single Python module, declares `parse() → ParseResult`, declares filename signature, declares `dim_metric` additions).
- Build **3–5 reference parser skills** beyond v1: Apple Health XML, Withings export, Fitbit Takeout, Oura, Strava.
- Build a **CLI interview** (`hpipe learn`) that walks the user through the 6 health-direction tracks with Rich prompts.
- Document the **plain-language + dual-coding pattern** for metric introduction; apply it to all 43+ metrics in `dim_metric.yaml`.
- Ship a public repo with `CONTRIBUTING.md` describing the skill model.

**You walk away with:** an open-source project people can plug into. A genuine analytical surface. Pillars 1, 2, 3 are real; 4, 5, 6 are CLI-resolved.

**Pros:** Touches every pillar at low cost (because the hard MCP pieces are adopted). Establishes the skill model before community forms — easier than retrofitting. Defensible niche (the AI-tutor + privacy combination is unique).
**Cons:** Adds ~2–3 months. Maintenance burden grows with each parser. No UI means the teaching layer is text-only — limited reach.

**Decide for Tier 2 if:** the AI-tutor + skill ecosystem are the actual goal, you have evenings for the next quarter, and you want to validate the concept before committing to a UI.

---

### Tier 3 — "Real product: UI + community + OpenRouter" (~6–12 months sustained)

**Scope on top of Tier 2:**
- Web UI (Streamlit MVP → eventually proper React/SvelteKit).
- Full interview + teaching layer with explorable explanations (reactive documents, parameterizable diagrams).
- OpenRouter integration so users pick their model.
- Community moderation: PR review for parser skills, security audits, vetting.
- Hosting-optional architecture (still local-first, but a one-click Vercel/Fly deploy for the UI talking to a local DuckDB).
- Possibly: monetization via paid hosted instance / paid model credits / sponsorship.

**You walk away with:** a real product. Possibly a side business. Possibly a job's worth of work.

**Pros:** Maximum optionality. If quantified-self + AI-health coaching becomes a category, you're positioned.
**Cons:** Real time cost. UI design is a distinct skill we don't have. Community management is itself a job. Big-player threat (R10) materializes here, not in Tier 1/2. Without monetization, this competes with your paid work indefinitely.

**Decide for Tier 3 if:** you have either (a) clear traction signal from Tier 2 (≥20 community users, ≥3 PR'd parser skills), (b) a co-founder/co-maintainer, or (c) a willingness to make this your main thing.

---

## Decision rubric

The cheapest decision is one you can revisit. Run Tier 2 for 6 weeks; reassess.

| If you observe… | Move toward… |
|---|---|
| You're using `hpipe status` weekly without prompting | Tier 2+ (you're the validated user) |
| You build a parser for vendor X and find yourself writing it in 4 hours | Tier 2 (skill model is sound) |
| You build a parser for vendor X and it takes 4 days | Stay Tier 1 (extensibility is harder than it looked) |
| The MCP analytical surface answers a question Garmin Connect can't | Tier 2+ (Pillar 3 is the differentiator) |
| Someone unprompted asks if they can use it | Consider Tier 3 |
| Apple or Google ships an AI-tutor in their health app | Stay Tier 1 (R10 fired) |
| You stop using it yourself for 2 weeks | Stop the project (Tier 0) |

---

## Things we still don't know

(Carried forward from [PRIOR_ART_RESULTS.md](PRIOR_ART_RESULTS.md) §6 + new questions raised by this analysis.)

- **Can `mcp-server-duckdb` open an `age`-encrypted file** without exposing plaintext to disk? If not, Pillar 3 + Pillar 6 need an architectural decision.
- **What does the skill contract actually look like?** Claude Code's skill format is young; the parser-skill design is unproven.
- **What's the right unit of "teaching"?** Is it a metric (HRV is one card)? A track (sleep & recovery is one journey)? A question ("why did my HRV drop last week" is one tour)? Unresolved.
- **Are there ~10 quantified-self users who'd actually contribute parser skills?** No evidence either way; needs a small test (post to `r/QuantifiedSelf` after Tier 2 ships).
- **Does the EU AI Act categorize a personal-health AI tutor as high-risk?** Probably not — it's analytical, not diagnostic — but worth a legal-tier read before Tier 3.
- **Monetization model**: pure FOSS, paid hosting tier, sponsorship, Patreon, never-money? Different choices imply different architecture decisions.

## What to do this week

If you're sold on Tier 2:

1. **One-week spike** on `mcp-server-duckdb` + `age` to answer the encryption-compatibility open question. If `mcp-server-duckdb` can't talk to an encrypted DuckDB, we know the architectural pain early.
2. **Write the skill contract proposal** as a short doc + a single example. Confirm it feels right before committing to N parsers.
3. **Close FR-6 (`age` round-trip live test)** — it's a 30-minute Tier-1 item that should not block Tier-2 work.

If you're not sure: do Tier 1 only, stop, and revisit in 4 weeks with fresh eyes.
