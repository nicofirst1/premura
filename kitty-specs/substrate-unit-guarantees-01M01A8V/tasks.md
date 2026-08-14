# Tasks: Substrate Unit Guarantees

**Input**: spec.md (FR-001..FR-010, NFR-001..NFR-004, C-001..C-005), plan.md (IC-01..IC-07) **Prerequisites**: plan.md, research.md, data-model.md, contracts/

## Work Package Manifest

| WP   | Title                                                            | Depends on             | Phase            | Subtasks  |
| ---- | ---------------------------------------------------------------- | ---------------------- | ---------------- | --------- |
| WP01 | Shared units module + read-only connection default               | —                      | 1 Substrate      | T001–T003 |
| WP02 | Load-boundary unit enforcement for measurements                  | WP01                   | 1 Substrate      | T004–T006 |
| WP03 | Parsers stop converting (lab_pdf, bmt emit unit-as-observed)     | WP02                   | 2 Simplification | T007–T009 |
| WP04 | Structured skip persistence (hp.ingest_skip)                     | WP02, WP03             | 2 Closed loops   | T010–T012 |
| WP05 | Source-kind vocabulary rail + ingest_row MCP tool                | WP02, WP04             | 3 Rail and road  | T013–T016 |
| WP06 | audit-integrity CLI verb + spelling-variant backfill migration   | WP01                   | 3 Detection      | T017–T019 |
| WP07 | Labsheet remediation: one-shot delete script + runtime procedure | WP05                   | 4 Remediation    | T020–T021 |
| WP08 | Docs made true + doctrine substrate test + live-doc sync         | WP03, WP05, WP06, WP07 | 4 Truth          | T022–T024 |

Details, owned files, and done-criteria live in each `tasks/WPNN-*.md` prompt (frontmatter is authoritative for ownership and dependencies).

## Execution lanes

- WP01 first (unblocks everything).
- Lane A (sequential, shared files): WP02 → WP03 → WP04 → WP05 → WP07.
- Lane B (parallel to Lane A after WP01): WP06.
- WP08 last — docs trail the code they describe.

## Mission-wide review gate

Every WP review and the mission review record a written pass/fail on the six-question over-engineering checklist (spec C-005): existence, abstraction budget, shrink check, one-rule-one-chokepoint, process test, reuse ladder. Reviewers also run `ruff format --check` in addition to the standard gates.
