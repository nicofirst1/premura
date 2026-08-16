# Mission Specification: Substrate Unit Guarantees

**Mission Branch**: `substrate-unit-guarantees-01M01A8V`
**Created**: 2026-08-14
**Status**: Draft
**Input**: User description: "Global re-engineering around the labsheet incident: unit guarantees moved from per-parser convention into the load boundary, a paved road cheaper than the bypass, and closed loops so refusals are visible. Every review step must focus on over-engineering."

## Background (incident, 2026-08-14)

A four-agent investigation established: the warehouse holds magnitude-class wrong-unit rows (all 20 `blood_glucose` rows are mg/dl values under canonical `mmol_per_l`; HbA1c IFCC values stored as `%`; mis-scaled electrolytes) plus 74 metrics with spelling-only unit variants. Current `premura ingest` is not the cause — every polluted row carries `source_kind='labsheet'`, a write path with no code in this repo: an operating agent bypassed the parser pipeline and wrote rows directly, because the sanctioned path (author a full parser) costs real engineering for a five-row spreadsheet and nothing mechanical stops a raw write. Unit enforcement exists only as per-parser convention (`lab_pdf` converts-or-refuses; `bmt` silently passes unknown units through); `fact_interval` units are forced to canonical at load while `fact_measurement` units load verbatim; `IngestBatch.skipped_rows`/`unmapped_metrics` are computed and then dropped. GitHub: #113 (this mission's core), #111 (the blood-glucose instance), #114 (out of scope).

Governing principle (added to doctrine by this mission): **fewer, lower, harder rails** — move each guarantee to the one chokepoint where it cannot be bypassed, provide a paved road cheaper than the bypass, then delete the ceremony the rail replaces. The test for every guarantee: *what happens if an agent simply doesn't follow the process? If bad data lands silently, the guarantee is fiction.*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The warehouse refuses wrong-unit data at the boundary (Priority: P1)

As the operating agent (or any writer), every measurement I load either lands in its metric's canonical unit or is refused row-by-row and recorded — regardless of which parser or path produced it. Parsers report the unit as observed; one shared conversion home converts; the loader is the sole place that writes a canonical unit label.

**Why this priority**: this is the substrate rail. Without it every other change is ceremony; with it, the labsheet class of corruption becomes structurally impossible through the sanctioned seam.

**Independent Test**: ingest a synthetic batch whose rows use a convertible non-canonical unit (e.g. lb), an already-canonical unit, and an unconvertible unit — assert converted, untouched, and refused-but-recorded respectively, batch commits.

**Acceptance Scenarios**:

1. **Given** a measurement in a convertible non-canonical unit (e.g. lb for a kg metric), **When** it is loaded, **Then** the stored value is converted and the stored unit equals `dim_metric.canonical_unit`.
2. **Given** a batch containing one unconvertible-unit row and one good row, **When** loaded, **Then** the good row lands, the bad row is absent from `hp.fact_measurement`, the refusal is recorded, and `load()` does not raise.
3. **Given** any completed ingest, **When** the warehouse is queried, **Then** no `fact_measurement.unit` differs from its metric's `canonical_unit`.

---

### User Story 2 - A paved road cheaper than the bypass (Priority: P2)

As a runtime agent holding manually-transcribed data (a spreadsheet, a single lab value), I can resolve a column label to a canonical `metric_id` and load rows through a bounded agent-surface tool — with mandatory provenance — in two tool calls. Unsanctioned writes fail loudly: any batch whose `source_kind` is outside the registered vocabulary is refused before a single row is written.

**Why this priority**: the incident happened because the bypass was cheaper than compliance. The rail (vocabulary check) and the road (bounded load tool) must ship together or agents will route around the rail.

**Independent Test**: end-to-end tool call → warehouse row; and the bypass regression — `loader.load()` with `source_kind='labsheet'` raises before any write.

**Acceptance Scenarios**:

1. **Given** a spreadsheet column label, **When** the agent asks the metric-lookup op, **Then** it receives the same canonical `metric_id` a parser author would get.
2. **Given** a valid manual row with provenance, **When** loaded via the tool, **Then** it lands in `hp.fact_measurement` under the manual source kind, subject to the same unit boundary as every parser.
3. **Given** a manual row without provenance, **When** submitted, **Then** it is refused before reaching the loader.
4. **Given** a batch with an unregistered `source_kind`, **When** loaded, **Then** the load raises and zero rows are written.

---

### User Story 3 - Refusals and integrity are visible (Priority: P3)

As the operating agent or maintainer, every refused or skipped row is queryable from the warehouse (kind, field, units, reason), and one CLI verb reports integrity: rows whose unit differs from canonical, and source kinds outside the vocabulary. Legacy spelling-only variants are normalized; the labsheet pollution has a reviewed, one-shot removal path plus a documented re-entry procedure.

**Why this priority**: closed loops. The incident stayed invisible because skips were computed then dropped and no detection query existed.

**Independent Test**: refuse a row, query it back from the warehouse; run the audit verb against seeded good/bad warehouses and assert findings.

**Acceptance Scenarios**:

1. **Given** a refused row, **When** the batch finishes, **Then** a skip record with kind/field/from-unit/to-unit/reason is queryable and joined to its ingest run.
2. **Given** a warehouse with one non-canonical-unit row and one unregistered source kind, **When** the audit verb runs, **Then** both are reported; **Given** a clean warehouse, **Then** zero findings.
3. **Given** a legacy row whose unit differs from canonical only in spelling, **When** migrations run, **Then** it is relabeled without value change; **Given** a magnitude-wrong row, **Then** it is untouched.

---

### User Story 4 - Contracts tell the truth (Priority: P4)

As a future maintainer or agent, every documented guarantee names its mechanical enforcement home, the parser contract describes the real batch-level vs row-level failure split, the runtime operating guide names the paved road and explicitly forbids direct warehouse writes, and doctrine carries the substrate test with this incident as the worked example.

**Why this priority**: docs that overstate guarantees caused the false "wontfix" on #111. Truthful docs are cheap once the mechanics exist.

**Independent Test**: doc lint gates pass; each updated claim is spot-checked against shipped behavior.

**Acceptance Scenarios**:

1. **Given** the parser contract, **When** read after this mission, **Then** its failure-mode claims match `loader.load()`'s actual behavior.
2. **Given** the runtime operating guide, **When** an agent needs to load one-off data, **Then** the documented answer is the paved-road tool and direct warehouse writes are explicitly out of bounds.

### Edge Cases

- Batch mixing convertible, identity, and unconvertible units → partial load, refusals recorded, no raise (US1-2).
- Unregistered `source_kind` → raise before any write, including the ingest-run bookkeeping row if it would orphan (US2-4).
- Manual load missing provenance → refused pre-loader (US2-3).
- Spelling-only variant vs magnitude-wrong legacy row → backfill relabels the former, never touches the latter (US3-3).
- Migration double-run → idempotent, no duplicates, no errors.
- Metric with no conversion rule for an observed unit pair → refuse, never guess, never pass through.
- BMT wide-format has no per-row unit string → its config-declared unit assumption stays at the parser and is documented as such (scope exception).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Shared unit module: one home for unit spelling normalization and value conversion, table-driven, with a stated rule for adding entries; refusal (`None`) when no rule applies. | US1 | High | Open |
| FR-002 | Load-boundary enforcement: every `fact_measurement` row is converted to canonical or refused at `loader.load()`; the stored unit label is always `dim_metric.canonical_unit`; observed unit preserved in row payload. | US1 | High | Open |
| FR-003 | Structured skip persistence: unit refusals, parser skipped rows, and unmapped metrics are persisted queryably, joined to their ingest run. | US3 | High | Open |
| FR-004 | Parser simplification: parsers emit unit-as-observed; parser-local conversion logic is deleted; no parser decides unit correctness. | US1 | High | Open |
| FR-005 | Source-kind vocabulary rail: loads with a `source_kind` outside the registered vocabulary (plus the manual kind) raise before any write. | US2 | High | Open |
| FR-006 | Paved road: one collapsed-parameterized agent-surface tool offering metric lookup and single-row manual load with mandatory provenance, routed through `loader.load()`. | US2 | High | Open |
| FR-007 | Integrity audit verb: CLI reports non-canonical-unit rows and out-of-vocabulary source kinds. | US3 | Medium | Open |
| FR-008 | Spelling-variant backfill: idempotent migration relabeling only vetted spelling-equal pairs; magnitude-wrong rows excluded. | US3 | Medium | Open |
| FR-009 | Labsheet remediation mechanism: reviewed one-shot delete script (with dry-run count) plus documented runtime re-entry procedure; execution is post-merge, on the operator machine. | US3 | Medium | Open |
| FR-010 | Docs made true: parser contract, contributing guide, stages/spec docs, update strategy, runtime operating guide (paved road named; direct warehouse writes forbidden), doctrine substrate-test section, live-doc sync (status/roadmap, tool-count claims). | US4 | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Net-diff discipline | `lab_pdf.py` and `bmt.py` line counts strictly decrease; no new abstraction lands that is not traceable to an FR (over-engineering review gate, recorded per WP). | Maintainability | High | Open |
| NFR-002 | No silent loss | Every row the loader refuses is queryable from the warehouse; refusal counts reported by the loader equal persisted skip rows for the batch. | Reliability | High | Open |
| NFR-003 | Bypass regression-proof | A load with an unregistered `source_kind` writes zero rows and raises; covered by a dedicated test that would have caught the labsheet incident. | Integrity | High | Open |
| NFR-004 | Migration idempotency | All new migrations are replay-safe: double-run produces no errors and no state change (test-enforced). | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No PHI in repo | All fixtures synthetic; no real operator data, values, dates, or filenames in code, tests, or specs. | Regulatory | High | Open |
| C-002 | Migrations stay replay-forever | `store/migrations/` remains additive/idempotent-only; the destructive labsheet delete ships as a hand-run one-shot under `ops/`, never a numbered migration. | Technical | High | Open |
| C-003 | Collapsed tool surface | The paved road adds at most one parameterized tool to the default MCP surface, per the existing collapsed-surface convention. | Technical | Medium | Open |
| C-004 | Out of scope | #114 (extraction label mangling), a full `premura rebuild` verb, BMT wide-format unit redesign, re-entering the operator's data (post-merge runtime work). | Business | High | Open |
| C-005 | Over-engineering review gate | Every WP review and the mission review record a written pass/fail on the six-question over-engineering checklist (existence, abstraction budget, shrink check, one-rule-one-chokepoint, process test, reuse ladder); mechanism untraceable to an FR fails review even with green tests. | Process | High | Open |

### Key Entities

- **Canonical unit vocabulary**: per-metric target unit, declared once in the metric ontology; the only unit the warehouse stores.
- **Conversion rule**: a (from-unit, to-unit[, metric]) → factor/affine mapping in the shared unit module; absence of a rule means refusal, never pass-through.
- **Ingest skip record**: durable row-level record of anything the boundary refused or a parser skipped: kind, raw field, metric, from/to units, reason, ingest-run linkage.
- **Source-kind vocabulary**: the registered parser source kinds plus one manual-load kind; membership is enforced at the load boundary.
- **Manual load row**: a single agent-submitted measurement with mandatory plain-text provenance, entering through the same boundary as parser output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After remediation, the integrity audit reports zero non-canonical-unit rows and zero out-of-vocabulary source kinds on the real warehouse.
- **SC-002**: Replaying the incident (any unregistered `source_kind` through the sanctioned seam) fails loudly with zero rows written.
- **SC-003**: Loading one manually-transcribed value takes at most two agent tool calls (lookup, load) — cheaper than any bypass.
- **SC-004**: Zero unit-conversion logic remains in any parser (grep-verifiable); exactly one conversion home exists.
- **SC-005**: Every post-mission refusal is queryable from the warehouse with kind, units, and reason.
- **SC-006**: The mission's net line delta outside tests and docs is roughly neutral: shared-module additions offset by parser deletions (over-engineering gate evidence).
