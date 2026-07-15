# premura — Specification

> Status: authoritative. Source of truth for what the system must do.
>
> Companion to [DOCTRINE.md](DOCTRINE.md) (product stance) and [USERJOURNEY.md](../using/USERJOURNEY.md) (experience). This document is the source of truth for **what the system must do**, not how.

## 1. Purpose

Build a single, locally-owned warehouse and tool substrate for the user's personal health data, with encrypted off-site artifacts, holding metrics Android **Health Connect** does not bridge: HRV, respiratory rate, stress, Body Battery, SpO2, body composition, training metrics. Per [DOCTRINE.md](DOCTRINE.md), the primary runtime client is an AI agent acting for the human user; Health Connect is one input among several, not the destination.

## 2. Scope

**In scope:** monthly-cadence ingestion of whatever the registered parsers support into a unified long-format star schema in **DuckDB**; deterministic cross-source deduplication; `age`-encryption of exported snapshots and staged raws (recipient key held by the user); opt-in Drive backup via `rclone`; a macOS **launchd** agent that runs on a calendar trigger, notifies when inputs are needed, and waits for a user sentinel; a `premura` CLI; and an agent-facing MCP/tool surface as the default analytical interface, with CLI/SQL as expert fallback.

**Out of scope:** live API pulls from any vendor; writing back into Health Connect; mobile/Android components; multi-user support; real-time/streaming ingestion; per-activity FIT-stream decoding; Apple Health / iOS sources; a graphical dashboard.

## 3. Ingest invariants

Per-source parsing behavior is the parser [CONTRACT](../../src/premura/parsers/CONTRACT.md)'s job, not this spec's. The durable, source-independent invariants are:

- **Idempotent.** Re-running any ingest with the same input (matched by sha256) is a no-op for rows already written.
- **Historical rows are preserved** even when a fresher dump no longer contains them (e.g. Garmin's 2-/5-year horizon).

## 4. Non-functional requirements

- **Security.** GDPR Article 9 special-category data. Off-machine artifacts are `age`-encrypted at rest; cleartext never leaves the machine. No analytics or telemetry.
- **Durability.** The DuckDB warehouse is the system of record post-ingestion. The `age` key is the single secret; its loss is total backup loss (warned at setup). Source exports are transient (Garmin GDPR links expire in days), so the encrypted raw tarball is the durable copy.
- **Portability.** The warehouse opens on any DuckDB ≥1.1 platform with no platform-specific extensions; artifacts decrypt with stock `age`.

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

The system SHALL expose a programmatic analytical surface for an AI agent acting on the user's behalf. The shipped shape is the MCP surface described in `docs/building/STAGES.md`.

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

## 8. Known limitations

- **HC HR-series uniqueness collisions**: ~3 sibling rows share `parent_uuid + epoch_millis`; deduped in-batch, invisible in stats. Cosmetic.
- **Wide-format BMT without `Time`**: timestamps land at 00:00:00 local.
- **No FIT-file (per-activity stream) ingestion**: out of scope by design (see §2).
