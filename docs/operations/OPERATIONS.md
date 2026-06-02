# premura — Operations

> Status: live reference. Operator commands and day-to-day run surface.
>
> Companion to [../README.md](../../README.md) (setup), [STATUS.md](STATUS.md)
> (current shipped state), and [SPEC.md](../product/SPEC.md) (requirements).

## How to use it today

```bash
# put inputs in data/inbox/ (HC .db, Garmin GDPR .zip, SAA/BMT .csv, lab files), then:
uv run hpipe ingest                      # autodiscovers all supported sources
uv run hpipe status                      # current row counts
uv run hpipe export --month 2026-05      # snapshot + tarball + age-encrypt
uv run hpipe upload --month 2026-05      # opt-in upload step
uv run hpipe doctor                      # preflight checks
uv run hpipe install-launchd             # macOS scheduled run on day 1 @ 10:00
```

## Direct SQL

```bash
duckdb -readonly data/duck/health.duckdb
```

## Notes

- Upload remains opt-in; `run-monthly` does not push automatically.
- Lab ingest is part of the current source surface; install the lab extras before parsing real PDFs.
- `README.md` is the primary bootstrap and installation guide.
- `STATUS.md` is the authoritative snapshot of what is currently verified.
