# Phase 1 Data Model — Research Trace Audit Skill

> No database tables, no migration, no `hp.*`/`trace.*` change (C-001). This is a **conceptual**
> model of the skill's inputs, working artifacts, and outputs, plus the on-disk shape of the
> checked-in fixtures. "Validation rules" are the rubric/contract rules a reviewer can check.

## Entity: Session Disclosure  *(input — read-only, owned by the trace)*

The structured audit-consumer object produced by `research_trace_disclosure`. **Consumed, never
produced or mutated by this skill.** Defined by
`kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`.

- Fields used by the skill: `schema_version`, `session_id`, `started_at_utc`,
  `warehouse_fingerprint`, `raw_analytical_call_count`, `unique_hypothesis_count` (`N`),
  `surfaced` (Surfaced Summary), `refusal_breakdown`, `calls` (list of Call Record),
  `calls_truncated`.
- **Rule:** counts are read from these structured fields only; never parsed from
  `disclosure_text` (FR-006, C-002). When `calls_truncated` is set, summary counts are
  authoritative — the skill does not require every raw call (Edge Case: bounded/truncated list).

### Sub-entity: Surfaced Summary

- `status` (`available` | `unavailable`), `count` (int | null), `message` (required when
  unavailable), `marks` (list of Surfaced Mark).
- **Rule:** when `status = unavailable`, the skill treats missing surfaced marks as a **review
  issue** and never infers a surfaced count from prose or effect size (FR-008, C-002, Scenario 2).

### Sub-entity: Call Record

- `call_id`, `tool_name`, `hypothesis_identity`, `request_hash`,
  `terminal_status` (`available` | `refused` | `error`), `refusal_reason` (nullable),
  `error_kind` (nullable), `result_ref` (nullable), `started_at_utc`, `finished_at_utc`.
- **Rule:** refused/errored calls are first-class evidence; the skill must inspect them before
  marking an answer acceptable (FR-009, Scenario 3).

## Entity: Final Analytical Answer  *(input)*

- The text/response under audit.
- **Rule:** the skill obtains **both** the Session Disclosure and the answer text before issuing
  any judgment (FR-007).

## Entity: Audit Rubric  *(working artifact — the bounded registry)*

The criteria the skill applies, expressed a level above a fixed checklist.

- Fields per **Audit Criterion**: `id`, `category` (one of: `search_effort_disclosure`,
  `refused_or_unavailable_handling`, `contradiction_handling`, `overclaim_boundary`),
  `question` (what the reviewer asks), `evidence_source` (which disclosure field / answer span
  grounds it), `failure_modes`, `suggested_revision_hint`.
- **Rule (Design Altitude):** the rubric defines the *categories* and a **rule for adding a
  criterion** (`contracts/rubric-criterion-contract.md`); it is not a closed list of banned
  phrases. New analytical tools may introduce new criteria via that rule without redefining the
  skill.

## Entity: Audit Result  *(output)*

Defined by `contracts/audit-result-contract.md`.

- `verdict` (`pass` | `needs_revision` | `blocked`), `reasons` (list, each with an
  `evidence_ref`), `suggested_revisions` (list), `next_steps` (optional).
- **Rule:** every non-`pass` verdict carries ≥ 1 concrete evidence reference drawn from the
  disclosure fields or a quoted answer span (NFR-003, SC-003).

## Entity: Audit Fixture  *(checked-in test artifact)*

On-disk under `src/premura/skills/research-trace-audit/fixtures/`. One JSON per case.

- Shape: `{ "disclosure": <Session Disclosure>, "final_answer": <string>, "expected_verdict":
  <pass|needs_revision|blocked>, "expected_reason_categories": [<category>...] }`.
- Required cases (SC-002): `pass`, `omitted-search-effort`, `hidden-refusal`,
  `surfaced-unavailable`, `overclaim`.
- **Rule:** disclosures are **synthetic** — no real `hp.*` rows, no PHI (risk boundary 5). Each
  fixture is authored with its expected verdict **before** the rubric prose (DIRECTIVE_034).

## Entity: Skill Packaging Recommendation  *(WP0 output)*

- `recommendation` (`adopt` | `defer` | `reject`), `targets` (supported install homes),
  `verification_check` per target (NFR-006), `rationale`, `sources` (≥ 3 or stated reason).
- **Rule:** kept separate from the audit logic (C-006); gates WP3's installer scope.
