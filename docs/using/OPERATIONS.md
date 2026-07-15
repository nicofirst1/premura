# premura — Operations

> Status: live reference. Operator commands and day-to-day run surface.
>
> Companion to [../README.md](../../README.md) (setup), [STATUS.md](../shared/STATUS.md)
> (current shipped state), and [SPEC.md](../shared/SPEC.md) (requirements).

## How to use it today

```bash
# put inputs in data/inbox/ (HC .db, Garmin GDPR .zip, SAA/BMT .csv, lab files), then:
uv run premura ingest                      # autodiscovers all supported sources
uv run premura status                      # current row counts
uv run premura export --month 2026-05      # snapshot + tarball + age-encrypt
uv run premura upload --month 2026-05      # opt-in upload step
uv run premura doctor                      # preflight checks
uv run premura install-launchd             # macOS scheduled run on day 1 @ 10:00
```

## Full `premura` command reference

```
premura bootstrap                     # setup readiness (on a fresh clone use `uv run premura bootstrap`; setup only — no ingest/upload)
premura ingest [--source all|hc|garmin|saa|bmt|lab|mfp] [PATH]
premura status
premura export --month YYYY-MM        # snapshot + tarball staged raws, age-encrypt
premura upload --month YYYY-MM        # OPT-IN rclone push (not run automatically)
premura doctor
premura gc --keep N
premura run-monthly                   # full ingest+encrypt pipeline (no upload step)
premura install-launchd / uninstall-launchd
```

Experimental: `premura ingest --source lab PATH` uses local docling extraction for real PDFs. Install the base extractor stack with `uv sync --extra lab` or `pip install premura[lab]`. The Apple-Silicon stool-report VLM path is separate: `uv sync --extra lab-vlm` or `pip install premura[lab-vlm]`. Plain-text lab fixtures are still accepted for parser testing.

## MCP surfaces

### Default agent-facing surface (`premura-mcp`)

Primary analytical path for agents. Fully validity-gated — all tools delegate to the Stage 2 signal engine; no raw `hp.*` SQL on this surface.

```bash
uv run premura-mcp
uv run premura-mcp --warehouse-path /absolute/path/to/health.duckdb
```

By default it resolves the warehouse from `PREMURA_DATA_DIR/duck/health.duckdb`.

Tools exposed:

- `list_metrics` — validity-gated catalog entries (engine-delegated, structured envelopes)
- `metric_summary` — validity summary for one metric (engine-delegated)
- `resting_hr_status` — current resting HR with freshness verdict
- `resting_hr_trend` — resting-HR trend with gap visibility
- `steps_trend` — daily-steps trend (never imputes missing days)
- `weight_trend` — body-weight trend with carry-forward caveats
- `sleep_deep_pct_baseline` — latest deep-sleep % vs user's own baseline
- `hrv_change_around_date` — overnight HRV before/after a user-named date
- `profile_context_supported_fields` / `profile_context_record` — bounded agent-mediated profile capture
- `change_point`, `smoothed_average`, `correlate`, `rolling_mean`, `paired_t_test`, `condition_paired_t_test` — the completed bounded set of deterministic analytical tools (`paired_t_test` reports a before/after paired difference with a descriptive uncertainty band — not a significance test, no p-value, names no cause)
- `research_trace_open`, `research_trace_mark_surfaced`, `research_trace_disclosure` — session research trace and disclosure
- `pubmed_search`, `pubmed_fetch` — literature grounding; search hits are discovery candidates only, and final answers may cite only fetched PMID records

Signal-backed and analytical tools return structured `available` / `missing_input` / `stale_input` / `insufficient_data` or first-class refusal payloads rather than free-form claims.

### Operator fallback surface (`premura-mcp-operator`)

Lower-guarantee expert mode. Adds `query_warehouse` (raw SQL escape hatch) on top of the default tools. No Stage 2 validity guarantees apply to `query_warehouse` results — callers own all result interpretation. **Agent use requires explicit user approval**, enforced two ways: `query_warehouse` is absent from the default surface, and this entrypoint refuses to start unless you acknowledge lower-guarantee mode with `--ack` (or `PREMURA_OPERATOR_ACK=1`).

```bash
uv run premura-mcp-operator --ack
uv run premura-mcp-operator --ack --warehouse-path /absolute/path/to/health.duckdb
```

`query_warehouse` returns up to 200 rows by default and accepts `max_rows` up to 1000. How an agent should operate these surfaces honestly on a human's behalf is the subject of [RUNTIME_AGENT.md](../operating/RUNTIME_AGENT.md).

## Direct SQL

```bash
duckdb -readonly data/duck/health.duckdb
```

Direct DuckDB and notebook work remain available as additional expert interfaces.

## Notes

- Upload remains opt-in; `run-monthly` does not push automatically.
- Lab ingest is part of the current source surface; install the lab extras before parsing real PDFs.
- `README.md` is the primary bootstrap and installation guide.
- `STATUS.md` is the authoritative snapshot of what is currently verified.
