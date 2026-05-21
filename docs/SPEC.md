# premura — Specification

> Status: authoritative. Source of truth for what the system must do.
>
> Companion to [ARCHITECTURE_HISTORY.md](ARCHITECTURE_HISTORY.md) (implementation history), [USERJOURNEY.md](USERJOURNEY.md) (experience), [STATUS.md](STATUS.md) (what works today), and [ROADMAP.md](ROADMAP.md) (what's next).
> This document is the source of truth for **what the system must do**, not how.

## 1. Purpose

Build a single, locally-owned, encrypted-off-site warehouse of the user's personal health data that contains metrics Android **Health Connect** does not bridge: HRV, respiratory rate, stress, Body Battery, SpO2, body composition, training metrics. Health Connect remains one input among several rather than the destination.

## 2. Scope

### In scope (v1)
- Ingestion of **monthly cadence** dumps from four named sources:
  1. **Garmin Connect** — GDPR data export `.zip` (manual request from `account.garmin.com/datamanagement/`)
  2. **Health Connect** — `.db` produced by HC's built-in auto-export to Google Drive
  3. **Sleep as Android** — CSV export
  4. **Body Measurement Tracker** (cookapps) — CSV export
- Parsing each source into a unified long-format star schema in **DuckDB**.
- Deterministic cross-source deduplication.
- Encryption of the warehouse and the staged raw artifacts with **`age`**, using a recipient public key whose private key the user holds.
- Off-site backup to **Google Drive** via **`rclone`**.
- A macOS **launchd** agent that runs on a calendar trigger, emits a notification when fresh inputs are needed, and waits for a user-controlled sentinel before processing.
- A Python CLI (`hpipe`) covering: `ingest`, `status`, `export`, `upload`, `doctor`, `run-monthly`, `gc`, `install-launchd`.

### Out of scope (v1)
- Live API pulls from any vendor (no scraping of Garmin Connect, no Google Fit REST, no Apple HealthKit).
- Any path that writes data back into Health Connect.
- Mobile or Android components of any kind.
- Multi-user / shared-account support.
- Real-time or streaming ingestion.
- Per-activity FIT-file stream decoding (only summarized JSON from the GDPR dump in v1).
- Apple Health / iOS sources.
- A graphical dashboard (the warehouse is the artifact; the user brings their own SQL/Polars/notebook).

## 3. Functional requirements

| ID | Requirement | Verification |
|---|---|---|
| FR-1 | The system SHALL ingest a Health Connect `.db` (`user_version=20` or compatible) and produce rows in `hp.fact_measurement` / `hp.fact_interval` for every supported metric type listed in PLAN §"Per-source parsers". | Ingest a Health Connect export at `~/Downloads/health_connect_export.db`; assert fact and interval row counts are non-zero and match the parser's coverage report. |
| FR-2 | The system SHALL ingest a Garmin GDPR `.zip` and produce rows for HRV (overnight + snapshot), respiratory rate, stress, Body Battery, SpO2, training load, training status, training readiness, daily wellness, and summarized activities. | Ingest a real GDPR zip; assert each metric type appears in `dim_metric` with `value_kind` correctly classified. |
| FR-3 | The system SHALL ingest a Sleep as Android CSV and produce per-minute actigraphy samples plus session intervals, using the CSV's `Tz` column as the authoritative IANA time zone. | Ingest a sample; assert sleep cycles that cross a DST boundary stay continuous. |
| FR-4 | The system SHALL ingest a Body Measurement Tracker CSV, converting units per `config.parsers.bmt.weight_unit` and `config.parsers.bmt.length_unit`, and assigning unknown columns to `metric_id = bmt_custom:<slug>` with `unit='unknown'`. | Ingest a sample with kg and lb settings; assert canonical kg output. |
| FR-5 | The system SHALL deduplicate within a single source (native UUID / synthesized key UNIQUE) and across sources (priority-ordered match by metric_id + ±2s timestamp + ±0.01 value). | Ingest the HC file twice; assert `COUNT(*)` unchanged. Ingest a Garmin GDPR row and an HC-bridged Garmin row of the same metric/value/instant; assert one row with `source_id` = Garmin GDPR. |
| FR-6 | The system SHALL produce an encrypted artifact `health.duckdb.age` (and `raw.tar.gz.age` of the month's staged raws) recoverable with the user's `age` private key. | Round-trip: `age -d` of the encrypted file, byte-diff against the source. |
| FR-7 | The system SHALL upload encrypted artifacts to `gdrive:/backups/premura/YYYY/MM/` and verify via `rclone lsl`. | Run upload; verify listing shows expected files with matching sizes. |
| FR-8 | The system SHALL run unattended-or-notify on macOS via launchd, calendar-triggered monthly, and never act on inputs unless the user has touched `data/inbox/.ready`. | `launchctl kickstart` the agent; verify it notifies and exits without ingesting if `.ready` is absent. |
| FR-9 | The system SHALL be idempotent: re-running any ingest with the same input file (matched by sha256) is a no-op for rows already written. | Two consecutive ingests of the same file; second run's `rows_inserted = 0`, `rows_skipped_dup = N`. |
| FR-10 | The system SHALL preserve historical rows even when a fresher dump no longer contains them (Garmin's 2-/5-year horizon). | Ingest dump A covering 2024-01–2026-04; ingest dump B covering 2024-03–2026-05; assert rows from 2024-01–2024-02 still present and tagged with dump A's `ingest_batch`. |

## 4. Non-functional requirements

### NFR-Security
- Health data is treated as **sensitive personal data under GDPR Article 9** (special category — data concerning health).
- All artifacts uploaded to Drive MUST be encrypted at rest. Cleartext MUST never reach Drive.
- `age` private key MUST be stored with `0600` permissions and excluded from `git`.
- The `rclone` Drive remote MUST use `drive.file` scope (per-app sandbox), not `drive` (full drive).
- No third-party analytics, telemetry, or crash reporting in the pipeline itself.
- A `manifest.json` accompanying each upload MAY contain non-PHI metadata (sha256s, batch_id, age recipient fingerprint, source-file inventory by name + size only).

### NFR-Durability
- The DuckDB warehouse is the **system of record** post-ingestion. Stage/raw files MAY be garbage-collected per `hpipe gc --keep N` (default N=3 months).
- Garmin GDPR exports expire 3 days after generation; once ingested, the encrypted raw tarball on Drive is the only remaining copy of the original dump.
- The `age` private key loss = total backup loss. The system MUST emit a setup-time warning and a periodic reminder.

### NFR-Observability
- Every ingest run MUST write a row to `hp.ingest_run` with `started_at`, `finished_at`, `source_kind`, `source_path`, `source_sha256`, `rows_inserted`, `rows_skipped_dup`.
- Logs MUST be structured (`structlog` JSON lines), written to `~/Library/Logs/premura/{out,err}.log`.
- `hpipe doctor` MUST report status of: `age`, `rclone`, `uv`, DuckDB file presence, age key fingerprint, rclone remote reachability, free disk in `data/`.

### NFR-Portability
- The warehouse file MUST open on any platform with DuckDB ≥1.1 (no platform-specific extensions stored in the file).
- Encrypted artifacts MUST decrypt with stock `age` on any platform.

### NFR-Performance (soft targets, not pass/fail)
- Ingest of a ~200 MB HC export completes in under 60 s on an M-series Mac.
- Monthly run end-to-end (assume Garmin GDPR is the slowest input): under 10 minutes given a ~500 MB GDPR zip.
- Resulting DuckDB file size after 5 years of history: target <1 GB before encryption.

## 5. Data contract

### Canonical units (`dim_metric.canonical_unit`)
| Domain | Unit |
|---|---|
| body mass (weight, lean, water, bone, fat) | kg |
| body fat percentage | % |
| length (height) | m |
| heart rate, resting HR | bpm |
| HRV (rMSSD) | ms |
| respiratory rate | breaths/min |
| oxygen saturation | % |
| temperature | °C |
| blood pressure | mmHg |
| blood glucose | mmol/L |
| distance | m |
| energy | kcal |
| VO₂ max | mL/kg/min |
| stress, Body Battery, training load | dimensionless 0–100 (scale per Garmin) |

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

## 6. Interface — CLI surface (`hpipe`)

```
hpipe ingest [--source all|hc|garmin|saa|bmt] [PATH]   # parse and store
hpipe status                                            # summary of ingest_run + row counts per metric
hpipe export --month YYYY-MM                            # snapshot + tarball staged raws
hpipe upload                                            # age-encrypt + rclone copy to Drive
hpipe run-monthly                                       # full pipeline (launchd entry-point)
hpipe doctor                                            # environment + config preflight
hpipe gc --keep N                                       # drop local exports older than N months
hpipe install-launchd / uninstall-launchd               # manage the launchd agent
```

All commands MUST emit a non-zero exit code on any failure that breaks the contract (failed sha256, failed upload verification, failed encryption round-trip).

## 7. Acceptance criteria

The v1 milestone is met when, simultaneously:

- A full monthly run starting from a fresh checkout completes the verification ladder in PLAN §"Verification" with no manual fix-ups beyond the one-time bootstrap.
- A randomly chosen month's encrypted artifact on Drive decrypts to a DuckDB file whose row counts match the local warehouse at the same point in time.
- `hpipe doctor` reports green on the operator's Mac and on a second clean Mac (proves no implicit state outside the repo + `~/.config/premura/`).
- The wiki hub page (in the operator's personal knowledge wiki, location operator-specific) is committed and passes `/wiki-lint`.

## 8. Assumptions

- The user is the sole operator and sole subject. Multi-user data is out of scope.
- The user keeps `~/.config/premura/age.key` backed up in their password manager. Loss of this key is treated as user error, not a system failure.
- Google Drive remains available and the rclone `gdrive` remote stays authenticated.
- Garmin Connect, Sleep as Android, and Body Measurement Tracker continue to offer user-initiated exports in their current formats. Format drift is mitigated by defensive parsers (pattern-based file discovery, `PRAGMA table_info` checks) but not eliminated.
- macOS launchd is available; Linux/Windows operators would need to substitute `systemd` or Task Scheduler equivalents (out of v1 scope).
- DuckDB ≥ 1.1 stays backwards-compatible enough to read the warehouse file. DuckDB has shipped a forward-compat statement; we accept the risk.

## 9. Glossary

- **GDPR dump** — A complete personal-data export produced under GDPR Article 15 (right of access). Garmin's takes up to 30 days, expires after 3.
- **HC** — Health Connect, Android's central health-data API/database.
- **dim / fact** — Standard star-schema terms. `dim_*` = small, slowly-changing reference tables; `fact_*` = large, growing observation tables.
- **rMSSD** — Root mean square of successive differences between heartbeats; the HRV metric Garmin reports overnight.
- **age** — Modern file encryption tool (`age-encryption.org`), X25519 recipient keys, single binary, no key servers.
- **rclone** — `rsync`-like client for cloud object stores (Drive, S3, etc.) with optional client-side encryption (not used here — we encrypt with `age` first, treat Drive as opaque storage).
- **ULID** — 128-bit time-sortable ID; used for `batch_id` so ingest runs sort by time without an extra column.
