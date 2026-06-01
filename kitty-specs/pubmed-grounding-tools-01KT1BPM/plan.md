# Implementation Plan: PubMed Grounding Tools

**Branch**: `master` | **Date**: 2026-06-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/pubmed-grounding-tools-01KT1BPM/spec.md`

## Summary

Add user-initiated PubMed grounding to Premura's default MCP surface: search returns candidate PMIDs, fetch-by-PMID returns citeable records, and final answers may cite only fetched records. Planning deliberately starts with an adopt-vs-wrap-vs-build research gate over existing PubMed MCP servers and adjacent integration options; implementation proceeds only after the chosen option is shown to preserve Premura's citation contract and stage boundaries.

The expected engineering shape is a Premura-owned PubMed grounding contract at the MCP boundary. Existing servers may inform or power that contract, but Premura should not expose a third-party server directly unless it already satisfies the product contract without weakening citation safety, local-first posture, or Stage 2 offline guarantees.

## Technical Context

**Language/Version**: Python 3.11+ for Premura code; Phase 0 may evaluate non-Python third-party MCP servers but must not force a new runtime into Premura without an explicit decision.
**Primary Dependencies**: Existing MCP/FastMCP surface; possible PubMed provider behind a Premura-owned adapter contract after Phase 0. No dependency is approved before the adopt-vs-wrap-vs-build decision.
**Storage**: No persistent PubMed storage in this mission. PubMed search/fetch results are returned as tool outputs unless a later plan revision explicitly justifies storage.
**Testing**: Test-first with pytest through public MCP/server-facing surfaces; deterministic fixtures or mocked provider responses for network behavior; no live PubMed dependency in the default test loop.
**Target Platform**: Local-first Premura toolchain on macOS; MCP default surface used by local agents.
**Project Type**: Single Python project with Stage 3 MCP extension.
**Performance Goals**: Default PubMed search returns at most 20 candidate records; ordinary unavailable/no-result cases return structured outcomes. Non-ingest local commands should remain aligned with the charter's under-2-second soft target where live network is not involved.
**Constraints**: Network access belongs only in user-initiated Stage 3 MCP tooling. Stage 2 engine, parsers, and store remain offline at runtime. PubMed records provide literature context, not diagnosis, treatment advice, causal claims, or local-data computation.
**Scale/Scope**: First slice only: search candidates, fetch exact citeable records, candidate-vs-fetched citation rule, default MCP exposure, documentation. Personal-data bridge and concept-to-metric mapping stay deferred.

## Planning Answers

- The first slice includes **search plus fetch**: search discovers candidate PMIDs; fetch-by-PMID makes a record citeable.
- PubMed tools may appear directly on the **default MCP surface** because Premura is not in production yet.
- The personal-data bridge is out of scope.
- Phase 0 must survey existing PubMed MCP servers and related integration options, not only the three seed URLs provided by the maintainer.
- Planning should use an **adopt vs wrap vs build** decision gate before implementation.
- Default recommendation is to prefer a Premura-owned adapter/contract over direct third-party exposure unless an existing server already satisfies Premura's contract.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter Concern | Status | Plan Response |
| --- | --- | --- |
| Agent-first, human-beneficiary product shape | Pass | PubMed grounding serves the agent-facing MCP surface while helping the human understand literature context. |
| Local-first and offline by default | Pass with bounded exception | Existing local pipeline remains offline; PubMed is user-initiated Stage 3 network access only. No background network calls. |
| No overconfident health claims | Pass | Contracts separate literature context from user-data findings and ban diagnosis, treatment advice, and causal claims. |
| Test-first and public-interface testing | Pass | Work packages must begin with externally observable tests for search/fetch responses and MCP tool catalog behavior. |
| Minimal blast radius | Pass | Changes are Stage 3-bounded; Stage 2 engine, parsers, and store are not allowed to gain PubMed runtime dependencies. |
| Design altitude | Pass | Plan defines a provider/adapter decision and citation contract rather than hardcoding one external server as the product model. |

No charter violation is accepted. If implementation discovers that direct adoption of a third-party server requires an online-only, broad, or unreviewable surface, the plan requires wrapping or building instead.

## Project Structure

### Documentation (this feature)

```text
kitty-specs/pubmed-grounding-tools-01KT1BPM/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── pubmed-grounding-contract.md
└── tasks.md              # Created later by /spec-kitty.tasks, not by this command
```

### Source Code (repository root)

```text
src/premura/mcp/
├── entrypoint.py         # Registers default MCP tools
├── server.py             # Stage 3 wrapper helpers
└── pubmed.py             # Candidate home for PubMed grounding adapter/service

tests/
├── test_mcp_server.py    # Default/operator tool catalog assertions
└── test_mcp_pubmed.py    # Candidate/fetched contract and network-failure behavior

docs/
├── operations/STATUS.md
├── product/ROADMAP.md
└── architecture/STAGES.md
```

**Structure Decision**: Keep PubMed grounding in Stage 3 MCP code. If Phase 0 chooses a wrapper around an existing server/client, hide it behind a small Premura-owned adapter contract so `entrypoint.py` and user-facing tool outputs remain stable.

## Phase 0: Research Plan

Research must answer these questions before implementation tasks are generated:

1. Which existing PubMed MCP servers or adjacent PubMed integration libraries are viable candidates?
2. Do any candidates already preserve Premura's search-candidate vs fetched-citation distinction?
3. Can any candidate be used without exposing broad tools such as full-text download, deep paper analysis, or non-PubMed corpora on Premura's default surface?
4. Can the candidate be tested deterministically without live network calls?
5. Does the candidate introduce a new runtime/language dependency that is justified for this first slice?
6. If no candidate fits directly, what is the smallest native PubMed integration that satisfies the spec?

Research output is recorded in [research.md](research.md). The implementation plan currently chooses **wrap or build**, not direct adoption, unless a later Phase 0 finding proves direct adoption satisfies every contract.

## Phase 1: Design Outputs

- [data-model.md](data-model.md): defines PubMed query, candidate record, fetched record, and citation provenance shapes.
- [contracts/pubmed-grounding-contract.md](contracts/pubmed-grounding-contract.md): defines MCP-facing search/fetch behavior, citation eligibility, refusal outcomes, and stage boundaries.
- [quickstart.md](quickstart.md): gives reviewer-facing validation steps and example user flows.

## Post-Design Charter Check

| Charter Concern | Status | Evidence |
| --- | --- | --- |
| Stage boundary remains intact | Pass | Contract places PubMed only in Stage 3 MCP and explicitly forbids Stage 2/runtime engine network access. |
| Citation safety is reviewable | Pass | Data model distinguishes candidate records from fetched records; contract says only fetched records are citeable. |
| No PHI exposure | Pass | PubMed tools do not read `hp.*` rows and require no health warehouse access. |
| Testability | Pass | Quickstart and contracts require deterministic fixtures/mocked provider responses. |
| Scope bounded | Pass | Data bridge, concept-to-metric mapping, full-text/deep-analysis tools, storage, and diagnosis/treatment advice remain out of scope. |

No unresolved planning questions remain.

## Complexity Tracking

No charter violations or complexity exceptions are currently justified.
