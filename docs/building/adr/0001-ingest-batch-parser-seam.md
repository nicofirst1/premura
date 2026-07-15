# Adopt IngestBatch as the parser-to-loader seam

> **Status:** Accepted — 2026-06-02

Premura will replace `ParseResult` and `PluginParseResult` as the long-term parser seam with a single `IngestBatch` module used by both first-party parsers and plugin parsers. An `IngestBatch` is atomic at the warehouse seam: it carries loadable rows, source descriptors, declared metrics, and review metadata such as `unmapped_metrics`; the plugin validates it before returning, the loader validates it again, and the whole batch fails if any row violates the contract. Dedupe stays at the warehouse seam in a separate `Dedupe planner` module that returns a dedupe plan, and the loader becomes a thin orchestrator that applies one validated `IngestBatch` in one transaction.
