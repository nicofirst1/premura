# Audit-Consumer Contract

> Status: live contract. The stable structured surface the research trace audit skill (`src/premura/skills/research-trace-audit/`) reads. Authored by the `session-research-trace-01KSYT4A` mission; moved here from that mission's `kitty-specs/.../contracts/` bookkeeping on 2026-06-11 so its only home is a live doc. See design decision note [0009](../adr/0009-session-research-trace-and-multiplicity-disclosure.md).

The audit-consumer contract is the stable structured surface the research trace audit skill reads.

## Contract Object: Session Disclosure

Required fields:

- `schema_version`: contract version string.
- `session_id`: trace session identifier.
- `started_at_utc`: session start time.
- `warehouse_fingerprint`: warehouse context reference.
- `raw_analytical_call_count`: count of all recorded analytical calls in the session.
- `unique_hypothesis_count`: `N`, count of unique normalized examined hypotheses.
- `surfaced`: surfaced summary object.
- `refusal_breakdown`: counts by refusal reason.
- `calls`: bounded list of stable call records or references.

Additional fields the implemented disclosure also carries (additive, not required by a consumer): `disclosure_text` (the framed `K user-facing findings among N unique hypotheses examined` sentence, with the raw analytical-call count shown separately) and `calls_truncated` (set when the bounded call list was capped). The `disclosure_text` is a convenience rendering; a consumer must derive its own counts from the structured fields above, never by parsing the prose.

## Contract Object: Surfaced Summary

Required fields:

- `status`: `available` or `unavailable`.
- `count`: integer when available; null when unavailable.
- `message`: required when unavailable.
- `marks`: list of surfaced marks when available.

Rules:

- If analytical calls exist and no surfaced marks exist, `status` is `unavailable` and `count` is null.
- The canonical trace must not infer surfaced calls from effect size or final-answer text.

## Contract Object: Call Record

Required fields:

- `call_id`.
- `tool_name`.
- `hypothesis_identity`.
- `request_hash`.
- `terminal_status`: `available`, `refused`, or `error`.
- `refusal_reason`: nullable (populated only for a `refused` call).
- `error_kind`: nullable (populated only for an `error` call — a dispatch failure recorded as a first-class call).
- `result_ref`: nullable object with `result_id` and `result_hash`.
- `call_kind`: `analytical` or `evidence_source` (additive since operating-roles slice 2; defaults to `analytical`). Note: the disclosure's `calls` list contains only `analytical` records, so a consumer reading Call Records through the disclosure observes `analytical` exclusively — `evidence_source` rows are reachable only via the citation-binding read path, not this contract.
- `started_at_utc`.
- `finished_at_utc`.

Rules:

- `hypothesis_identity` is the deduplication key for `N`.
- Refused calls remain first-class records and count toward `N` if they reached data/admissibility evaluation.
- Exact retries have separate `call_id` values but the same `hypothesis_identity`.
- Only `analytical` records count toward `raw`, `N`, the refusal breakdown, and the disclosure's call list. `evidence_source` records (literature lookups such as `pubmed_fetch`) are recorded in the same store for citation binding but never appear in the multiplicity disclosure.

## Contract Object: Surfaced Mark

Required fields:

- `mark_id`.
- `call_id`.
- `role`.
- `rationale`.
- `marked_at_utc`.

Rules:

- `role` describes presentation use, not statistical strength.
- `rationale` is agent-authored context for the later audit skill.

## Forbidden Semantics

The contract must not expose or imply:

- p-values.
- statistical significance labels.
- multiplicity-corrected statistics.
- a guessed surfaced count.
- raw health fact dumps as trace payloads.

## Audit Skill Consumer

The research trace audit skill (shipped 2026-05-31) compares this contract object against a final answer and decides whether the answer disclosed search effort, hid refused or contradictory calls, overclaimed causality, or should open an issue/suggestion. Those judgments are interpretation, not measurement — they read this contract read-only and must not change the canonical trace counts.
