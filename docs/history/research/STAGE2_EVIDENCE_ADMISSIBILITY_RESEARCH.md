# premura — Stage 2 Evidence Admissibility Research

> Status: proposal/archive. Research summary to inform a future mission spec,
> not a runtime contract.
>
> Generated: 2026-05-29
> Scope: pre-Stage-3 research on deterministic evidence selection for personal
> health analysis.

## Purpose

Capture the research used to shape Premura's next analytical step: a
conservative Stage 2 policy for deciding which personal-health evidence is
admissible before richer analysis or agent narration happens.

This note is intentionally general. It does not define MCP tools, UI behavior,
or diagnostic output. It is about the grounded layer underneath those later
stages.

## Summary

The main safety problem is not only generic model hallucination. The more
dangerous failure is using the wrong evidence for the question, especially old
or weak evidence presented as if it described the present.

The literature points to the same recurring bottlenecks:

- stale evidence treated as current
- missing provenance for claims and summaries
- overconfident tone despite weak evidence
- confounding and missingness in self-tracking data
- weak refusal boundaries, where descriptive summaries drift into advice or
  diagnosis

The research supports a deterministic admissibility layer that sits in Stage 2
and decides, before any broader analysis:

- what kind of question is being asked
- what kinds of evidence are eligible for that question
- whether the available evidence is recent enough and dense enough
- when the system should refuse rather than narrate

## Main Research Findings

### 1. Freshness is not one universal timeout

The meaningful recency of a measurement depends on both:

- the metric family
- the question being asked

The same datum can be valid for one question and invalid for another. An older
`A1C` can still support a long-term-control question, but it is not honest
evidence for "what is happening right now?"

### 2. Question type matters as much as metric type

The literature repeatedly separates at least four question shapes:

- **Current status**: what is true now or near now
- **Recent trend**: which way something has been moving over recent days or
  weeks
- **Long-term control**: what a marker says about control over weeks or months
- **Historical baseline**: what the operator's own normal or longer history
  looks like

This is a useful framing for Premura because it keeps Stage 2 from treating all
measurements as one undifferentiated stream.

### 3. Sparse and missing data are safety issues, not cosmetic issues

When evidence is sparse, non-wear can be mistaken for inactivity, missingness
can be mistaken for normality, and time-averaged summaries can hide a recent
change.

The safer default is to keep missing, sparse, stale, and wrong-kind-of-evidence
states separate rather than collapsing them into one generic "low quality"
label.

### 4. Provenance has to travel with the evidence

Health-facing claims are hard to trust if the system cannot show where they came
from. At minimum, medically meaningful claims should carry:

- source or origin
- timestamp or effective date
- measurement context when known
- caveats about sparsity, imputation, or method sensitivity

### 5. Refusal is part of honesty

The literature does not support pushing through weak evidence with a softer tone.
It supports abstention when the remaining evidence is too old, too sparse, or
semantically wrong for the question.

## Bottlenecks That Matter Most For Premura

### Stale evidence treated as current

Why it matters:
Old labs, wearable summaries, or historical baselines can sound plausible while
being wrong for a present-tense question.

Implication:
Stage 2 should reject or clearly downgrade evidence that is too old for the
question shape.

### Missing provenance

Why it matters:
The operator and the reviewing agent need to know whether a statement came from
the user's own warehouse, a derived summary, or model inference.

Implication:
Later outputs should be traceable back to time-stamped personal evidence.

### Overconfident tone

Why it matters:
Fluent output can create false trust even when the evidence base is weak.

Implication:
Low-evidence states should become refusal, clarification, or explicit caveat,
not confident narrative.

### Confounding in longitudinal self-tracking data

Why it matters:
Travel, illness, alcohol, sensor drift, adherence, algorithm changes, and life
events can all distort interpretation.

Implication:
Premura should treat self-tracking data as descriptive and baseline-relative,
not causal or diagnostic.

### Weak refusal boundaries

Why it matters:
A system that starts from descriptive summaries can drift into diagnosis,
treatment, or action advice if boundaries are not explicit.

Implication:
The first analytical layer should stay non-diagnostic and descriptive, with
clear refusal when the question requires stronger grounding.

## Metric Families And Temporal Semantics

The research supports a compact policy taxonomy rather than one rule per metric.

| Metric family | Typical temporal meaning | Honest question shapes | Main caution |
|---|---|---|---|
| Stable profile facts | Effective-dated context, not expiring measurements | Historical baseline, denominator/context questions | Valid until superseded, not "fresh until stale" |
| Acute spot measures | Point-in-time state | Current status, what was true then | Becomes stale quickly |
| Home blood pressure | Short-run serial average, not one isolated truth | Current reading, recent average/trend | Single readings are noisy |
| CGM | High-frequency recent pattern | Current status, recent trend, variability | Needs enough recent coverage |
| A1C | Long-horizon control marker | Long-term control, broad change over months | Not a current-state marker |
| Lipids | Slow-response chronic-risk/control marker | Long-term control, therapy response, historical baseline | Weak as a same-week signal |
| Sparse lab panels | Collection-time observations whose meaning varies by analyte | What was true then, slower trend, personal-baseline comparison | Often needs analyte-specific caution |
| Weight | Current body mass plus slow trajectory | Current status, recent trend, long-term trajectory | Day-to-day noise can mislead |
| Body composition | Slow-moving phenotype or trajectory | Historical baseline, long-term trend | Method-sensitive, weak for short-horizon claims |
| Activity metrics | Recent behavior load | Recent trend, adherence, historical baseline | A single day can mislead |
| Sleep metrics | Multi-night recent pattern | Recent trend, deviation from own baseline | Wearable scoring is not hard truth |
| HRV / resting HR / recovery metrics | Baseline-relative recent physiology | Deviation from own baseline, recent trend | Context-sensitive, weakly standardized |

## Where Hard Windows Are More Defensible

Harder windows are more defensible when the metric already has a widely used
measurement schedule or integration horizon.

Examples the research supports more strongly:

- `A1C` as a marker of roughly the last three months, with recent weeks weighing
  more heavily
- home blood pressure interpreted from multiple readings over a short run, not a
  single isolated value
- CGM interpreted from a recent window with enough wear coverage
- weekly framing for activity targets because the public-health guidance is
  written that way
- lipids rechecked over weeks to months after a therapy change, not day to day

## Where Caveats Are More Honest Than Hard Windows

Many metrics are too method-sensitive, context-sensitive, or analyte-specific to
justify a confident universal timeout.

Examples where caveats are usually more honest than a single hard cutoff:

- HRV
- resting heart rate
- wearable sleep staging
- day-to-day weight changes
- body-fat estimates from impedance methods
- many sparse lab panels whose interpretation depends on the analyte and the
  collection context

For these, Premura should prefer policy classes like "baseline-relative" or
"method-sensitive; interpret cautiously" over pretending to have a universal
clinical rule.

## Suggested Policy Shape For A Future Software Mission

The eventual software mission should implement shared policy classes, not a
scattered set of ad hoc exceptions.

A useful plain-English model would let a metric or metric family declare:

- what question shapes it can support
- whether it uses a strict window, a preferred window, a baseline-relative
  policy, or caveat-only handling
- what minimum evidence density or coverage it needs when relevant
- what standing cautions must always travel with the result

Possible policy classes:

- `assertion_until_superseded`
- `point_in_time_acute`
- `serial_average_short_run`
- `rolling_recent_pattern`
- `integrated_long_term_control`
- `baseline_relative`
- `slow_trajectory_method_sensitive`
- `sparse_lab_analyte_specific`

These names are implementation-facing placeholders only. The user-facing prose
should stay plain English.

## Recommended Stage 2 Flow

The research supports a conservative sequence:

1. Classify the question as current status, recent trend, long-term control, or
   historical baseline.
2. Select candidate evidence from the warehouse.
3. Filter that evidence by temporal admissibility for the question type.
4. Check sufficiency, coverage, and context.
5. Keep admissible evidence separate from rejected evidence.
6. Refuse if nothing solid remains.

This is the key safety point: Stage 2 should not let a later model see
everything and decide informally. It should pre-filter to an evidence bundle
that is temporally honest.

## Recommendation

Before building broader deterministic analytical tools, Premura should first
settle a plain-English evidence-admissibility policy for Stage 2.

That policy should answer:

- which question types Premura recognizes
- which metric families can support which question types
- when evidence is too old or too sparse to use
- when a result needs caveats instead of a hard verdict
- when the correct behavior is refusal rather than narration

Once that policy is settled, a follow-on software mission can implement the
first deterministic analytical tools on top of it.

## Source Anchors

This research summary was grounded in the following kinds of sources:

- general health-AI safety and evaluation reviews in `JAMA`, `Annals of Internal
  Medicine`, `Lancet Digital Health`, and related journals
- FDA-oriented discussion of health-AI life-cycle monitoring and local
  post-deployment evaluation
- reviews of wearable validity, digital phenotyping, and uncertainty handling
- guidance and consensus statements around `A1C`, home blood pressure, CGM,
  lipid follow-up, and weekly activity framing
- lab-medicine discussion of biological variation and reference-change thinking
  for repeated sparse lab interpretation

Specific source anchors used during the research included work or guidance from
`NIDDK`, `ATTD` consensus material on CGM interpretation, `ACC/AHA` blood
pressure and lipid guidance as summarized in clinician-facing references,
`WHO` physical-activity guidance, and health-AI safety articles discussing
uncertainty, abstention, and real-world evaluation.
