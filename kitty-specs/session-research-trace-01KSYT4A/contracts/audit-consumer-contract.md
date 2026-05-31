# Audit-Consumer Contract

The audit-consumer contract is the stable structured surface a later audit skill will read. This mission does not implement the audit skill.

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
- `refusal_reason`: nullable.
- `result_ref`: nullable object with `result_id` and `result_hash`.
- `started_at_utc`.
- `finished_at_utc`.

Rules:

- `hypothesis_identity` is the deduplication key for `N`.
- Refused calls remain first-class records and count toward `N` if they reached data/admissibility evaluation.
- Exact retries have separate `call_id` values but the same `hypothesis_identity`.

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

## Audit Skill Follow-On

A later audit skill may compare this contract object against a final answer and decide whether the answer disclosed search effort, hid refused or contradictory calls, overclaimed causality, or should open an issue/suggestion. Those judgments are out of scope for this mission and must not change the canonical trace counts.
