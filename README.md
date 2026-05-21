# premura

Personal health-data warehouse. Ingests monthly dumps from **Health Connect, Garmin GDPR, Sleep as Android, Body Measurement Tracker** into a single encrypted DuckDB. Captures the metrics Health Connect doesn't bridge (HRV rMSSD overnight, stress, body battery, training load/readiness, VO₂ max, etc.).

> Docs live in [`docs/`](docs/): [SPEC](docs/SPEC.md) · [PLAN](docs/PLAN.md) · [USERJOURNEY](docs/USERJOURNEY.md) · [STATUS](docs/STATUS.md) · [ROADMAP](docs/ROADMAP.md)

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

`hp.fact_measurement` (point-in-time) and `hp.fact_interval` (bounded events), joined to `hp.dim_metric` + `hp.dim_source`. See [STATUS.md](docs/STATUS.md) for live row counts and [SPEC.md §5](docs/SPEC.md) for the data contract.

Query directly:

```bash
duckdb -readonly data/duck/health.duckdb
```

## CLI surface

```
hpipe ingest [--source all|hc|garmin|saa|bmt] [PATH]
hpipe status
hpipe export --month YYYY-MM        # snapshot + tarball staged raws, age-encrypt
hpipe upload --month YYYY-MM        # OPT-IN rclone push (not run automatically)
hpipe doctor
hpipe gc --keep N
hpipe run-monthly                   # full ingest+encrypt pipeline (no upload step)
hpipe install-launchd / uninstall-launchd
```

Tests: `uv run python -m pytest -q` (17 passing).
