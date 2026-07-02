---
name: research-trace-audit
description: Audit a final Premura analytical answer against its session research trace disclosure (the audit-consumer contract). REQUIRES two inputs — the structured Session Disclosure object from `research_trace_disclosure`, and the final analytical answer text. Use when an agent or reviewer says "audit this answer against the trace", "did this answer disclose its search effort", "check this analytical answer for overclaiming", or must judge whether the answer disclosed search effort and the multiplicity denominator, hid refused/errored/surfaced-unavailable calls, suppressed contradictions, or overclaimed causation/diagnosis/significance. Premura-specific; not a general critique of arbitrary agent answers.
---

# Premura research trace audit

You are auditing one Premura **final analytical answer** against the
**Session Disclosure** recorded for the session that produced it. The audit
judges honesty about *search effort* (how many hypotheses were examined to
surface the few presented), *refused / errored / unavailable* calls, suppressed
*contradictions*, and *overclaim* beyond what Premura's descriptive tools
support. You emit one structured **Audit Result** per (disclosure, answer) pair.

This skill is **Premura-specific**. It audits an answer built from a Premura
session research trace as exposed by the audit-consumer contract — not arbitrary
agent answers, and not a generic moral critique. If you were not handed a
Premura Session Disclosure, this skill does not apply.

The audit is **offline**: it reads only the two inputs you are handed. It issues
**no network call**, opens no registry, and never queries raw `hp.*` tables,
DuckDB, or session logs to reconstruct the trace. You consume the disclosure;
you do not repair, reconstruct, or mutate it.

## Required inputs

You cannot issue a real audit without **both** of these:

1. **The structured Session Disclosure object** from `research_trace_disclosure`
   — the contract object defined by
   `docs/building/architecture/AUDIT_CONSUMER_CONTRACT.md`.
   Accept it as JSON-like structured data or a faithfully pasted object. All
   counts come from its **structured fields** —
   `raw_analytical_call_count`, `unique_hypothesis_count` (`N`), `surfaced`,
   `refusal_breakdown`, and each Call Record's `terminal_status` /
   `refusal_reason` / `error_kind`. **Never** read counts out of the
   `disclosure_text` prose; it is a convenience rendering only.
2. **The final analytical answer text** — the answer the operator would see,
   built from that session.

If the structured disclosure is **missing**, the correct result is `blocked`
(or a request for the disclosure) — never a best-effort prose critique.

## When to invoke this skill

Invoke when an agent or reviewer must judge a Premura analytical answer against
its session research trace. Cues:

- "Audit this answer against the trace" / "did this answer disclose its search
  effort" / "check this analytical answer for overclaiming".
- A final answer presents a finding or two and you need to know whether it
  disclosed the multiplicity denominator, hid refusals/errors, treated a
  `surfaced.status = unavailable` session as if it had a ranked "top N", or
  escalated an association into causation/diagnosis/treatment/prediction/
  significance.

Do **not** invoke for: producing the analytical answer itself, repairing or
re-running a trace, editing trace storage, or auditing answers that have no
Premura Session Disclosure behind them.

## Read the rubric first

**Do not embed the criteria here.** The authoritative criteria registry ships
beside this file at:

> `AUDIT_RUBRIC.md`

Read it **before issuing any verdict**. It defines the four closed audit
categories, each criterion's question / evidence source / suggested-revision
hint, the verdict guidance (when a fired criterion means `needs_revision` vs
`blocked`), and the rule for adding a new criterion. If `AUDIT_RUBRIC.md` ever
disagrees with this skill on criteria detail, `AUDIT_RUBRIC.md` wins.

## Workflow

1. **Confirm both inputs are present.** No structured disclosure → `blocked`
   (or request it). Do not proceed on the answer alone.
2. **Read `AUDIT_RUBRIC.md`** end-to-end so every category is applied against
   its grounding fields.
3. **Inspect the structured counts and surfaced summary** — `unique_hypothesis_count`
   (`N`), `raw_analytical_call_count`, and `surfaced` (`status`, `count`,
   `marks`). When `surfaced.status = unavailable`, `count` is null: **never
   infer or fabricate a surfaced count** from available calls, effect size, or
   the answer's own emphasis.
4. **Inspect refusals, errors, unavailable state, and call records** — walk
   `refusal_breakdown` and each Call Record's `terminal_status` /
   `refusal_reason` / `error_kind`. A refused or errored call must not appear in
   the answer as a confident "nothing notable".
5. **Compare the final answer's claims against tool boundaries** — quote spans
   where the answer exceeds what the producing tool supports (e.g. an
   `correlate` yields an association, not a cause).
6. **Apply each of the four rubric categories** and **emit a verdict**:
   `pass`, `needs_revision`, or `blocked`.
7. **Attach concrete evidence to every non-`pass` result** — each reason carries
   an `evidence_ref` that is either a named disclosure field with its value
   (e.g. `unique_hypothesis_count = 18`, `surfaced.status = unavailable`,
   `refusal_breakdown.paired_sample_floor = 2`) or a quoted span from the answer
   (e.g. "training load caused your HRV drop"). A bare "looks overclaimed" with
   no field or quote is itself a rubric failure.

A `pass` requires that **all four categories were reviewed** and none fired —
record the review of each category, not merely the absence of a flag.

## Audit result shape

Emit the structure defined by `contracts/audit-result-contract.md` in this
mission:

- `verdict` — exactly one of `pass`, `needs_revision`, `blocked`.
- `reasons` — one per fired or noteworthy criterion, each with `criterion_id`,
  `category`, `finding`, and an `evidence_ref` (structured field-and-value, or a
  quoted answer span). At least one reason for any non-`pass` verdict.
- `suggested_revisions` — concrete wording/disclosure changes (≥ 1 for any
  non-`pass`). A revision must **never** propose changing trace storage (e.g.
  editing `unique_hypothesis_count` or back-filling `surfaced` counts) as the fix
  for an answer problem.
- `next_steps` — optional (e.g. "re-open the trace and mark surfaced calls").

## Authoritative references

Precedence — three files, three jobs:

- **`docs/building/architecture/AUDIT_CONSUMER_CONTRACT.md`**
  — defines the **trace input shape** (the Session Disclosure object and its
  fields).
- **`AUDIT_RUBRIC.md`** (beside this file) — defines the **audit criteria**.
- **`SKILL.md`** (this file) — defines **how an agent runs the audit**.

The `fixtures/` directory beside this file holds synthetic worked examples — a
Session Disclosure + answer + `expected_verdict` each — for calibration. Load one
when you want to check your reading of a category against a known verdict:
`pass.json` (all four reviewed, none fired → `pass`), `omitted-search-effort.json`
(`N` not disclosed → `needs_revision`), `hidden-refusal.json` (refusal recast as
"nothing notable" → `needs_revision`), `surfaced-unavailable.json`
(`surfaced.status = unavailable` presented as a ranked top-N → `needs_revision`),
`overclaim.json` (association presented as causation → `blocked`),
`out-of-form-citation.json` (a bare "a 2023 study" citation presented as
verified with no recognized PMID form → `needs_revision`), and
`clean-citation.json` (only a recognized-form, gate-fetched PMID citation →
`pass`). The fixtures are examples; `AUDIT_RUBRIC.md` remains the source of
criteria detail.

## Do not

- **Do not infer a surfaced count when `surfaced.status = unavailable`** — treat
  it as "no surfaced selection recorded", never as zero or as a self-ranked top-N.
- **Do not read counts from `disclosure_text`** — derive every count from the
  structured fields.
- **Do not introduce forbidden semantics yourself.** You may *flag* a p-value,
  significance label, multiplicity correction, or causal / diagnostic /
  treatment / predictive claim in the **audited answer**, but the audit result
  must never itself assert significance, causation, diagnosis, treatment, or
  prediction.
- **Do not mutate or reconstruct the trace** — no editing counts, no
  back-filling `surfaced`, no querying `hp.*` / DuckDB / logs.
- **Do not write a generic moral critique** — name what transparency means here:
  search effort, surfaced availability, refusals/errors, suppressed
  contradictions, and claim boundaries.
- **Do not require a network call** at runtime.
