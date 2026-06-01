# Contract: PubMed Grounding Tools

## Purpose

Define the MCP-facing behavior for PubMed grounding. The contract exists so Premura can evaluate third-party PubMed MCP servers without surrendering its product boundary: search finds candidates, fetch-by-PMID creates citeable records, and PubMed context never computes over the user's warehouse data.

## Tool: `pubmed_search`

Search PubMed for candidate literature records.

### Input

| Field | Required | Meaning |
| --- | --- | --- |
| `query` | Yes | Plain-language or PubMed-compatible search text. |
| `limit` | No | Maximum number of candidates to return; default must be no more than 20. |
| `sort` | No | Optional provider-supported sort preference. |

### Success Output

| Field | Meaning |
| --- | --- |
| `status` | `available` when the search completed. |
| `query` | Echo of the search query used. |
| `candidates` | List of candidate records. |
| `count` | Number of candidates returned. |
| `citation_rule` | Plain statement that candidates are not citeable until fetched by PMID. |

Each candidate record must include `pmid`, `source`, and `citation_status = candidate_only`. Title/snippet fields are optional and must not be fabricated.

### No-Result Output

| Field | Meaning |
| --- | --- |
| `status` | `no_results`. |
| `query` | Search query used. |
| `candidates` | Empty list. |
| `message` | Plain-language explanation. |

## Tool: `pubmed_fetch`

Fetch an exact PubMed record by PMID.

### Input

| Field | Required | Meaning |
| --- | --- | --- |
| `pmid` | Yes | Exact PubMed identifier. |

### Success Output

| Field | Meaning |
| --- | --- |
| `status` | `available`. |
| `record` | Fetched PubMed record. |

The fetched record must include `pmid`, `pubmed_url`, and `citation_status = citeable_fetched_record`. It should include title, authors/author summary, journal/source, publication date, and abstract when available. Missing optional metadata must remain explicit.

### Unavailable Output

| Field | Meaning |
| --- | --- |
| `status` | One of `invalid_pmid`, `unavailable`, or `provider_error`. |
| `pmid` | PMID requested. |
| `message` | Plain-language explanation. |
| `retryable` | Whether retrying may help, if known. |

## Citation Eligibility Rule

Final user-facing answers may cite only `pubmed_fetch` success records with `citation_status = citeable_fetched_record`. `pubmed_search` candidates are discovery hints only, even when they contain titles or snippets.

## Stage Boundary Rules

- PubMed network access may occur only in user-initiated Stage 3 MCP tooling.
- PubMed tooling must not read or write `hp.*` health warehouse rows.
- Stage 2 engine, parsers, and store code must not gain runtime PubMed or network dependencies.
- PubMed outputs may provide literature context or rationale only. They must not produce diagnosis, treatment advice, causal claims, or computed claims about the human's own data.

## Provider Decision (resolved by WP01)

The Phase 0 research gate (`research.md`, "Final Decision") surveyed existing PubMed/biomedical MCP servers and PubMed client libraries and chose a single path: a **minimal native build on NCBI E-utilities behind a Premura-owned adapter** that exposes exactly the two tools above. No surveyed third-party MCP server is adopted or wrapped, and no PubMed client library is added as a runtime dependency for the first slice.

The general rule still governs any future provider work: an existing PubMed MCP server is directly adoptable only if it satisfies this contract without exposing out-of-scope tools on Premura's default surface; a useful-but-broader candidate must be wrapped behind Premura's own `pubmed_search` / `pubmed_fetch` behavior; otherwise build the smallest native provider needed for this contract. For the first slice, that rule resolves to the native E-utilities build.

## Explicitly Out of Scope

- Full-text article retrieval.
- Deep paper analysis.
- Europe PMC / Unpaywall expansion.
- Citation-style formatting beyond source provenance needed for final answers.
- MeSH lookup, related-article search, spell-check, or identifier conversion.
- Personal-data bridge or concept-to-metric mapping.
