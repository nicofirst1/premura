---
name: research-trace-audit
description: Audit a final Premura analytical answer against its structured Session Disclosure (audit-consumer contract). REQUIRES both: the disclosure object from `research_trace_disclosure` and the final answer text. Use when an agent or reviewer must audit an answer against its trace — search-effort disclosure, hidden refusals/errors, suppressed contradictions, overclaiming. Premura-specific; not general answer critique.
---

# Premura research trace audit

You are auditing one Premura **final analytical answer** against the **Session Disclosure** recorded for the session that produced it. The audit judges honesty about _search effort_ (how many hypotheses were examined to surface the few presented), _refused / errored / unavailable_ calls, suppressed _contradictions_, and _overclaim_ beyond what Premura's descriptive tools support. You emit one structured **Audit Result** per (disclosure, answer) pair.

This skill is **Premura-specific**. It audits an answer built from a Premura session research trace as exposed by the audit-consumer contract — not arbitrary agent answers, and not a generic moral critique. If you were not handed a Premura Session Disclosure, this skill does not apply.

The audit is **offline**: it reads only the two inputs you are handed. It issues **no network call**, opens no registry, and never queries raw `hp.*` tables, DuckDB, or session logs to reconstruct the trace. You consume the disclosure; you do not repair, reconstruct, or mutate it.

## Required inputs

You cannot issue a real audit without **both** of these:

1. **The structured Session Disclosure object** from `research_trace_disclosure` — the contract object defined by `src/premura/AUDIT_CONSUMER_CONTRACT.md` (see it for the full field list). Accept it as JSON-like structured data or a faithfully pasted object. All counts come from its structured fields — **never** from the `disclosure_text` prose, which is a convenience rendering only.
2. **The final analytical answer text** — the answer the operator would see, built from that session.

If the structured disclosure is **missing**, the correct result is `blocked` (or a request for the disclosure) — never a best-effort prose critique.

## When to invoke this skill

Invoke when an agent or reviewer must judge a Premura analytical answer against its session research trace. Cues:

- "Audit this answer against the trace" / "did this answer disclose its search effort" / "check this analytical answer for overclaiming".
- A final answer presents a finding or two and you need to know whether it disclosed the multiplicity denominator, hid refusals/errors, treated a `surfaced.status = unavailable` session as if it had a ranked "top N", or escalated an association into causation/diagnosis/treatment/prediction/ significance.

Do **not** invoke for: producing the analytical answer itself, repairing or re-running a trace, editing trace storage, or auditing answers that have no Premura Session Disclosure behind them.

## Read the rubric first

**Do not embed the criteria here.** The authoritative criteria registry ships beside this file at:

> `AUDIT_RUBRIC.md`

Read it **before issuing any verdict**. It defines the four closed audit categories, each criterion's question / evidence source / suggested-revision hint, the verdict guidance (when a fired criterion means `needs_revision` vs `blocked`), and the rule for adding a new criterion. If `AUDIT_RUBRIC.md` ever disagrees with this skill on criteria detail, `AUDIT_RUBRIC.md` wins.

## Workflow

1. **Confirm both inputs are present.** No structured disclosure → `blocked` (or request it). Do not proceed on the answer alone.
2. **Read `AUDIT_RUBRIC.md`** end-to-end so every category is applied against its grounding fields.
3. **Check `search_effort_disclosure`** — grounding fields: `unique_hypothesis_count` (`N`), `raw_analytical_call_count`, `surfaced` (`status`, `count`, `marks`). See `AUDIT_RUBRIC.md` for the criterion.
4. **Check `refused_or_unavailable_handling`** — grounding fields: `refusal_breakdown`, each Call Record's `terminal_status` / `refusal_reason` / `error_kind`, `surfaced.status`. See `AUDIT_RUBRIC.md` for the criteria.
5. **Check `overclaim_boundary`** — grounding fields: quoted answer spans against the producing call's tool semantics. See `AUDIT_RUBRIC.md` for the criteria.
6. **Apply each of the four rubric categories** and **emit a verdict**: `pass`, `needs_revision`, or `blocked`.
7. **Attach concrete evidence to every non-`pass` result** — each reason carries an `evidence_ref` that is either a named disclosure field with its value (e.g. `unique_hypothesis_count = 18`, `surfaced.status = unavailable`, `refusal_breakdown.paired_sample_floor = 2`) or a quoted span from the answer (e.g. "training load caused your HRV drop"). A bare "looks overclaimed" with no field or quote is itself a rubric failure.

A `pass` requires that **all four categories were reviewed** and none fired — record the review of each category, not merely the absence of a flag.

## Audit result shape

This is the single authoritative definition of the output shape — emit exactly this structure:

- `verdict` — exactly one of `pass`, `needs_revision`, `blocked`.
- `reasons` — one per fired or noteworthy criterion, each with `criterion_id`, `category`, `finding`, and an `evidence_ref` (structured field-and-value, or a quoted answer span). At least one reason for any non-`pass` verdict. A reason may _flag_ a forbidden semantic in the audited answer (significance, causation, diagnosis, treatment, prediction) but must never itself assert one.
- `suggested_revisions` — concrete wording/disclosure changes (≥ 1 for any non-`pass`). A revision must **never** propose changing trace storage (e.g. editing `unique_hypothesis_count` or back-filling `surfaced` counts) as the fix for an answer problem.
- `next_steps` — optional (e.g. "re-open the trace and mark surfaced calls").

## Authoritative references

Precedence — three files, three jobs:

- **`src/premura/AUDIT_CONSUMER_CONTRACT.md`** — defines the **trace input shape** (the Session Disclosure object and its fields).
- **`AUDIT_RUBRIC.md`** (beside this file) — defines the **audit criteria**.
- **`SKILL.md`** (this file) — defines **how an agent runs the audit**.

The `fixtures/` directory beside this file holds synthetic worked examples — a Session Disclosure + answer + `expected_verdict` each — for calibration, one per criterion (see `AUDIT_RUBRIC.md` for which fixture exercises which criterion).
