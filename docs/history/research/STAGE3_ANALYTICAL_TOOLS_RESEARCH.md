# premura — Stage 3 Analytical Tools Research

> Status: durable design rationale. Source of record for the decisions that the
> Stage 3 analytical-tools mission (`stage-3-analytical-tools-01KST48C`)
> implements. Later analytical work follows this note instead of re-deciding.
>
> Generated: 2026-05-29
> Scope: the first deterministic analytical layer over the operator's own
> admissible evidence — its method shapes, its question-type and confound
> vocabularies, and the boundaries it must not cross.
>
> Companions: [`DOCTRINE.md`](../../product/DOCTRINE.md),
> [`ROADMAP.md`](../../product/ROADMAP.md) §"Next major phase — analytical depth",
> [`FULL_APP_DEVELOPMENT_PLAN.md`](../../product/FULL_APP_DEVELOPMENT_PLAN.md)
> §"Phase 3: `v2.2 analytical depth`",
> [ADR 0007 — evidence admissibility as a declared contract](../../adr/0007-evidence-admissibility-as-a-declared-contract.md),
> and the prior
> [`STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md`](STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md).

## Purpose

Premura can already answer grounded descriptive and comparative questions
through the Stage 2 result families (`status`, `trend`, `baseline`, `change`),
exposed as Stage 3 MCP tools that delegate to the engine rather than reading the
warehouse directly. The next step in the roadmap's analytical-depth phase is a
deterministic *statistical* layer on top of that grounded evidence.

This note records why the first analytical mission builds a small, deterministic
**analytical-tool contract** — a registry, a declared input-series shape, and a
mandatory result envelope — and proves it with exactly two conservative tools
(`change_point` and a smoothed average) **before** broader statistics, literature
grounding, or reproducible traces. The reader here is the implementing agent; the
beneficiary is the human operator whose own data is being analyzed. The agent
needs a settled, citeable rationale so that tests and data shapes can lock the
contract in without re-litigating method choices, and so that later analytical
tools extend the same seam instead of inventing one-off conventions.

This is the **narration-honesty** half of the documented R7 risk: the agent
should narrate computed estimates, uncertainty, and validity metadata that the
tools return, instead of fabricating magnitudes from priors. It does **not**
claim to fix the deeper weakness of n-of-1 self-tracked time series. That
weakness is carried, not removed, by attaching validity and confound metadata to
every estimate and by refusing when the data cannot honestly support the request.

## Summary

The mission settles five things, all in plain English and all at the altitude
DOCTRINE.md requires (define the rule for adding tools, do not enumerate the
intended statistical surface):

1. **Conservative, interpretable methods only.** The two proof tools are chosen
   because they are easy for an agent to narrate honestly and easy for a reviewer
   to validate, not because they maximize statistical coverage.
2. **A single-level-shift `change_point` method** over one ordered series, picked
   by the largest standardized level difference among valid split points, with no
   p-value.
3. **A trailing rolling-mean smoothed average**, with a declared window and
   minimum coverage, that does not invent or fill missing data and states plainly
   when no uncertainty interval is available.
4. **Two reviewed, closed analytical question types** — `level_shift_detection`
   and `smoothed_pattern` — added to the evidence-policy vocabulary rather than
   bent onto the existing descriptive question shapes.
5. **A closed, runtime-owned confound vocabulary** of eight keys, so the agent
   can branch on machine-readable validity warnings instead of parsing prose.

Everything stays local-first, descriptive, non-causal, and non-diagnostic, and
nothing here reopens the Stage 2 result families.

## Decisions

### D1 — Use conservative, interpretable methods, and defer the rest

The proof tools exist to prove the contract and reduce narration risk, not to
ship broad statistics. A full significance-testing suite is rejected for this
slice: it is too broad to prove the seam with, and effect sizes and p-values are
too easy to overstate in confounded n-of-1 data. The roadmap also lists
`correlate` as an early candidate; it was considered as the second proof tool but
replaced by the smoothed average during planning, because correlation introduces
two-input overlap handling and causal-narration risk earlier than the contract
needs. Paired tests and broader hypothesis testing are deferred to later
missions. This keeps the first surface small enough to validate by inspection.

### D2 — `change_point` method shape (the `level_shift_detection` question)

The initial `change_point` tool is a **single-level-shift detector over one
admissible, ordered series**. It:

- scans **candidate split points** that leave at least a declared **minimum
  number of usable observations on both sides**;
- computes the before-mean and after-mean for each candidate;
- selects the candidate with the **largest absolute standardized level
  difference**;
- reports the selected split time, the before level, the after level, the
  direction of the shift, the method revision, and sample counts on each side.

The uncertainty payload **describes the support around the selected split**; it
deliberately carries **no p-value**. The method is deterministic and inspectable:
given the same evidence, parameters, and policy version, it returns the same
split. If the usable window is too small on either side, or the requested
parameters fall outside supported bounds, the tool **refuses with a distinct
reason and returns no estimate** rather than reporting a spurious change point.
The result names a *when* and a *how much*, never a *why*.

### D3 — Smoothed average method shape (the `smoothed_pattern` question)

The smoothed average tool computes a **deterministic trailing rolling mean** over
one admissible, ordered series, using a **declared window and minimum coverage**.
It:

- does **not fill long gaps** or invent missing observations — missingness stays
  visible;
- carries, per output point or summary value, the **effective window, the usable
  count, the imputation percentage, the coverage, and the method revision**;
- when the method has **no natural confidence interval**, states explicitly that
  **uncertainty is not defined for this method** and relies on the validity and
  confound metadata instead, rather than fabricating a band.

A trailing (not centered) mean is chosen because it never uses observations from
after the point it summarizes, which is the honest shape for an agent narrating a
"recent pattern" to the operator. As with `change_point`, insufficient or stale
evidence produces a structured refusal, not a smoothed guess.

### D4 — Add reviewed analytical question types (closed vocabulary)

The two analytical questions are **not** the same as the Stage 2 descriptive
shapes (current status, recent trend, long-term control, historical baseline), so
forcing them onto existing values would distort the admissibility check and hide
the analytical sufficiency requirements. The mission therefore extends the closed
evidence-policy `QuestionType` vocabulary with two reviewed values:

- **`level_shift_detection`** — for `change_point`.
- **`smoothed_pattern`** — for the smoothed average tool.

These are **closed runtime vocabulary entries, not prose suggestions and not
user-facing labels.** No tool may pass a free-form question string; the evaluator
recognizes only reviewed values, consistent with ADR 0007's closed-vocabulary
admissibility contract.

### D5 — Closed, runtime-owned confound checklist

Every non-refusal analytical result carries a **confound checklist** drawn from a
**closed vocabulary**. This is the committed initial set:

- **`high_imputation`** — too much of the usable series was filled/imputed.
- **`low_sample_size`** — usable observations are near the minimum for the method.
- **`short_overlap_window`** — the admissible window is short relative to what the
  question needs.
- **`parameter_at_limit`** — a requested parameter sits at an allowed bound.
- **`vendor_estimate_input`** — an input value is a vendor-derived estimate, not a
  primary measurement.
- **`temporal_autocorrelation`** — successive observations are correlated, so
  apparent stability or change may be overstated.
- **`life_event_sensitive`** — the metric is one whose level is easily shifted by
  ordinary life events (travel, illness, training change), so a detected shift is
  not evidence of cause.
- **`method_uncertainty_unavailable`** — the method cannot express a natural
  uncertainty interval (the smoothed-average case in D3).

These are **closed runtime vocabulary entries owned by the implementation
contract and enforced by validation tests** — not prose suggestions. Confound
keys outside the committed set are rejected by validation. The research note may
propose keys; the mission owns the committed vocabulary and may extend it through
the same reviewed process, but agents cannot mint values like "probably fine" or
collapse distinct risks into a generic quality label.

## Alternatives rejected

- **Defer the research to a separate mission** — rejected; implementation planning
  would begin with unresolved contract choices.
- **Encode the choices only in code comments** — rejected; the planning and review
  process needs durable, citeable rationale, which is why this note exists.
- **A full significance-testing / hypothesis suite as the first slice** —
  rejected; too broad to prove the seam and too easy to overstate in n-of-1 data.
- **Correlation as the second proof tool** — considered (it is named in the
  roadmap), but deferred; two-input overlap and causal-narration risk arrive
  earlier than the contract needs.
- **Register `change_point` as a Stage 2 `change` family signal** — rejected;
  Stage 2 answer families are closed, and a level-shift estimate answers a
  different question than a before/after descriptive comparison.
- **Bayesian online change-point detection** — rejected for the first slice;
  priors and posterior explanations add review burden without proving the seam.
- **Multiple change-point segmentation** — rejected; the proof tool only needs to
  prove the contract and refusal behavior.
- **Visual-only before/after comparison** — rejected; the mission needs a
  deterministic *computed* estimate the agent can narrate.
- **Centered or exponential smoothing** — centered smoothing can use future
  observations and is harder to narrate honestly; exponential smoothing makes
  alpha another policy decision. Both deferred in favor of a trailing mean.
- **Interpolation-heavy smoothing** — rejected; missingness must stay visible.
- **Reusing `historical_baseline` / `recent_trend` for the analytical questions**
  — rejected; it distorts level-shift detection and hides analytical sufficiency.
- **Free-form question names or free-form caveat strings** — rejected; they
  violate the closed-vocabulary policy and agents cannot reliably branch on prose.
- **A single numeric quality score for confounds** — rejected; it collapses
  distinct refusal and confound reasons into one opaque number.
- **A runtime PubMed / literature check** — rejected; out of scope and a
  local-first violation for this mission. Literature grounding is a later mission.

## Consequences for implementation

For the agent picking up the contract and proof tools:

- **Build the contract, not a catalog.** The deliverable is a registry plus a
  declared tool descriptor, a post-admissibility input-series shape, and a
  mandatory result envelope (estimate or refusal, uncertainty behavior,
  `validity_status`, `is_imputed_pct`, sample size, and the closed confound
  checklist). Adding a future tool is registration against that contract, not a
  new branch in a dispatcher. This note must **not** be read as an enumeration of
  the intended statistical surface.
- **Two proof tools only:** `change_point` and the smoothed average, with the
  shapes in D2 and D3. The proof set stays narrow.
- **Keep the Stage 2 / Stage 3 boundary.** Analytical MCP wrappers delegate to the
  engine-owned analytical path and never read raw fact tables; inputs pass through
  evidence-admissibility evaluation before any computation runs. This preserves
  the boundary ADR 0007 established for Stage 2.
- **No runtime network access.** The analytical layer is local-first; no
  network-access modules or literature calls are reachable from analytical runtime
  code.
- **No diagnosis, causation, treatment, dosing, emergency guidance, or
  population-norm comparison.** Outputs describe the operator's own series against
  the operator's own history; they name a *when* and a *how much*, never a cause
  or a clinical verdict, and never compare the operator to a population norm.
- **Do not reopen Stage 2.** The closed `RESULT_FAMILIES` set is unchanged;
  `change_point` is a Stage 3 analytical tool, not a new or extended Stage 2
  `change` answer family.
- **Refusal is a first-class outcome.** Stale, inadmissible, insufficient, and
  out-of-bounds inputs each return a distinct machine-readable refusal reason and
  no estimate. Withholding untrustworthy evidence is the conservative default, as
  in ADR 0007.
- **The closed vocabularies are owned by the mission's validation tests.** The two
  analytical `QuestionType` values (D4) and the eight confound keys (D5) are
  enforced; values outside them are rejected.
