# premura — Specification

> Status: authoritative. Source of truth for what the system must do.
>
> Companion to [DOCTRINE.md](DOCTRINE.md) (product stance), [USERJOURNEY.md](../using/USERJOURNEY.md) (experience), and [STATUS.md](STATUS.md) (what works today). This document is the source of truth for **what the system must do**, not how.

## 1. Purpose

Build a single, locally-owned warehouse and tool substrate for the user's personal health data, with encrypted off-site artifacts, holding metrics Android **Health Connect** does not bridge: HRV, respiratory rate, stress, Body Battery, SpO2, body composition, training metrics. Per [DOCTRINE.md](DOCTRINE.md), the primary runtime client is an AI agent acting for the human user; Health Connect is one input among several, not the destination.

## 2. Scope

**In scope (current pre-v1 line):** monthly-cadence ingestion of the supported sources (Garmin Connect GDPR `.zip`, Health Connect `.db`, Sleep as Android CSV, Body Measurement Tracker CSV, local lab files) into a unified long-format star schema in **DuckDB**; deterministic cross-source deduplication; `age`-encryption of exported snapshots and staged raws (recipient key held by the user); opt-in Drive backup via `rclone`; a macOS **launchd** agent that runs on a calendar trigger, notifies when inputs are needed, and waits for a user sentinel; a `premura` CLI; and an agent-facing MCP/tool surface as the default analytical interface, with CLI/SQL as expert fallback.

**Out of scope (v1):** live API pulls from any vendor; writing back into Health Connect; mobile/Android components; multi-user support; real-time/streaming ingestion; per-activity FIT-stream decoding; Apple Health / iOS sources; a graphical dashboard.

## 3. Functional requirements

| ID    | Requirement                                                                                                                                                                                                           |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-1  | Ingest a Health Connect `.db` (`user_version=20` or compatible) into `hp.fact_measurement` / `hp.fact_interval` for every supported metric type.                                                                      |
| FR-2  | Ingest a Garmin GDPR `.zip`: HRV (overnight + snapshot), respiratory rate, stress, Body Battery, SpO2, training load/status/readiness, daily wellness, and summarized activities, each with the correct `value_kind`. |
| FR-3  | Ingest a Sleep as Android CSV into per-minute actigraphy plus session intervals, using the `Tz` column as the authoritative IANA time zone (sleep stays continuous across a DST boundary).                            |
| FR-4  | Ingest a Body Measurement Tracker CSV, converting units per `config.parsers.bmt.*` and assigning unknown columns to `bmt_custom:<slug>` with `unit='unknown'`.                                                        |
| FR-5  | Deduplicate within a source (UNIQUE native/synthesized key) and across sources (priority-ordered match by metric_id + ±2s + ±0.01 value).                                                                             |
| FR-6  | Produce encrypted `health.duckdb.age` and `raw.tar.gz.age` recoverable with the user's `age` private key.                                                                                                             |
| FR-7  | Upload encrypted artifacts to `gdrive:/backups/premura/YYYY/MM/` only on explicit opt-in, verified via `rclone lsl`.                                                                                                  |
| FR-8  | Run unattended-or-notify on macOS via launchd, calendar-triggered monthly, acting only when the user has touched `data/inbox/.ready`.                                                                                 |
| FR-9  | Be idempotent: re-running any ingest with the same input (matched by sha256) is a no-op for rows already written.                                                                                                     |
| FR-10 | Preserve historical rows even when a fresher dump no longer contains them (Garmin's 2-/5-year horizon).                                                                                                               |

## 4. Non-functional requirements

- **Security.** GDPR Article 9 special-category data. Drive artifacts encrypted at rest, cleartext never on Drive. `age` key `0600` + git-excluded. `rclone` remote uses `drive.file` scope. No analytics/telemetry. Upload `manifest.json` carries non-PHI metadata only.
- **Durability.** The DuckDB warehouse is the system of record post-ingestion; stage/raw files gc'd via `premura gc --keep N` (default 3 months). Garmin GDPR exports expire in 3 days, so the encrypted raw tarball is the durable copy. `age` key loss = total backup loss (warn at setup, remind periodically).
- **Observability.** Each ingest writes an `hp.ingest_run` row (timestamps, source_kind/path/sha256, rows inserted/skipped). Structured `structlog` JSON logs. `premura doctor` reports `age`, `rclone`, `uv`, DuckDB presence, key fingerprint, rclone reachability, free disk.
- **Portability.** Warehouse opens on any DuckDB ≥1.1 platform (no platform-specific extensions); artifacts decrypt with stock `age`.
- **Performance (soft).** ~200 MB HC ingest <60 s (M-series); monthly run <10 min for a ~500 MB GDPR zip; warehouse <1 GB after 5 years.

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

The system SHALL expose a programmatic analytical surface for an AI agent acting on the user's behalf. The shipped shape is the MCP surface described in `docs/building/architecture/STAGES.md` and `docs/shared/STATUS.md`.

### Operator interface — CLI surface (`premura`)

```
premura bootstrap                                         # fresh-clone setup readiness
premura ingest [--source all|hc|garmin|saa|bmt|lab] [PATH] # parse and store
premura status                                            # ingest_run + per-metric row counts
premura export --month YYYY-MM                            # snapshot + tarball raws, age-encrypt
premura upload --month YYYY-MM                            # opt-in rclone copy to Drive
premura run-monthly                                       # ingest + encrypt (no upload)
premura doctor                                            # environment + config preflight
premura gc --keep N                                       # drop exports older than N months
premura install-launchd / uninstall-launchd               # manage the launchd agent
premura install-skills                                    # install bundled agent skills
premura profile-fields / profile-record                   # expert profile-capture mirror
```

All commands MUST emit a non-zero exit code on any failure that breaks the contract (failed sha256, failed upload verification, failed encryption round-trip).

## 7. Acceptance criteria

- A full monthly run from a fresh checkout completes the verification ladder with no manual fix-ups beyond the one-time bootstrap.
- A random month's encrypted artifact decrypts to a DuckDB file whose row counts match the local warehouse at that point in time (same for any uploaded copy).
- `premura doctor` reports green on the operator's Mac and on a second clean Mac (no implicit state outside the repo + `~/.config/premura/`).
