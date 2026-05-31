# Implementation Plan: Session Research Trace and Multiplicity Disclosure
*Path: templates/plan-template.md*

**Branch**: `master` | **Date**: 2026-05-31 | **Spec**: `kitty-specs/session-research-trace-01KSYT4A/spec.md`
**Input**: Feature specification from `kitty-specs/session-research-trace-01KSYT4A/spec.md`

## Summary

Add a session-scoped, append-only research trace at the MCP boundary so Premura can disclose search effort as `K user-facing findings among N unique hypotheses examined`. The analytical engine remains stateless and byte-deterministic; the MCP boundary opens explicit research sessions, records analytical calls before/after dispatch, lets the agent mark surfaced results, and exports a structured disclosure plus a stable audit-consumer contract. The audit skill that interprets the trace and turns findings into issues, PRs, or suggestions remains out of scope.

## Engineering Alignment

- The session ledger lives at the MCP boundary, not in the analytical engine.
- Sessions are explicitly opened through the MCP surface and identified by a stable `session_id`.
- The canonical ledger is structured, append-only DuckDB data in a dedicated non-`hp.*` schema: `trace.*`.
- Markdown/JSON exports are generated from the structured trace; they are not canonical records.
- `N` means unique examined hypotheses after deterministic normalization; raw analytical calls are reported separately.
- Refused analytical calls count toward `N` if they reached data or evidence/admissibility evaluation.
- `K` means explicitly marked user-facing findings; if no marks exist, surfaced count is unavailable, not guessed.
- The audit skill is designed for through a stable consumer contract, but not implemented in this mission.

## Technical Context

**Language/Version**: Python 3.11+.
**Primary Dependencies**: Existing project stack: DuckDB, Typer/Rich, Pydantic where useful for boundary models, FastMCP, pytest, ruff, mypy. No new external service or network dependency.
**Storage**: Existing local DuckDB warehouse file. Add migration `005_trace_audit.sql` with a dedicated `trace.*` schema; no trace tables under `hp.*`.
**Testing**: pytest. Test-first implementation is required. Tests should exercise behavior through public boundaries: MCP entrypoint wrappers, trace store public functions, migration/schema initialization, and exported disclosure output. Quality gates before review handoff: `ruff`, changed-scope `mypy`, and `pytest -q`.
**Target Platform**: Local-first macOS Python toolchain, preserving DuckDB portability.
**Project Type**: Single Python package plus docs/spec artifacts.
**Performance Goals**: A disclosure query for a session with up to 500 recorded calls returns in under 1 second on the reference local warehouse.
**Constraints**: Engine purity: no clock, session state, filesystem, network, or trace writes in `premura.engine`. Trace data is tool-use provenance, not health data, and must not enter encrypted health export semantics. No p-values, significance labels, or audit-skill interpretation in this mission.
**Scale/Scope**: One additive trace subsystem, one migration, explicit MCP trace tools, analytical-call recording around the existing default analytical wrappers, contracts/docs updates, and live-doc sync.

## Planning Questions Answered

| Question | Decision |
|---|---|
| Should research sessions be explicit or implicit? | Explicit. The MCP surface opens a session and returns a stable `session_id`; tracing is reproducible and testable. |
| Where does state live? | At the MCP boundary in `premura.trace` and `trace.*` DuckDB tables, never in the engine. |
| What is canonical? | Structured append-only trace rows. Markdown/JSON exports are generated views. |
| What counts toward `N`? | Unique normalized examined hypotheses, including refused calls that reached data/admissibility; exact retries and non-analytical calls do not count. |
| What determines `K`? | Explicit surfaced marks made through the session layer; absence of marks means `K` is unavailable. |
| Is the audit skill in scope? | No. This mission ships the trace and audit-consumer contract only. |

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Local-first / offline**: Pass. Trace lives in the existing local DuckDB warehouse and adds no network dependency.
- **Agent-first, human-first purpose**: Pass. The trace is an agent-operated MCP ledger that produces human-understandable disclosure.
- **Design a level above**: Pass. The plan defines normalized hypothesis identity as a per-tool declaration rule, not a central enumerated counting switch.
- **Scientific honesty**: Pass. The disclosure reports search effort and explicitly avoids p-values, significance labels, and fake multiplicity correction.
- **PHI hygiene**: Pass with implementation constraint. Trace records tool-use provenance and compact references; they must avoid storing raw health fact payloads beyond stable hashes/compact envelopes allowed by the contract.
- **Test-first and public-boundary tests**: Pass. Implementation work must begin from failing tests that drive public behavior.
- **Quality gates**: Pass. `ruff`, changed-scope `mypy`, and `pytest -q` are required before review handoff.

No charter violations are justified for this mission.

## Project Structure

### Documentation (this feature)

```text
kitty-specs/session-research-trace-01KSYT4A/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── audit-consumer-contract.md
│   └── mcp-trace-tools.md
└── spec.md
```

### Source Code (repository root)

```text
src/premura/
├── trace.py                         # New trace store/service surface
├── mcp/
│   └── entrypoint.py                # Add explicit trace tools and recording around analytical wrappers
└── store/
    └── migrations/
        └── 005_trace_audit.sql      # New trace.* schema and append-only tables

tests/
├── test_trace_store.py              # Schema, append-only, disclosure counts, hashing/identity behavior
├── test_mcp_trace_tools.py          # Open/mark/disclosure tools through MCP boundary
└── test_mcp_trace_recording.py      # Analytical calls recorded once, refusals counted, engine purity unchanged

docs/
├── operations/STATUS.md
├── architecture/STAGES.md
├── product/ROADMAP.md
└── product/FULL_APP_DEVELOPMENT_PLAN.md
```

**Structure Decision**: Keep tracing as a small package-level service (`src/premura/trace.py`) used by the MCP entrypoint. This avoids engine coupling and avoids adding a broad service layer. Storage follows the existing migration path because the canonical trace lives in the local warehouse.

## Phase 0: Research Decisions

See `kitty-specs/session-research-trace-01KSYT4A/research.md`.

Decisions settled:

- Explicit MCP session lifecycle.
- `trace.*` schema in the warehouse, outside `hp.*`.
- Append-only canonical records with generated exports.
- Per-tool normalized hypothesis identity declaration.
- Surfaced marks as explicit session-layer records.
- Audit-consumer contract now; audit skill later.

## Phase 1: Design And Contracts

See:

- `kitty-specs/session-research-trace-01KSYT4A/data-model.md`
- `kitty-specs/session-research-trace-01KSYT4A/contracts/mcp-trace-tools.md`
- `kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`
- `kitty-specs/session-research-trace-01KSYT4A/quickstart.md`

## Post-Design Charter Check

- **Local-first / offline**: Pass. All contracts operate against the local MCP server and DuckDB warehouse.
- **Engine purity**: Pass. The trace contract is explicitly outside `premura.engine`; tests must compare analytical envelopes with tracing on vs off.
- **Scientific honesty**: Pass. Contract language uses `user-facing findings`, `unique hypotheses examined`, and `refusal breakdown`; it forbids `significant` framing.
- **Guide, don't enumerate**: Pass. Future tools add a normalized identity declaration instead of editing the disclosure counting algorithm.
- **Scope control**: Pass. The audit skill, PubMed, new analytical math, and `paired_t_test` remain out of scope.

## Complexity Tracking

No charter violations or unusual complexity exemptions are required.

## Implementation Sequencing Guidance

1. Add failing tests for migration/schema ownership and append-only behavior.
2. Add failing tests for trace session lifecycle, analytical-call recording, normalized identity deduplication, refusal breakdown, surfaced marks, and disclosure export.
3. Implement `005_trace_audit.sql` and `premura.trace` public functions.
4. Wire MCP trace tools and analytical wrapper recording.
5. Update contracts/docs and live reference docs.
6. Run `ruff`, changed-scope `mypy`, and `pytest -q` before review handoff.
