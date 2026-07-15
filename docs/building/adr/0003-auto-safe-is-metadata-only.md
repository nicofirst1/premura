# Keep `auto_safe` as metadata; ingest never calls the Stage 2 engine

> **Status:** Accepted — 2026-06-02

Premura keeps the authoritative Stage 1 -> Stage 2 boundary from `docs/building/architecture/STAGES.md`: ingest persists only rows reconstructed from source artifacts and does not call the signal engine during `load()`. The `SignalSpec.auto_safe` flag remains as metadata for future explicit recompute flows, but derived lab ratios are materialized only through deliberate Stage 2 execution, because that preserves the repo's rebuild-from-raw contract and avoids silently mixing ingest with post-ingest derivation.
