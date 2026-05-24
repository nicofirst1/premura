# 03 — Grounding And Contribution Gate (Stage 2 engine functions)

> Mission: `grounded-extensible-engine-research-01KSD0D1` · WP03 · supports FR-003, FR-004, FR-005, NFR-003
> Purpose: turn the mission's safety promise into a usable decision rule. This document gives a contributor (human or coding agent) three things: how a new **engine function** is judged for scientific grounding, the exact package they must hand in, and a short reviewer gate (≤10 pass/fail checks) that decides whether it lands. It closes Open Questions 1–3 from WP01.

This builds on `research/01-repo-baseline.md` (WP01, approved) and `research/02-stage2-taxonomy.md` (WP02, approved) and cites them rather than re-deriving. It reuses their wording exactly: **engine function** = one registered Stage 2 signal function (one `SignalSpec` + its `fn`); **engine function family**; **signal**; **derived signal**; **health direction** distinct from a signal's `domain` tag; **contribution contract** = "the package a contributor must hand in to add a new engine function" (WP01 "Terminology notes"). Plain English throughout (NFR-006). Every top-level recommendation carries a traceable reference (NFR-001).

A scope reminder that the whole document leans on: Stage 2 is deterministic, network-free, LLM-free, reproducible from the warehouse alone (WP01 Stable Commitment 1). The WP02 "what stays OUT of Stage 2" table is the fast pre-filter — a proposal that returns a p-value / confidence interval / significance verdict, calls the network, looks up references, or teaches a concept is in the wrong stage *before grounding is even assessed* (WP02 Layer 3 boundary table).

---

## Part A — Parser contract vs. the engine seam (T009)

The parser side already ships a written contributor contract: `src/premura/parsers/CONTRACT.md`. The engine side ships only a registration record (`SignalSpec`) and a small public API (`src/premura/engine/_registry.py`; `src/premura/engine/__init__.py`), with no contributor-facing contract (WP01 Open Question 1). The parser contract is the right *spirit-analogue* to borrow from — but the two jobs differ enough that copying it literally would be a mistake. Below, in practical contributor terms.

### What the parser contract gets right — borrow it

| Parser contract habit | Why it helps | How Stage 2 borrows it |
|---|---|---|
| **One file ships with the package and is the source of truth** (`CONTRACT.md` header). | Contributors don't hunt for rules across meetings or chat. | This document is that file for engine functions. A contributor reads one page and can proceed. |
| **A short, ordered, objective reviewer checklist** (`CONTRACT.md` "Reviewer checklist", 7 items). | Review is routine, not bespoke debate; pass/fail beats prose. | The reviewer gate in Part D is the engine analogue, capped at ≤10 checks (NFR-003). |
| **Same-PR rule for ontology additions** (`CONTRACT.md` "Same-PR rule"). | The vocabulary and the code that uses it can never drift apart. | An engine function whose `output` is a new `derived:` `metric_id` must add the matching `dim_metric.yaml` row in the same PR (Part C, Part D check 6). |
| **"At least one fixture-driven test"** (`CONTRACT.md` reviewer checklist). | Determinism is *demonstrated*, not asserted. | An engine function must ship a test that fixes inputs and asserts the exact output (Part C, Part D check 7). For a deterministic engine this is non-negotiable. |
| **A required note explaining anything skipped / ambiguous** (`unmapped_metrics` / `skipped_rows` PR note). | Forces honesty about edge cases instead of silent gaps. | Engine functions must declare caveats and how missing/stale inputs are handled (Part C "caveats", Part D check 5). |
| **The `derived:` namespace is reserved for the engine** (`CONTRACT.md` "off-limits to parsers"). | A clean line between ingested fact and computed signal. | Reaffirmed from the other side: an engine function that *writes* a signal owns the `derived:` namespace and must respect it (WP01 Stable Commitment 7). |

### What is genuinely different about Stage 2 — do NOT copy literally

| Parser reality | Stage 2 reality | Contributor consequence |
|---|---|---|
| A parser's correctness is **mechanical**: did it map vendor field → canonical `metric_id` correctly (the mandatory decision tree, `CONTRACT.md`). The data's *meaning* is the vendor's. | An engine function makes a **claim about the body**: "this ratio / trend / status is worth answering." Correctness includes *whether the question deserves a deterministic answer at all*. | Stage 2 needs a **scientific grounding rubric** (Part B) that parsers simply do not need. A parser is never rejected for "this metric isn't clinically meaningful"; an engine function can be. |
| The parser decision tree is a **closed lookup** (alias → LOINC → IEEE 1752.1 → bare name → `vendor:*` fallback). Following the order *is* compliance. | There is no equivalent lookup for "is this signal grounded." Grounding is a **judgement against evidence**, not a table walk. | Don't expect a mechanical checklist to settle grounding. The rubric gives accept/defer/reject *criteria*; a reviewer still exercises judgement (Part B). |
| Parsers are a **federated plugin surface** by design — a structural `PluginParser` protocol so third parties drop in vendor support (`CONTRACT.md` "Symbols you implement against"). | The engine seam is *currently* an **open boundary** for a possible proprietary `premura-engine-pro`, but whether engine functions become a third-party plugin/skill system is **explicitly undecided and out of scope here** (WP01 Open Question 8; WP01 Stable Commitment 4). | **Do not imply Stage 2 needs the same plugin mechanism as parsers.** This contract governs *what a contribution must contain and prove*, regardless of whether the function ships first-party or in a proprietary package. It is a contribution contract, not a plugin loader spec. |
| A parser's blast radius is one source artifact; a bad batch fails and is re-run (`IngestBatch` validation). | An engine function **persists `derived:` rows back into the warehouse** with `revision` stamped, and other signals/Stage 3 may read them; re-deriving today is manual (WP01 Known Debt 3). | Stage 2 carries a **stage-boundary obligation** parsers don't: a contribution must prove it stays inside Stage 2 (no stats, no network, no teaching — WP02 boundary table) and handles staleness/imputation honestly. That is why the gate has a boundary-compliance check parsers have no analogue for. |

**One-line summary for a contributor:** borrow the parser contract's *discipline* (one source-of-truth file, a short objective gate, same-PR vocabulary, a real test, honest caveat notes) but expect two extra demands parsers never face — *prove the function is scientifically grounded*, and *prove it stays inside Stage 2*.

---

## Part B — Scientific grounding rubric (T010)

This rubric decides whether a proposed engine function is grounded enough to belong in Premura. It produces one of three verdicts: **ACCEPT**, **DEFER**, **REJECT**. Run the WP02 boundary pre-filter first; if the proposal is out of stage, it is REJECT without reaching the evidence questions below.

### What counts as sufficient evidence

An engine function is "scientifically grounded" when **the relationship it computes is recognised in mainstream clinical or sports-physiology practice, and the computation itself is faithful to that recognised definition.** Sufficient evidence is one of:

1. A named, real, well-known reference for the relationship — e.g. a clinical guideline body or standard text. Examples a reviewer would accept as real (cite honestly; do not fabricate): NCEP ATP III lipid guidance for lipid ratios; the AST/ALT (De Ritis) ratio as a long-standing liver marker; standard HRV interpretation (Task Force of the European Society of Cardiology, 1996) for overnight rMSSD as a recovery signal. *Illustrative example only:* "a 7-day rolling mean of resting heart rate" needs no guideline citation — it is a plain descriptive summary of the user's own data, and that is the evidence (see below).
2. **For purely descriptive functions** (current value + freshness, own-baseline mean, trend direction, before/after delta — WP02 families Q1–Q4), the evidence bar is *lower* because the function asserts nothing about the body beyond "here is your own number over time." The grounding question becomes: *is the descriptive statistic computed honestly* (correct window, validity-gated, imputation disclosed)? These are accepted on faithful computation alone.
3. **For interpretive / compound functions** (a derived ratio or a multi-signal composite — WP02 family Q5), the bar is *higher*: the contributor must cite a real, recognised definition of the composite and the threshold/meaning it implies, and must keep the *interpretation* out of Stage 2 (the number is Stage 2; "this means under-recovered" is Stage 4 — WP02 Layer 2 note on Q5).

### Caveat handling and uncertainty disclosure (required for ACCEPT)

Grounding is not just "the relationship is real." A grounded function must also be *honest about its limits*:

- **Input validity / staleness.** It must state how it behaves when an input is stale past its `validity_window`, and never present a stale value as "current" without an explicit override (WP01 Stable Commitment 8; WP02 Q1 note). Built on the shipped `check_inputs_available` gate (`src/premura/engine/__init__.py`).
- **Missing data / imputation.** If it tolerates gaps, it must surface an `is_imputed` mask and name the policy used; if it cannot tolerate gaps, it must say so and decline rather than guess (WP02 Q2; WP01 Known Debt 5).
- **Population scope.** It must state who the recognised definition applies to and where it does not (e.g. lipid ratios assume an adult; a ratio undefined for a value of zero must say so). Where a function *needs* profile context (sex, age) it must name that dependency — it does not invent it (WP01 Open Question 5; GitHub issue #6).
- **What it does NOT claim.** It must explicitly disclaim significance/causation: Stage 2 reports a value or a delta, never "this change is statistically significant" or "X caused Y" (WP02 boundary table).

### Verdict criteria

**ACCEPT** — all of:
- Passes the WP02 boundary pre-filter (in-stage: deterministic, no stats verdict, no network, no teaching).
- Maps to exactly one WP02 function family (Q1–Q5 / signal selector).
- Evidence basis meets the bar for its type (descriptive: honest computation; interpretive: a real recognised definition).
- Caveats above are addressed: staleness, missing-data, population scope, and explicit non-claims.
- Inputs are canonical `metric_id`s that exist (or are added same-PR) and are realistically present in the warehouse for the targeted direction (WP02 Layer 1 first-wave data).

**DEFER** — the relationship is plausible and in-stage, but at least one of:
- The evidence is suggestive but not yet a recognised definition (emerging marker, single small study, contributor's own heuristic).
- A required input is not yet reliably in the warehouse, or needs profile context that is an open dependency (issue #6).
- Caveat handling is incomplete (e.g. no staleness behaviour stated) but fixable.
- *DEFER means "good idea, not yet" — record what evidence or input would move it to ACCEPT.*

**REJECT** — any of:
- Fails the boundary pre-filter (returns a p-value/CI/significance verdict, needs the network, looks up references, or is really Stage 4 teaching — WP02 boundary table).
- Asserts a body claim with no recognised basis, or fabricates / misattributes a citation.
- Misrepresents uncertainty — e.g. presents stale or imputed data as fresh/observed, or implies causation.
- Duplicates an existing signal with no added value, or cannot be made deterministic/reproducible from the warehouse alone.

---

## Part C — Contributor submission contract (T011)

This is the minimum package a contributor or coding agent hands in to propose a new engine function. Keep it compact and concrete — one short block per item, in the PR description (or an accompanying `.md`), plus the code and test. The reviewer gate (Part D) reads directly off this package.

| # | Item | What to provide | Maps to |
|---|---|---|---|
| 1 | **Intended user question** | The plain-English question this answers, and which **health direction** + **question shape** it serves (e.g. "Sleep & recovery / Q2 trend"). | WP02 Layers 1–2 |
| 2 | **Required inputs** | The canonical `metric_id`(s) it reads. Flag any input that needs profile context (sex/age) as a dependency on issue #6. | `SignalSpec.inputs`; WP01 Open Q5 |
| 3 | **Output shape** | What it returns. If it persists a derived signal, the `derived:` `metric_id`, its unit, and the rows' shape; if transient, the return object. State `priority` and `auto_safe` with one line of justification each. | `SignalSpec.output/priority/auto_safe`; WP01 Stable Commitments 6–7 |
| 4 | **Function family + rationale** | Which one WP02 family it belongs to, and why this belongs in Stage 2 (not Stage 3 stats or Stage 4 teaching). | WP02 Layer 3 + boundary table |
| 5 | **Evidence basis** | For descriptive functions: state it's a plain descriptive statistic. For interpretive ones: the real, recognised reference for the relationship and the threshold/meaning it implies. No fabricated citations. | Part B "sufficient evidence" |
| 6 | **Caveats / uncertainty handling** | Behaviour on stale inputs (validity_window), behaviour on missing data (`is_imputed` mask + policy, or explicit decline), population scope, and an explicit list of what it does NOT claim (no significance, no causation). | Part B caveats |
| 7 | **Notes for review** | The same-PR `dim_metric.yaml` diff (if a new metric), the fixture test name, the `revision` value, and any field deliberately skipped or assumption made. | parser-`CONTRACT.md` analogue; `SignalSpec.revision` |

A contributor who fills these seven items has, by construction, everything the reviewer gate checks. There is nothing else to schedule a meeting about.

---

## Part D — Reviewer gate (T012) — 10 checks, all pass/fail

Run top to bottom. Any FAIL stops the function from landing; checks 1–2 are the fast boundary/grounding pre-filter, 3–7 are substance, 8–10 are review readiness. **Total: 10 checks (≤10 per NFR-003).**

| # | Check (PASS condition) | Covers | Evidence |
|---|---|---|---|
| 1 | **In-stage.** Deterministic, network-free, LLM-free; returns no p-value / confidence interval / significance verdict, does no reference lookup, and is not Stage 4 teaching. | Boundary | WP02 boundary table; WP01 Stable Commitment 1 |
| 2 | **Family-mapped.** Maps to exactly one WP02 function family (Q1–Q5 / signal selector). | Boundary / scope | WP02 Layer 3 |
| 3 | **Grounded.** Verdict is ACCEPT under Part B (descriptive computed honestly, or interpretive with a real recognised reference — no fabricated citation). | Scientific grounding | Part B |
| 4 | **Inputs real & present.** Every input `metric_id` exists in `dim_metric.yaml` (or is added same-PR) and is realistically present for the targeted direction; profile-context dependencies are named, not invented. | Grounding / data fit | `SignalSpec.inputs`; WP01 Open Q5; WP02 Layer 1 |
| 5 | **Honest about uncertainty.** Stale-input behaviour stated (no stale-as-current), missing-data handled via `is_imputed` mask + named policy or an explicit decline, population scope stated, and non-claims (no significance/causation) listed. | Grounding / caveats | Part B caveats |
| 6 | **Output & namespace correct.** If it persists, `output` starts with `derived:`, the matching `dim_metric.yaml` row is in the same PR, and unit/shape are specified; `priority` and `auto_safe` are justified. | Boundary (Stage 2/3/4 fidelity) | parser-`CONTRACT.md` same-PR rule; WP01 Stable Commitments 6–7 |
| 7 | **Deterministic test ships.** At least one fixture-driven test fixes inputs and asserts the exact output. | Review readiness | parser-`CONTRACT.md` test rule |
| 8 | **Local-first respected.** No new telemetry, no cleartext leaving the machine, no network call introduced anywhere in the function path. | Boundary (local-first) | WP01 Stable Commitment 10 |
| 9 | **Submission package complete.** All seven Part C items are present and answer the question a reviewer would otherwise ask. | Review readiness | Part C |
| 10 | **No silent collision / drift.** `name` does not collide with an existing `SignalSpec`; `revision` is set (and bumped if logic changed); any skipped field or assumption has a one-line note. | Review readiness | `_registry.py` collision note; `SignalSpec.revision` |

---

## Part E — Worked examples (T013)

Three candidates plausible for Premura, each run through Part B then the Part D gate.

### Example 1 — ACCEPT: `resting_hr_7day_trend`

- **Intended question / family:** "Is my resting heart rate trending up, down, or flat this week?" — Cardiovascular fitness direction, Q2 trend (WP02 Layers 1–2).
- **Inputs / output:** input `resting_hr`; transient output — a 7-day windowed series plus a plain direction descriptor (rising/falling/flat) and an `is_imputed` mask. No `derived:` persistence (read-only summary), so no new ontology row.
- **Rubric (Part B):** descriptive function — evidence bar is faithful computation, met. Caveats: declines if `resting_hr` is stale past its `validity_window`; gaps marked via `is_imputed`; explicitly claims no significance and no causation.
- **Gate (Part D):** 1 PASS (no stats/network/teaching) · 2 PASS (Q2 trend) · 3 PASS (descriptive, honest) · 4 PASS (`resting_hr` is a common warehouse metric, WP02 Layer 1) · 5 PASS (staleness + imputation + non-claims stated) · 6 PASS (transient, no namespace concern; nothing to persist) · 7 PASS (fixture test asserts the trend on fixed inputs) · 8 PASS (local-only) · 9 PASS (package complete) · 10 PASS (unique `name`, `revision="1"`). → **ACCEPT.**

### Example 2 — DEFER: `metabolic_syndrome_composite`

- **Intended question / family:** "Do my body-composition and lipid signals together suggest metabolic-syndrome risk?" — Metabolic direction, Q5 compound (WP02 Layers 1–2).
- **Inputs / output:** inputs `waist_circumference`, `bmi`, `derived:tg_hdl_ratio`, plus sex and age for the recognised cut-points; output a derived composite.
- **Rubric (Part B):** the *relationship* is recognised (metabolic-syndrome criteria are well established) and the function is in-stage if it returns numbers, not a verdict. But two grounding requirements aren't met *today*: `waist_circumference` is not yet a reliably present warehouse metric (WP02 Layer 1 defers lab/profile depth), and the cut-points need **sex and age**, which are an open profile-context dependency (WP01 Open Q5; issue #6). The criteria are also routinely a *clinical diagnosis*, so the interpretive line to Stage 4 must be drawn carefully.
- **Gate (Part D):** 1 PASS (numbers only, if built carefully) · 2 PASS (Q5) · 3 PASS-with-reservation (recognised basis exists) · **4 FAIL** (required inputs not reliably present; profile context is an open dependency, not invented) · 5 PASS-pending. First FAIL stops it. → **DEFER.** *To reach ACCEPT:* land the profile-attribute design (issue #6) and reliable `waist_circumference` ingest, then resubmit; the evidence basis is already adequate.

### Example 3 — REJECT: `sleep_stress_correlation`

- **Intended question / family:** "Are my poor-sleep nights statistically correlated with high-stress days?" — Sleep & recovery direction, framed as Q4/Q5.
- **Inputs / output:** inputs `sleep_rating`, `stress`; output a Pearson `r` with an associated p-value and a "significant / not significant" verdict.
- **Rubric (Part B):** fails the pre-filter immediately. A correlation coefficient with a p-value and a significance verdict is a **statistical claim**, which is Stage 3, not Stage 2 — it is exactly the `correlate` tool named in the WP02 boundary table (WP02 Layer 3 boundary table; ROADMAP "deterministic stat tools").
- **Gate (Part D):** **1 FAIL** (returns a p-value and a significance verdict; this is Stage 3). Stops at the first check. → **REJECT.** *Right home:* this belongs as a Stage 3 statistics tool. The Stage 2-legal sibling would be a Q4 **change-detection** function returning a plain before/after delta with no significance claim (WP02 Q4 example) — that one could be submitted instead and judged on its own merits.

---

## How later WPs should use this gate

- **WP04 (seam evaluation)** can check each `SignalSpec` field and public API function against Part C/D: any field the contribution contract relies on (`inputs`, `output`, `priority`, `auto_safe`, `revision`) is a "keep" candidate; anything the gate never references is a disposition question (WP01 Open Question 4).
- **WP05 (quick wins)** should run its 3–7 shortlist through Part B + Part D before recommending it, so every quick win arrives pre-graded as ACCEPT (and any DEFER is labelled with what unblocks it).
- **WP06 (synthesis)** can cite this gate as the mission's answer to FR-003/FR-004/FR-005 and point to the three worked examples as evidence the gate is usable, not aspirational.
