# PubMed Grounding Tools Specification

## Feature Overview

Premura should let an agent ground health explanations in PubMed records through the default MCP surface, without letting literature replace deterministic analysis over the user's own warehouse data.

This mission adds the first PubMed grounding slice: user-initiated PubMed search returns candidate records, exact PMID fetch returns citeable records, and final answers may cite only records that were fetched by PMID. It deliberately stops before the personal-data bridge: no automated concept-to-metric mapping, no literature-driven local analysis, and no Stage 2 or engine network dependency.

## Mission Metadata

| Field | Value |
| --- | --- |
| Friendly title | PubMed Grounding Tools |
| Mission type | software-dev |
| Initial description | Tool-Grounded PubMed Grounding (let's be sure our concepts are aligned) |
| Planning/base branch | master |
| Merge target branch | master |

## Intent Summary

The human wants the next analytical-depth mission to add PubMed grounding directly to the default agent MCP surface. The agent should be able to search PubMed for candidate papers and fetch exact PubMed records by PMID. The citation rule is strict: search results are discovery candidates, while fetched records are the only records a final user-facing answer may cite.

The mission excludes the data bridge that maps literature concepts to Premura metrics. PubMed can provide citation context and rationale, but deterministic Premura tools remain the source for any claim about the user's own data.

## Actors

| Actor | Goal |
| --- | --- |
| Human beneficiary | Ask a health question and receive an answer that distinguishes personal data findings from literature context. |
| Agent operator | Search for relevant PubMed records, fetch exact records, and cite only verified fetched records. |
| Reviewer | Verify that PubMed grounding stays in Stage 3 and does not weaken Premura's local-first analytical boundaries. |

## User Scenarios & Testing

### Scenario 1: Search for Candidate Literature

Given the human asks a question that needs literature context, when the agent searches PubMed with a plain-language query, then Premura returns candidate records with enough information for the agent to choose which PMIDs to inspect further.

Acceptance criteria:
- Search returns candidate PMIDs and human-readable titles or summaries when PubMed has matches.
- Search results are clearly marked as candidates, not citeable final sources.
- A no-results search returns a structured no-results outcome rather than an ambiguous failure.

### Scenario 2: Fetch an Exact Citeable Record

Given the agent has a PMID from search or another user-approved source, when it fetches that PMID, then Premura returns a stable citation record that can be cited in a final answer.

Acceptance criteria:
- Fetch-by-PMID returns PMID, title, authors or author summary, journal/source, publication date when available, abstract text when available, and a source URL or PubMed reference.
- Missing optional fields are represented explicitly instead of fabricated.
- Invalid or unavailable PMIDs produce a structured refusal or unavailable outcome with a clear message.

### Scenario 3: Cite Only Fetched Records

Given an agent has run both search and fetch, when it prepares a final user-facing answer, then only fetched records are eligible as citations.

Acceptance criteria:
- The tool outputs distinguish candidate search results from fetched citation records.
- The mission documentation states that final answers must not cite search-only records.
- Tests or contract examples cover the candidate-vs-fetched distinction.

### Scenario 4: Keep Literature Separate From Local Analysis

Given the agent wants to answer a personal-data question, when PubMed context is used, then PubMed records provide background or rationale only and do not compute, alter, or authorize claims about the user's own warehouse data.

Acceptance criteria:
- PubMed tooling does not read or write health warehouse rows.
- Stage 2 and engine code remain free of runtime network calls.
- User-data claims still come from existing Premura signal or analytical tools.

## Functional Requirements

| ID | Requirement | Status | Acceptance Criteria |
| --- | --- | --- | --- |
| FR-001 | Premura shall provide a user-initiated PubMed search capability on the default agent MCP surface. | Proposed | An agent can submit a query and receive zero or more candidate PubMed records with PMIDs. |
| FR-002 | PubMed search results shall be labeled as discovery candidates and not as final citations. | Proposed | The response shape includes a candidate status or equivalent wording that prevents search-only records from being treated as citeable. |
| FR-003 | Premura shall provide a PubMed fetch capability that retrieves an exact record by PMID. | Proposed | Given a valid PMID, the agent receives a citation record suitable for final-answer citation. |
| FR-004 | Fetched PubMed records shall preserve citation-critical metadata when available. | Proposed | The record includes PMID, title, publication source, publication date, author information, abstract when available, and a PubMed reference or URL. |
| FR-005 | PubMed fetch shall represent missing optional metadata explicitly. | Proposed | A record with no abstract or partial author/source data returns null, empty, or unavailable fields with no invented text. |
| FR-006 | Invalid, missing, or unavailable PMID requests shall return a structured unavailable/refusal outcome. | Proposed | The agent receives a machine-branchable outcome and plain-language message without an uncaught exception for ordinary lookup failures. |
| FR-007 | Final-answer citation guidance shall require that citeable PubMed references come from fetch-by-PMID records, not search-only candidates. | Proposed | The spec, contracts, or tool descriptions state the rule, and validation examples exercise it. |
| FR-008 | PubMed grounding shall remain separate from local user-data analysis. | Proposed | PubMed tool outputs provide literature context only and do not contain computed claims about the user's warehouse data. |
| FR-009 | The default MCP tool catalog shall expose the PubMed search and fetch tools alongside the existing agent-safe tools. | Proposed | Listing the default surface includes the new PubMed tools, while existing signal, analytical, profile-capture, and trace tools remain available. |
| FR-010 | The mission shall document the personal-data bridge as explicitly out of scope. | Proposed | The shipped docs state that automated concept-to-metric mapping and literature-to-warehouse bridging are deferred. |

## Non-Functional Requirements

| ID | Requirement | Status | Measurement |
| --- | --- | --- | --- |
| NFR-001 | PubMed lookup failures shall be represented as structured outcomes for ordinary user-facing failures. | Proposed | 100% of covered no-results, invalid-PMID, and unavailable-record tests return a structured outcome rather than an uncaught exception. |
| NFR-002 | PubMed search responses shall be bounded for agent use. | Proposed | A single search response returns no more than 20 candidate records by default unless an explicit, reviewed limit changes that threshold. |
| NFR-003 | PubMed records shall preserve source provenance. | Proposed | 100% of fetched-record success responses include the PMID and a PubMed reference or URL. |
| NFR-004 | Stage 2 and engine runtime shall remain offline. | Proposed | Static or test validation confirms zero runtime PubMed/network dependencies under `premura.engine`. |
| NFR-005 | Citation safety shall be contract-tested. | Proposed | At least one acceptance test or fixture verifies that search-only candidates are not represented as citeable fetched records. |
| NFR-006 | The default MCP surface shall stay reviewable as a closed explicit catalog. | Proposed | Tool-catalog tests assert the complete expected default and operator tool counts after the new tools are added. |

## Constraints

| ID | Constraint | Status | Verification |
| --- | --- | --- | --- |
| C-001 | PubMed network access belongs only in Stage 3 MCP tooling for user-initiated calls. | Proposed | Review confirms no Stage 2 engine or parser code performs runtime PubMed calls. |
| C-002 | PubMed records shall not be used as a source of diagnosis, treatment advice, or causal claims. | Proposed | Tool descriptions, docs, and examples preserve literature-as-context language. |
| C-003 | The mission shall not add automated concept-to-metric mapping. | Proposed | No requirement or acceptance path maps PubMed concepts to Premura canonical metrics. |
| C-004 | The mission shall not add a personal-data bridge from literature to warehouse queries. | Proposed | No tool takes PubMed concepts and automatically selects local metrics or analytical tools. |
| C-005 | PubMed tooling shall not read or write `hp.*` health warehouse rows. | Proposed | PubMed tools can operate without opening the health warehouse for row access. |
| C-006 | Search results shall not be citeable final records until fetched by PMID. | Proposed | Response shapes and examples make the candidate/fetched distinction explicit. |

## Success Criteria

| ID | Criterion | Measurement |
| --- | --- | --- |
| SC-001 | An agent can discover candidate PubMed records for a health-context query. | In a representative test, a search query returns candidate PMIDs or a structured no-results outcome within the bounded response shape. |
| SC-002 | An agent can fetch an exact citation record by PMID. | In a representative test, fetch-by-PMID returns citation metadata and provenance for at least one known PMID fixture or mocked PubMed response. |
| SC-003 | Final-answer citation eligibility is unambiguous. | 100% of contract examples distinguish search candidates from fetched citeable records. |
| SC-004 | User-data analysis boundaries remain intact. | Review and tests show no PubMed runtime dependency inside Stage 2 engine code and no PubMed tool reads local health facts. |
| SC-005 | The default MCP surface reflects the new capability. | Tool-catalog validation shows the PubMed search and fetch tools are present on the default surface. |

## Key Entities

| Entity | Description |
| --- | --- |
| PubMed Search Query | User- or agent-supplied plain-language search text used to find candidate records. |
| PubMed Candidate Record | A search result containing at least a PMID and basic descriptive metadata; not citeable until fetched. |
| PubMed Fetched Record | An exact PMID lookup result with provenance and citation metadata eligible for final-answer citation. |
| Citation Provenance | The fields that let an answer trace a literature claim back to a fetched PubMed record. |

## Assumptions

- The mission uses the default `software-dev` Spec Kitty mission type because it adds runtime tool behavior.
- PubMed grounding is useful enough to expose on the default MCP surface during the current non-production phase.
- Search plus fetch is the desired first slice: search discovers candidate PMIDs; fetch-by-PMID makes a record citeable.
- The personal-data bridge remains a future mission after the citation contract proves itself.
- Literature may provide background or rationale, but claims about the human's own data continue to come from Premura's deterministic local tools.

## Out of Scope

- Personal-data bridge from literature concepts to warehouse signals.
- Automated concept-to-metric mapping.
- Literature-driven computation over the user's data.
- Diagnosis, treatment recommendations, clinical decision support, or causal claims.
- Runtime PubMed or network access from Stage 2 engine, parsers, or store code.
- Persistent storage of PubMed search history or fetched records unless a later planning step explicitly justifies it.

## Dependencies

- Existing Stage 3 MCP default surface and tool-catalog tests.
- Existing Stage 2/engine rule that runtime analysis stays deterministic and offline.
- PubMed availability for live use, with tests expected to avoid relying on live network behavior for deterministic validation.

## Requirement Quality Notes

- Functional, non-functional, and constraint requirements are separated.
- Each requirement has a stable ID and non-empty status.
- Non-functional requirements include measurable thresholds or complete coverage statements.
- No unresolved clarification markers remain.
