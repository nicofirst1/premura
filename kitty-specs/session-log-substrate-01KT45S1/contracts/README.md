# Contracts — Session Log Substrate (Slice One)

These are the **internal interface seams** for the slice. There is no HTTP/REST
surface; the "contracts" are the public function/data boundaries that tests drive
black-box (DIRECTIVE_036), asserting on observable outputs (DuckDB row counts in
the session-log file, the returned verdict, raised exceptions, file bytes).

| Contract | Seam | Consumed by |
| --- | --- | --- |
| `session-log-writer.md` | `premura.session_log.store` — connect/init + writer fns | the harness (sole writer) |
| `runtime-contract-check.md` | `premura.parsers.contract_check.check_runtime_contract` | the grader; the runner (informational) |
| `ingest-outcome-envelope.schema.json` | subprocess stdout JSON | the harness |
| `grader-verdict.schema.json` | `premura.harness.grader.grade` return | the repeatable check, the live trial, tests |
| `live-trial-seam.md` | `premura.harness.live_trial` — Driver/Operator protocols | tests (fake operator); deferred real model |

Determinism: the verdict (`grader-verdict.schema.json`) is byte-stable across
runs (NFR-001); it never embeds ids/timestamps (D5).
