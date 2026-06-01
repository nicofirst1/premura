# Data Model: PubMed Grounding Tools

## Overview

This mission does not add persistent warehouse tables. The data model describes transient MCP tool inputs and outputs for PubMed grounding. The central distinction is between a **candidate** found by search and a **fetched record** retrieved by exact PMID. Only fetched records are eligible for final-answer citation.

## Entity: PubMedSearchQuery

Represents a user-initiated literature search request.

| Field | Meaning | Validation |
| --- | --- | --- |
| `query` | Plain-language or PubMed-compatible search text supplied by the agent on behalf of the human. | Required, non-empty after trimming. |
| `limit` | Maximum number of candidate records requested. | Optional; default no more than 20; implementation may enforce a maximum. |
| `sort` | Optional sort preference if the chosen provider supports it. | Optional; unsupported values must produce a structured refusal or use a documented default. |

## Entity: PubMedCandidateRecord

Represents a search result. It is useful for discovery but not citeable as final evidence.

| Field | Meaning | Validation |
| --- | --- | --- |
| `pmid` | PubMed identifier returned by search. | Required; string of identifier characters accepted by PubMed. |
| `title` | Candidate title if available from search/summary. | Optional; never fabricated. |
| `snippet` | Short descriptive text or summary if available. | Optional; never fabricated. |
| `source` | Source label for the candidate result, such as PubMed. | Required. |
| `citation_status` | Whether this record may be cited. | Must be `candidate_only` for search results. |

## Entity: PubMedFetchRequest

Represents exact lookup by PMID.

| Field | Meaning | Validation |
| --- | --- | --- |
| `pmid` | Exact PubMed identifier to fetch. | Required, non-empty. Ordinary invalid/unavailable IDs return structured unavailable/refusal outcomes. |

## Entity: PubMedFetchedRecord

Represents a fetched PubMed record eligible for final-answer citation.

| Field | Meaning | Validation |
| --- | --- | --- |
| `pmid` | Exact PubMed identifier fetched. | Required. |
| `title` | Article title. | Required when provider returns it; missing title must be explicit. |
| `authors` | Author list or concise author summary. | Optional; preserve missingness explicitly. |
| `journal` | Journal or publication source. | Optional; preserve missingness explicitly. |
| `publication_date` | Publication date or best available year/date. | Optional; preserve missingness explicitly. |
| `abstract` | Abstract text when available. | Optional; never fabricated. |
| `pubmed_url` | Source URL/reference for the fetched record. | Required for fetched success. |
| `citation_status` | Whether this record may be cited. | Must be `citeable_fetched_record` for fetched success. |

## Entity: PubMedUnavailableOutcome

Represents ordinary lookup failure without crashing the agent workflow.

| Field | Meaning | Validation |
| --- | --- | --- |
| `status` | Machine-branchable outcome. | One of a small reviewed set such as `no_results`, `invalid_pmid`, `unavailable`, or `provider_error`. |
| `message` | Plain-language explanation for the agent/human. | Required. |
| `query` or `pmid` | The input that could not be satisfied. | Required when applicable. |
| `retryable` | Whether retrying may help. | Boolean if available. |

## Entity: CitationProvenance

Represents the minimum trace needed for an answer to cite literature honestly.

| Field | Meaning | Validation |
| --- | --- | --- |
| `pmid` | PubMed identifier. | Required. |
| `pubmed_url` | Stable PubMed reference. | Required. |
| `fetched_at` | Time the record was fetched, if exposed. | Optional; if present, generated at the MCP boundary, not Stage 2. |
| `provider` | Provider used to fetch the record. The first slice uses a single native NCBI E-utilities provider behind a Premura-owned adapter, so this is a stable label (e.g. `ncbi-eutils`); the field stays present so additional providers can be distinguished later without a schema change. | Required. |

## State Rules

- Search produces `PubMedCandidateRecord` values with `citation_status = candidate_only`.
- Fetch produces `PubMedFetchedRecord` values with `citation_status = citeable_fetched_record`.
- A candidate does not become citeable by being present in search output; it must be fetched by PMID.
- PubMed outputs do not become Stage 2 signals and do not read `hp.*` health rows.
- Missing PubMed metadata remains missing; the system must not invent abstracts, authors, dates, or source details.

## Deferred Entities

These are intentionally not modeled in this mission:

- Literature-to-metric concept mapping.
- Personal-data bridge records.
- Persistent PubMed cache or search history.
- Full-text article body model.
- Deep paper analysis output.
