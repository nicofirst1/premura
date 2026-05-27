# Premura

Local-first, agent-operable health reasoning substrate. A human supplies health-data exports, questions, and approvals; agents ingest, normalize, analyze, compare, and explain through deterministic tools over a single DuckDB warehouse. The system captures the metrics Health Connect does not bridge (HRV rMSSD overnight, stress, body battery, training load/readiness, VO₂ max, etc.) while keeping encrypted export and backup artifacts under the human user's control.

> Docs live in [`docs/`](docs/): [Guide](docs/README.md) · [Doctrine](docs/product/DOCTRINE.md) · [SPEC](docs/product/SPEC.md) · [STATUS](docs/operations/STATUS.md) · [Stages](docs/architecture/STAGES.md) · [Roadmap](docs/product/ROADMAP.md) · [Full Plan](docs/product/FULL_APP_DEVELOPMENT_PLAN.md)
> Contributor guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Quick start

```bash
bash ops/bootstrap.sh                       # one-time: brew installs, age keypair, optional rclone
uv run hpipe doctor                         # verify environment
# drop inputs into data/inbox/, then:
uv run hpipe run-monthly                    # ingest + encrypt (no auto-upload)
uv run hpipe upload --month YYYY-MM         # OPT-IN — push to Drive only when you say so
```

## age key storage

The `age` private key at `~/.config/premura/age.key` is the single secret. Lose it = lose all encrypted backups. Two recommended options:

1. **Local backed-up file** (Time Machine, external drive). Default.
2. **Bitwarden secure note** — `bootstrap.sh` prints a `bw create item …` recipe you can run after `bw login`. Retrieve later with `bw get notes 'premura age key' > ~/.config/premura/age.key && chmod 600 …`.

## What's in the warehouse

`hp.fact_measurement` (point-in-time) and `hp.fact_interval` (bounded events), joined to `hp.dim_metric` + `hp.dim_source`. See [STATUS.md](docs/operations/STATUS.md) for live row counts and [SPEC.md §5](docs/product/SPEC.md) for the data contract.

Query directly:

```bash
duckdb -readonly data/duck/health.duckdb
```

## CLI surface

```
hpipe ingest [--source all|hc|garmin|saa|bmt|lab] [PATH]
hpipe status
hpipe export --month YYYY-MM        # snapshot + tarball staged raws, age-encrypt
hpipe upload --month YYYY-MM        # OPT-IN rclone push (not run automatically)
hpipe doctor
hpipe gc --keep N
hpipe run-monthly                   # full ingest+encrypt pipeline (no upload step)
hpipe install-launchd / uninstall-launchd
```

Experimental: `hpipe ingest --source lab PATH` uses local docling extraction for real PDFs. Install the base extractor stack with `uv sync --extra lab` or `pip install premura[lab]`. The Apple-Silicon stool-report VLM path is separate: `uv sync --extra lab-vlm` or `pip install premura[lab-vlm]`. Plain-text lab fixtures are still accepted for parser testing.

## MCP surface

### Default agent-facing surface (`premura-mcp`)

Primary analytical path for agents. Fully validity-gated — all tools delegate to the Stage 2 signal engine; no raw `hp.*` SQL on this surface.

```bash
uv run premura-mcp
uv run premura-mcp --warehouse-path /absolute/path/to/health.duckdb
```

By default it resolves the warehouse from `HPIPE_DATA_DIR/duck/health.duckdb`.

Tools exposed:

- `list_metrics` — validity-gated catalog entries (engine-delegated, structured envelopes)
- `metric_summary` — validity summary for one metric (engine-delegated)
- `resting_hr_status` — current resting HR with freshness verdict
- `resting_hr_trend` — resting-HR trend with gap visibility
- `steps_trend` — daily-steps trend (never imputes missing days)
- `weight_trend` — body-weight trend with carry-forward caveats
- `sleep_deep_pct_baseline` — latest deep-sleep % vs user's own baseline
- `hrv_change_around_date` — overnight HRV before/after a user-named date

The six signal-backed tools return structured `available` / `missing_input` / `stale_input` / `insufficient_data` payloads.

### Operator fallback surface (`premura-mcp-operator`)

Lower-guarantee expert mode. Adds `query_warehouse` (raw SQL escape hatch) on top of all eight default tools. No Stage 2 validity guarantees apply to `query_warehouse` results — callers own all result interpretation. **Agent use requires explicit user approval**, enforced two ways: `query_warehouse` is absent from the default surface, and this entrypoint refuses to start unless you acknowledge lower-guarantee mode with `--ack` (or `PREMURA_OPERATOR_ACK=1`).

```bash
uv run premura-mcp-operator --ack
uv run premura-mcp-operator --ack --warehouse-path /absolute/path/to/health.duckdb
```

`query_warehouse` returns up to 200 rows by default and accepts `max_rows` up to 1000. Direct DuckDB and notebook work remain available as additional expert interfaces.

Tests: `uv run python -m pytest -q`. See [STATUS.md](docs/operations/STATUS.md) for the current shipped pass count and coverage summary.
