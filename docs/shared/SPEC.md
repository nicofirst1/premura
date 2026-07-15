# premura — Specification

> Status: authoritative. Source of truth for what the system must do.
>
> Companion to [DOCTRINE.md](DOCTRINE.md) (product stance), [USERJOURNEY.md](../using/USERJOURNEY.md) (experience), and [STATUS.md](STATUS.md) (what works today). This document is the source of truth for **what the system must do**, not how.

## 1. Purpose

Build a single, locally-owned warehouse and tool substrate for the user's personal health data, with encrypted off-site artifacts, that contains metrics Android **Health Connect** does not bridge: HRV, respiratory rate, stress, Body Battery, SpO2, body composition, training metrics. Per [DOCTRINE.md](DOCTRINE.md), the primary runtime client is an AI agent acting for the human user; Health Connect remains one input among several rather than the destination.

## 2. Scope

**In scope (current pre-v1 line):** monthly-cadence ingestion of the supported sources (Garmin Connect GDPR `.zip`, Health Connect `.db`, Sleep as Android CSV, Body Measurement Tracker CSV, and local lab files); parsing each into a unified long-format star schema in **DuckDB**; deterministic cross-source deduplication; `age`-encryption of exported snapshots and staged raws (recipient key held by the user); opt-in Drive backup via `rclone` (the run stops at local encrypted artifacts unless the user runs upload); a macOS **launchd** agent that runs on a calendar trigger, notifies when inputs are needed, and waits for a user sentinel; a `premura` CLI (setup, ingest, status, export, opt-in upload, doctor, monthly run, gc, launchd install, skill install, bounded profile capture); and an agent-facing MCP/tool surface over the warehouse and engine as the default analytical interface, with CLI/SQL as expert fallback.

**Out of scope (v1):** live API pulls from any vendor; writing data back into Health Connect; mobile/Android components; multi-user or shared-account support; real-time/streaming ingestion; per-activity FIT-stream decoding (only summarized JSON from the GDPR dump); Apple Health / iOS sources; a graphical dashboard (the warehouse is the artifact).

## 3. Functional requirements

| ID    | Requirement                                                                                                                                                                                                                                                              |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-1  | Ingest a Health Connect `.db` (`user_version=20` or compatible) and produce rows in `hp.fact_measurement` / `hp.fact_interval` for every supported metric type.                                                                                                          |
| FR-2  | Ingest a Garmin GDPR `.zip` and produce rows for HRV (overnight + snapshot), respiratory rate, stress, Body Battery, SpO2, training load, training status, training readiness, daily wellness, and summarized activities, each classified with the correct `value_kind`. |
| FR-3  | Ingest a Sleep as Android CSV into per-minute actigraphy samples plus session intervals, using the CSV's `Tz` column as the authoritative IANA time zone (sleep crossing a DST boundary stays continuous).                                                               |
| FR-4  | Ingest a Body Measurement Tracker CSV, converting units per `config.parsers.bmt.weight_unit` / `length_unit` and assigning unknown columns to `metric_id = bmt_custom:<slug>` with `unit='unknown'`.                                                                     |
| FR-5  | Deduplicate within a source (native UUID / synthesized key UNIQUE) and across sources (priority-ordered match by metric_id + ±2s timestamp + ±0.01 value).                                                                                                               |
| FR-6  | Produce an encrypted `health.duckdb.age` (and `raw.tar.gz.age` of the month's staged raws) recoverable with the user's `age` private key.                                                                                                                                |
| FR-7  | Upload encrypted artifacts to `gdrive:/backups/premura/YYYY/MM/` only on explicit opt-in, verified via `rclone lsl`.                                                                                                                                                     |
| FR-8  | Run unattended-or-notify on macOS via launchd, calendar-triggered monthly, acting on inputs only when the user has touched `data/inbox/.ready`.                                                                                                                          |
| FR-9  | Be idempotent: re-running any ingest with the same input file (matched by sha256) is a no-op for rows already written.                                                                                                                                                   |
| FR-10 | Preserve historical rows even when a fresher dump no longer contains them (Garmin's 2-/5-year horizon).                                                                                                                                                                  |

## 4. Non-functional requirements

- **Security.** Health data is **GDPR Article 9** special-category data. All Drive artifacts MUST be encrypted at rest; cleartext MUST never reach Drive. The `age` private key MUST be `0600` and git-excluded. The `rclone` remote MUST use `drive.file` scope, not full `drive`. No third-party analytics/telemetry/crash reporting in the pipeline. An upload `manifest.json` MAY carry only non-PHI metadata (sha256s, batch_id, age recipient fingerprint, file inventory by name + size).
- **Durability.** The DuckDB warehouse is the system of record post-ingestion; stage/raw files MAY be gc'd via `premura gc --keep N` (default 3 months). Garmin GDPR exports expire 3 days after generation, so the encrypted raw tarball becomes the durable copy. Loss of the `age` private key = total backup loss; the system MUST warn at setup and remind periodically.
- **Observability.** Every ingest MUST write an `hp.ingest_run` row (`started_at`, `finished_at`, `source_kind`, `source_path`, `source_sha256`, `rows_inserted`, `rows_skipped_dup`). Logs MUST be structured (`structlog` JSON) to `~/Library/Logs/premura/{out,err}.log`. `premura doctor` MUST report status of `age`, `rclone`, `uv`, DuckDB presence, age key fingerprint, rclone reachability, and free disk.
- **Portability.** The warehouse MUST open on any platform with DuckDB ≥1.1 (no platform-specific extensions stored). Encrypted artifacts MUST decrypt with stock `age`.
- **Performance (soft targets).** ~200 MB HC ingest under 60 s on an M-series Mac; monthly run under 10 min for a ~500 MB GDPR zip; warehouse under 1 GB after 5 years (before encryption).

## 5. Data contract

### Canonical units (`dim_metric.canonical_unit`)

| Domain                                     | Unit                                   |
| ------------------------------------------ | -------------------------------------- |
| body mass (weight, lean, water, bone, fat) | kg                                     |
| body fat percentage                        | %                                      |
| length (height)                            | m                                      |
| heart rate, resting HR                     | bpm                                    |
| HRV (rMSSD)                                | ms                                     |
| respiratory rate                           | breaths/min                            |
| oxygen saturation                          | %                                      |
| temperature                                | °C                                     |
| blood pressure                             | mmHg                                   |
| blood glucose                              | mmol/L                                 |
| distance                                   | m                                      |
| energy                                     | kcal                                   |
| VO₂ max                                    | mL/kg/min                              |
| stress, Body Battery, training load        | dimensionless 0–100 (scale per Garmin) |

### Timestamps

- `ts_utc`, `start_utc`, `end_utc` MUST be `TIMESTAMP` (UTC, no offset stored).
- `local_tz` MUST be IANA when known (Sleep as Android's `Tz` column is authoritative); otherwise an offset string `±HH:MM` derived from the source's offset metadata.
- HC `time` is ms-epoch; HC `zone_offset` is **seconds**. Do not double-multiply.

### Identity

- HC `uuid` BLOB is hex-encoded (32 chars lowercase) for `source_uuid`.
- Garmin GDPR rows synthesize `source_uuid = "garmin:<record_type>:<summaryId|calendarDate>"`.
- Sleep as Android uses `"saa:<Id>"`.
- BMT synthesizes `"bmt:<sha1(date+time+metric+value)>"`.
- `dedupe_key = "<source_kind>:<source_uuid>"` and is `UNIQUE` on fact tables.

### Cross-source priority (highest first)

1. `garmin_gdpr` — authoritative for any Garmin-recorded metric
2. `health_connect` rows where the writer is `com.garmin.android.apps.connectmobile`
3. `health_connect` rows from other apps
4. `sleep_as_android`
5. `bmt`

## 6. Interfaces

### Primary analytical interface — agent-facing tool surface

The system SHALL expose a programmatic analytical surface suitable for an AI agent acting on the human user's behalf. In the current shipped shape this is the MCP surface described in `docs/building/architecture/STAGES.md` and `docs/shared/STATUS.md`.

### Operator interface — CLI surface (`premura`)

```
premura bootstrap                                         # fresh-clone setup readiness; on a fresh clone use `uv run premura bootstrap`
premura ingest [--source all|hc|garmin|saa|bmt|lab] [PATH] # parse and store
premura status                                            # summary of ingest_run + row counts per metric
premura export --month YYYY-MM                            # snapshot + tarball staged raws, age-encrypt
premura upload --month YYYY-MM                            # opt-in rclone copy to Drive
premura run-monthly                                       # ingest + encrypt pipeline (no upload step)
premura doctor                                            # environment + config preflight
premura gc --keep N                                       # drop local exports older than N months
premura install-launchd / uninstall-launchd               # manage the launchd agent
premura install-skills                                    # install bundled agent skills
premura profile-fields / profile-record                   # expert mirror of bounded profile capture
```

All commands MUST emit a non-zero exit code on any failure that breaks the contract (failed sha256, failed upload verification, failed encryption round-trip).

## 7. Acceptance criteria

- A full monthly run from a fresh checkout completes the verification ladder with no manual fix-ups beyond the one-time bootstrap.
- A random month's encrypted artifact decrypts to a DuckDB file whose row counts match the local warehouse at the same point in time (same check applies to any uploaded copy).
- `premura doctor` reports green on the operator's Mac and on a second clean Mac (proves no implicit state outside the repo + `~/.config/premura/`).
