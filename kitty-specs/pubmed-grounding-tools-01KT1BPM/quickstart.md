# Quickstart: PubMed Grounding Tools

## Goal

Validate that Premura can search PubMed for candidate records and fetch exact citeable records by PMID while keeping literature separate from local user-data analysis.

## Reviewer Setup

1. Work from the project root checkout.
2. Read `kitty-specs/pubmed-grounding-tools-01KT1BPM/spec.md`.
3. Read `kitty-specs/pubmed-grounding-tools-01KT1BPM/contracts/pubmed-grounding-contract.md`.
4. Confirm implementation followed the resolved path in `kitty-specs/pubmed-grounding-tools-01KT1BPM/research.md` ("Final Decision"): a minimal native build on NCBI E-utilities behind a Premura-owned adapter exposing exactly `pubmed_search` and `pubmed_fetch` — not a third-party MCP server and not a new PubMed client-library dependency.

## Expected User Flow

1. Agent receives a health question that needs literature context.
2. Agent calls `pubmed_search` with a query such as `sleep restriction hrv`.
3. Tool returns candidate records with PMIDs and `citation_status = candidate_only`.
4. Agent selects a PMID and calls `pubmed_fetch`.
5. Tool returns a fetched record with `citation_status = citeable_fetched_record` and PubMed provenance.
6. Agent cites only the fetched record in the final answer.

## Acceptance Checks

- Search with a valid query returns candidate PMIDs or a structured `no_results` outcome.
- Search candidates are not represented as citeable records.
- Fetch with a valid PMID returns a fetched record with PubMed provenance.
- Fetch with an invalid/unavailable PMID returns a structured unavailable/refusal outcome.
- Missing optional metadata is explicit and not invented.
- Default MCP tool catalog includes the PubMed search/fetch tools.
- Operator surface still includes exactly the default tools plus the existing operator-only raw SQL escape hatch.
- Stage 2 engine code has no runtime PubMed/network dependency.
- PubMed tools do not read or write `hp.*` health warehouse rows.

## Suggested Validation Commands

Use the changed-scope commands chosen by implementation. Expected examples:

```bash
uv run python -m pytest -q tests/test_mcp_pubmed.py tests/test_mcp_server.py -x --tb=short
uv run ruff check src/premura/mcp tests/test_mcp_pubmed.py tests/test_mcp_server.py
uv run mypy src/premura/mcp
```

If the implementation adds a live-network smoke test, keep it out of the default test loop and document the opt-in command separately.

## Out-of-Scope Checks

Fail review if the implementation includes any of these without a follow-up approved spec change:

- Direct default exposure of broad third-party tools such as full-text fetch, deep paper analysis, MeSH lookup, Europe PMC, Unpaywall, or related-article discovery.
- Citation of search-only candidates.
- PubMed calls from `premura.engine`, parsers, or store code.
- Automated mapping from PubMed concepts to Premura canonical metrics.
- Claims that PubMed records diagnose, treat, cause, or compute anything about the user's own health data.
