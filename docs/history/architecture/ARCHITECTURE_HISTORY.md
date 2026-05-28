# premura — Architecture and Implementation History

> Status: proposal/archive. Historical implementation and architecture record, not the primary source of truth.
>
> Companion to [SPEC.md](../product/SPEC.md), [USERJOURNEY.md](../product/USERJOURNEY.md), [STATUS.md](../operations/STATUS.md), [ROADMAP.md](../product/ROADMAP.md).
> Repo working directory: operator's choice (referred to as `$REPO` below).
> Python package: `premura`; CLI entry: `hpipe`
> Existing on disk: `uv init` baseline (Python 3.11, empty `main.py`, empty `pyproject.toml` deps) — bootstrap step 2 replaces these.

## Context

Health Connect on Android is structurally incapable of holding the user's full health picture:

- **HRV, respiratory rate, stress, Body Battery, training load, SpO2** — Garmin Connect deliberately doesn't bridge most of these (the rest have no HC schema at all). Verified against a real Health Connect export (`~/Downloads/health_connect_export.db`, HC v20, ~200 MB): `heart_rate_variability_rmssd_record_table` and `respiratory_rate_record_table` are empty; Garmin's declared `record_types_used` doesn't even mention them.
- **Body composition** (body fat %, lean mass, body water, waist/hips) — Body Measurement Tracker only bridges weight + height to HC; the rest never leaves the app.
- **Manual BP** logged in Garmin Connect — not in the supported bridge list.

The new approach abandons HC as the target store. Instead: monthly GDPR/data dumps from 4 apps land on this Mac, get parsed into a unified **DuckDB** warehouse, then **age**-encrypted and pushed to Google Drive via **rclone**. HC becomes one input, not the destination.

Outcome: a single local SQL-queryable warehouse containing HRV, respiration, stress, Body Battery, body composition, sleep cycles, and everything else the phone bridges blocks — fully under the user's control, with encrypted off-site backup.

## Scope decisions (confirmed at planning time)

- **Sources**: Garmin Connect (GDPR zip), Health Connect (auto-export `.db` on Drive), Sleep as Android (CSV), Body Measurement Tracker (CSV).
- **Store**: single-file DuckDB at `$REPO/data/duck/health.duckdb`.
- **Encryption**: `age` with a recipient public key; private key stored at `~/.config/premura/age.key` (chmod 600) and backed up in a password manager.
- **Upload**: `rclone copy` to `gdrive:/backups/premura/YYYY/MM/`.
- **Cadence**: monthly. GDPR exports are manual button-clicks — pipeline waits for the user to drop files into `data/inbox/`.
- **Code repo**: this repo (`$REPO`) holds code only. The operator's personal knowledge wiki (separate repo, location operator-specific) gets a project hub page; no code lives there.

## Repo layout — `$REPO/`

```
premura/
├── pyproject.toml          # uv-managed; entry: hpipe = "premura.cli:main"
├── uv.lock
├── .python-version         # 3.11 (set by uv init)
├── .gitignore              # data/, .venv/, *.zip, *.db, *.age, .env
├── README.md               # ops only: setup, run, key recovery
├── src/premura/
│   ├── cli.py              # typer: ingest, status, export, upload, doctor, run-monthly
│   ├── config.py           # pydantic-settings: paths, age recipient, rclone remote, unit overrides
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── entrypoint.py   # FastMCP stdio entrypoint
│   │   └── server.py       # read-only warehouse tool implementations
│   ├── ops/
│   │   ├── encrypt.py      # subprocess wrapper for age
│   │   ├── notify.py       # osascript wrapper
│   │   ├── upload.py       # subprocess wrapper for rclone
│   │   └── launchd.plist.j2
│   ├── store/
│   │   ├── dedupe.py
│   │   ├── duck.py         # DuckDB connection + migrations runner
│   │   ├── loader.py
│   │   └── migrations/001_init.sql
│   ├── parsers/
│   │   ├── base.py         # Measurement dataclass + Parser protocol
│   │   ├── health_connect.py
│   │   ├── garmin_gdpr.py
│   │   ├── sleep_as_android.py
│   │   └── bmt.py
│   ├── dim_metric.yaml     # seed data, reviewable
│   └── ui/
├── tests/
│   ├── fixtures/           # anonymised mini-DBs, < 100KB each
│   ├── test_parsers/
│   ├── test_dedupe.py
│   └── test_schema_regression.py  # checks against real HC export
├── data/                   # gitignored
│   ├── inbox/              # user drops Garmin zip, SA Android CSV, BMT CSV here
│   ├── raw/                # extracted/normalized pre-DB
│   ├── duck/health.duckdb
│   └── exports/YYYY-MM/    # encrypted artifacts ready to upload
└── ops/bootstrap.sh        # brew install age rclone, mkdir, gen key, rclone config prompt
```

**Key dep versions** (pin minor):

```toml
dependencies = [
  "duckdb>=1.1,<2",
  "pydantic>=2.9,<3", "pydantic-settings>=2.5,<3",
  "typer>=0.12,<1", "rich>=13.9,<14",
  "polars>=1.12,<2",          # CSV/Parquet ingest, native DuckDB interop
  "fitparse>=1.2,<2",         # Garmin .fit (only if we ingest activity streams)
  "python-dateutil>=2.9,<3", "tzlocal>=5.2,<6",
  "structlog>=24.4,<25",
]
[project.optional-dependencies]
dev = ["pytest>=8.3,<9", "pytest-cov>=5", "ruff>=0.7", "mypy>=1.13"]
```

Use **`uv`** (already installed), not poetry.

## DuckDB schema — long-format star

Reject mirroring HC's table-per-record-type — 4 sources × 30+ metric types = combinatorial mess. One fact-per-cardinality, two dims, raw JSON escape hatch.

`src/premura/store/migrations/001_init.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS hp;

CREATE TABLE hp.dim_metric (
    metric_id      VARCHAR PRIMARY KEY,           -- 'hrv_rmssd', 'weight', 'heart_rate'
    display_name   VARCHAR NOT NULL,
    canonical_unit VARCHAR NOT NULL,              -- 'ms','kg','bpm','%','kcal','m','breaths_per_min'
    value_kind     VARCHAR NOT NULL,              -- 'instantaneous'|'aggregate'|'interval'
    description    VARCHAR
);

CREATE TABLE hp.dim_source (
    source_id      VARCHAR PRIMARY KEY,           -- 'garmin_gdpr:Forerunner965' / 'hc:com.google.android.apps.fitness|Pixel 9'
    source_kind    VARCHAR NOT NULL,              -- 'health_connect'|'garmin_gdpr'|'sleep_as_android'|'bmt'
    app_package    VARCHAR, app_name VARCHAR,
    device_manufacturer VARCHAR, device_model VARCHAR,
    first_seen TIMESTAMP, last_seen TIMESTAMP
);

CREATE TABLE hp.fact_measurement (
    measurement_id UBIGINT PRIMARY KEY,
    ts_utc         TIMESTAMP NOT NULL,
    local_tz       VARCHAR,                       -- IANA when known (SA Android), else "+02:00" form
    metric_id      VARCHAR NOT NULL REFERENCES hp.dim_metric(metric_id),
    value_num      DOUBLE,
    value_text     VARCHAR,                       -- categorical sleep stages, exercise labels
    unit           VARCHAR NOT NULL,
    source_id      VARCHAR NOT NULL REFERENCES hp.dim_source(source_id),
    source_uuid    VARCHAR,                       -- HC uuid hex / synthesized
    dedupe_key     VARCHAR NOT NULL UNIQUE,
    ingested_at    TIMESTAMP DEFAULT now(),
    ingest_batch   VARCHAR,                       -- ULID of run
    raw_payload    JSON
);
CREATE INDEX ix_fm_ts_metric ON hp.fact_measurement(ts_utc, metric_id);
CREATE INDEX ix_fm_metric_ts ON hp.fact_measurement(metric_id, ts_utc);

CREATE TABLE hp.fact_interval (
    interval_id  UBIGINT PRIMARY KEY,
    metric_id    VARCHAR NOT NULL REFERENCES hp.dim_metric(metric_id),
    start_utc    TIMESTAMP NOT NULL, end_utc TIMESTAMP NOT NULL, local_tz VARCHAR,
    value_num    DOUBLE, value_text VARCHAR,
    source_id    VARCHAR NOT NULL REFERENCES hp.dim_source(source_id),
    source_uuid  VARCHAR, parent_uuid VARCHAR,    -- sleep_stage.parent = sleep_session.uuid
    dedupe_key   VARCHAR NOT NULL UNIQUE,
    ingested_at  TIMESTAMP DEFAULT now(), ingest_batch VARCHAR,
    raw_payload  JSON
);
CREATE INDEX ix_fi_start_metric ON hp.fact_interval(start_utc, metric_id);

CREATE TABLE hp.ingest_run (
    batch_id      VARCHAR PRIMARY KEY,            -- ULID
    started_at    TIMESTAMP DEFAULT now(), finished_at TIMESTAMP,
    source_kind   VARCHAR, source_path VARCHAR, source_sha256 VARCHAR,
    rows_inserted BIGINT, rows_skipped_dup BIGINT, notes VARCHAR
);
```

Seed `dim_metric` from `src/premura/dim_metric.yaml` so the controlled vocab is reviewable.

## Per-source parsers

### Health Connect (`.db`, SQLite v3, `user_version=20`)

Open via DuckDB's sqlite_scanner (faster than stdlib for table scans):
`INSTALL sqlite; LOAD sqlite; ATTACH 'export.db' AS hc (TYPE sqlite, READ_ONLY);`

Tables to read with the metric mapping (all confirmed present in a real Health Connect v20 export):

| HC table | metric_id(s) | Conversion |
|---|---|---|
| `heart_rate_record_table` + `heart_rate_record_series_table` | `heart_rate` | bpm, as-is |
| `resting_heart_rate_record_table` | `resting_hr` | bpm |
| `heart_rate_variability_rmssd_record_table` | `hrv_rmssd` | ms (0 rows now — parser ready) |
| `respiratory_rate_record_table` | `resp_rate` | breaths/min (0 rows now) |
| `oxygen_saturation_record_table` | `spo2` | % |
| `weight_record_table` | `weight` | **grams → kg (÷1000)** |
| `body_fat_record_table` | `body_fat_pct` | % |
| `body_water_mass_record_table`, `bone_mass_record_table`, `lean_body_mass_record_table` | as named | grams → kg |
| `height_record_table` | `height` | m, as-is |
| `vo2_max_record_table` | `vo2_max` | mL/kg/min |
| `basal_metabolic_rate_record_table` | `bmr` | verify unit at parse — HC has changed between watts and kcal/day |
| `steps_record_table` | `steps` | interval |
| `distance_record_table` | `distance` | m |
| `active_calories_burned_record_table`, `total_calories_burned_record_table` | `active_kcal`, `total_kcal` | kcal |
| `sleep_session_record_table` + `sleep_stages_table` | `sleep_session`, `sleep_stage` | interval |
| `exercise_session_record_table` | `exercise_session` | interval, carries `exercise_type` code |
| `blood_pressure_record_table` | `bp_systolic`, `bp_diastolic` | mmHg |
| `blood_glucose_record_table` | `blood_glucose` | mmol/L |
| `skin_temperature_record_table`, `body_temperature_record_table` | as named | °C |
| `mindfulness_session_record_table` | `mindfulness_session` | interval |
| `hydration_record_table` | `hydration` | L |

**Critical conversions** (verified against a real HC v20 DB):
- `ts_utc = datetime.fromtimestamp(time/1000, tz=UTC)` — `time` is ms-epoch.
- `local_tz = f"{zone_offset/3600:+03.0f}:00"` — **zone_offset is in SECONDS, not ms**.
- `uuid` is a 16-byte BLOB — hex-encode at parse time (32 chars).
- Weight is in **grams** (e.g. `weight=75000.00` = 75.0 kg). Divide at parse, store kg.

JOIN `application_info_table` + `device_info_table` once at parse start, cache `source_id` lookups.

Defensive querying: at run start, `PRAGMA user_version` + `PRAGMA table_info(<t>)` for each table. Missing tables → warn-and-skip, not fail. Never `SELECT *` — name columns.

### Garmin GDPR zip

Structure: zip-of-zips with `DI_CONNECT/`, `DI-Connect-Wellness/`, `DI-Connect-Activity/`, etc. Walk by **filename pattern**, not folder (Garmin changes layout):

| Pattern | metric_id |
|---|---|
| `HRV_*.json`, `HRV_NIGHTLY_*.json` | `hrv_rmssd_overnight` (continuous) — distinguish from Health Snapshot's `hrv_rmssd_snapshot` |
| `STRESS_*.json` | `stress` (0–100, minute-level) |
| `BODY_BATTERY_*.json` | `body_battery` (0–100, 3-min interval) |
| `RESPIRATION_*.json` | `resp_rate` |
| `SPO2_*.json` | `spo2` |
| `TRAINING_LOAD_*.json`, `TRAINING_STATUS_*.json`, `TRAINING_READINESS_*.json` | training metrics |
| `*_wellnessData_*.json`, `UDS*.json` | daily rollups (resting HR, steps, intensity minutes) |
| `summarizedActivities*.json` | activity summaries |
| `*.fit` in `DI-Connect-Fitness-Uploaded-Files/` | only ingest if doing per-activity streams (defer to v2) |

Time: use `*Gmt` epoch-ms variants when present; fall back to ISO-with-offset.
Synthesize `source_uuid = f"garmin:{record_type}:{summaryId or calendarDate}"`.

Dispatcher pattern: `{filename_regex: handler_fn}` — small, testable.

### Sleep as Android

CSV, one row per night, very wide (per-minute columns with `HH:MM` headers). Parse with `polars.read_csv(infer_schema_length=0)`, melt the per-minute columns into long format. `Tz` column is IANA — **trust this as the authoritative TZ source across all 4 feeds**. `source_uuid = f"saa:{Id}"`.

Metrics emitted: `sleep_actigraphy` (per-minute), `sleep_session` (interval), `sleep_rating`, `sleep_deep_pct`.

### Body Measurement Tracker

CSV with `Date, Time, Weight, BodyFat, Muscle, Water, BMI, Visceral, BoneMass, Notes` plus user-custom columns. **Units are not embedded** — config keys `parsers.bmt.weight_unit` (kg|lb) and `parsers.bmt.length_unit` (cm|in) drive conversion. Unknown columns → `metric_id = f"bmt_custom:{slugify(col)}"`, `unit='unknown'`. Synthesize `source_uuid = f"bmt:{sha1(date+time+metric+value)}"`.

## Dedupe — 3 tiers

1. **Native ID per source**: `dedupe_key = f"{source_kind}:{source_uuid}"`. HC uuid as hex, Garmin synthesized key, SA Android row Id, BMT hash.
2. **Cross-source overlap** (HC's Garmin-bridged data vs Garmin GDPR): compute `match_key = f"{metric_id}|{round(ts_utc)}|{round(value_num, 3)}"`. If a row exists from a higher-priority source within ±2s and ±0.01, skip. Priority: **Garmin GDPR > HC(Garmin bridge) > HC(other) > SA Android > BMT**.
3. **Same-source updates** (Garmin recomputes daily summaries between exports): for synthesized Garmin keys, `INSERT … ON CONFLICT (dedupe_key) DO UPDATE`. Never overwrite HC native-UUID rows.

Dedupe runs at the parser → store boundary. Stage tables append-only; fact tables enforce UNIQUE.

## Encrypt + upload

Bootstrap (once):
```bash
brew install age rclone                                   # NOT installed currently — verified
mkdir -p ~/.config/premura
age-keygen -o ~/.config/premura/age.key           # public key to recipients.txt
chmod 600 ~/.config/premura/age.key
# Back up age.key in your password manager — WITHOUT IT BACKUPS ARE UNRECOVERABLE
rclone config                                              # remote name: gdrive, scope: drive.file
```

Per monthly run (`hpipe export --month YYYY-MM && hpipe upload`):
```bash
month=2026-05
mkdir -p data/exports/$month
cp data/duck/health.duckdb data/exports/$month/health.duckdb
tar -C data/raw -czf data/exports/$month/raw.tar.gz .
age -R ~/.config/premura/recipients.txt \
    -o data/exports/$month/health.duckdb.age data/exports/$month/health.duckdb
age -R ~/.config/premura/recipients.txt \
    -o data/exports/$month/raw.tar.gz.age data/exports/$month/raw.tar.gz
rm -P data/exports/$month/health.duckdb data/exports/$month/raw.tar.gz
year=${month%-*}; mo=${month#*-}
rclone copy data/exports/$month/ gdrive:/backups/premura/$year/$mo/ \
    --transfers 2 --checksum --immutable
rclone lsl gdrive:/backups/premura/$year/$mo/   # verify
```

Drive layout: `gdrive:/backups/premura/YYYY/MM/{health.duckdb.age, raw.tar.gz.age, manifest.json}`. `manifest.json` is cleartext metadata (sha256s, batch_id, age recipient fingerprint) — no PHI.

## Automation — macOS launchd

`~/Library/LaunchAgents/com.example.premura.monthly.plist` (label is operator-configurable; rendered from `ops/launchd.plist.j2`):

- `StartCalendarInterval`: day 1, 10:00 local.
- Runs `hpipe run-monthly`, which:
  1. macOS notification: "Request fresh Garmin GDPR export at garmin.com/datamanagement/, drop SA Android + BMT exports in `data/inbox/`, then `touch data/inbox/.ready`".
  2. Waits for `.ready` (polls hourly for 7 days). If absent after 7 days → renotify and exit.
  3. On `.ready`: ingest → export → encrypt → upload → notify success/failure.

Optional second agent for daily HC pickup: `…hourly-hc-pickup.plist` pulls the latest HC `.db` from Drive daily (HC auto-exports daily, **not monthly** despite the `export_period_key=30` in your preference table — HC overwrites the file), runs only the HC parser, skips encryption+upload.

`hpipe install-launchd` / `uninstall-launchd` for reproducibility.

## Wiki integration

If the operator maintains a personal knowledge wiki (separate repo, location operator-specific), add a single project hub page following that wiki's layout conventions.

Suggested frontmatter:
```yaml
---
title: "Premura"
type: project
tags: [personal-data, health, gdpr, duckdb, encryption, garmin, health-connect]
sources: ["[self]", "~/Downloads/health_connect_export.db"]
summary: "Monthly GDPR-dump ingestion from Garmin/HC/SAA/BMT into a unified encrypted DuckDB, backed up to Drive. Bypasses Health Connect's missing-metric problem."
created: 2026-05-20T11:00:00Z
updated: 2026-05-20T11:00:00Z
---
```

Sections: "Why this shape" (the HC bridge gap), "Architecture", "Cadence + manual steps", "Schema", "Related" (cross-link any neighbouring health/OCR project — note they are distinct).

Update the wiki's `index.md` to list the new project. Defer entity pages (`[[duckdb]]`, `[[age-encryption]]`, `[[rclone]]`, `[[garmin-connect]]`, `[[health-connect]]`, `[[sleep-as-android]]`, `[[body-measurement-tracker]]`) — typical convention: 2nd reference triggers entity creation, so wait for the project hub to be the first reference.

## Build order

1. `brew install age rclone` + `age-keygen` + `rclone config` (manual, ~15 min).
2. `cd $REPO && uv add` deps (repo already `uv init`d); `rm main.py`, create `src/premura/__init__.py`; commit `pyproject.toml` + `uv.lock`.
3. `store/duck.py` + `001_init.sql` + `dim_metric.yaml`; smoke-test on empty DB.
4. `parsers/health_connect.py` against a real HC export (e.g. `~/Downloads/health_connect_export.db`). Target: hundreds of thousands of fact rows + tens of thousands of sleep stages + hundreds of sleep sessions. Sanity-check weight (÷1000), HR distributions.
5. `dedupe.py` — HC alone gives a dedupe scenario (Garmin-bridged HR vs Fit HR).
6. `parsers/sleep_as_android.py` (smallest format, fastest win).
7. `parsers/bmt.py`.
8. `parsers/garmin_gdpr.py` — biggest unknown; do last with real zip in hand.
9. CLI verbs wired.
10. `encrypt.py` + `upload.py` thin wrappers; round-trip test: encrypt → upload → download → decrypt → byte-diff.
11. launchd plist rendered + loaded; manual trigger test.
12. Wiki hub page (optional) committed in the operator's personal knowledge-wiki repo.

Estimated effort: 3–4 evenings for steps 1–7+9–12; step 8 (Garmin GDPR) is open-ended — budget a full day after the user has an actual GDPR zip downloaded.

## Out of scope (explicit)

- **No `python-garminconnect` / live API**: scrapes login, breaks regularly, ToS-violating. GDPR dump is the legitimate path.
- **No Android app of our own** for HC write-back: HC has no documented import path; building an app means signing keys, Play Store policy, ongoing maintenance.
- **No Apple Health**: v1 operator is on Android (verified in HC `device_info_table`). YAGNI.
- **No HC re-injection of derived metrics**: warehouse is the analytics endpoint.
- **No comingling with `[[health-records]]`** (OCR of past medical scans) — different domain, cadence, threat model. Cross-link only.

## Critical files to create

All paths relative to `$REPO/`:

- `pyproject.toml`
- `src/premura/store/migrations/001_init.sql`
- `src/premura/dim_metric.yaml`
- `src/premura/parsers/health_connect.py`
- `src/premura/parsers/garmin_gdpr.py`
- `src/premura/parsers/sleep_as_android.py`
- `src/premura/parsers/bmt.py`
- `src/premura/store/dedupe.py`
- `src/premura/cli.py`
- `src/premura/ops/encrypt.py`, `src/premura/ops/upload.py`
- `src/premura/mcp/server.py`
- `src/premura/ops/launchd.plist.j2`
- `ops/bootstrap.sh`
- (Optional) hub page + index entry in the operator's personal knowledge wiki.

## Reference files on disk (read-only inputs)

- `~/Downloads/health_connect_export.db` (or wherever the operator stores their HC export) — HC v20, validates parser against real data.
- The operator's personal knowledge wiki (if maintained) supplies layout/tag conventions and any neighbouring health/OCR project for cross-linking.

## Verification

End-to-end test ladder (each step must pass before proceeding):

1. **Schema smoke**: `hpipe doctor` reports `age`, `rclone`, `uv` present; DuckDB warehouse opens; `dim_metric` rows seeded.
2. **HC parser regression**: `pytest tests/test_schema_regression.py` opens the real `health_connect_export.db`, asserts `user_version=20`, asserts every column the parser reads exists. Marked `@pytest.mark.regression`, skipped when file absent.
3. **Ingest HC**: `hpipe ingest --source hc ~/Downloads/health_connect_export.db`. Expected on a multi-year export: hundreds of thousands of rows in `fact_measurement`, tens of thousands in `fact_interval`. Spot-check: `SELECT MIN(value_num), MAX(value_num) FROM hp.fact_measurement WHERE metric_id='weight'` → values land in a plausible adult range (~40–200 kg).
4. **Dedupe sanity**: ingest the same HC file twice → `rows_skipped_dup` equals first run's `rows_inserted`; `COUNT(*)` unchanged.
5. **Sample parser unit tests**: each parser converts a known fixture row to a known `Measurement` (timezones in UTC, units canonical).
6. **Cross-source dedupe**: synthesize a Garmin GDPR row and an HC-from-Garmin row at the same instant + value → exactly one row in fact table, `source_id` = Garmin GDPR.
7. **Encrypt round-trip**: `hpipe export --month 2026-05 && age -d -i ~/.config/premura/age.key data/exports/2026-05/health.duckdb.age | diff - data/duck/health.duckdb` → no output.
8. **Upload round-trip**: `hpipe upload`; `rclone lsl gdrive:/backups/premura/2026/05/` shows expected files with matching sizes.
9. **Launchd dry run**: `launchctl bootstrap` then `launchctl kickstart -k gui/$(id -u)/com.example.premura.monthly` (use whichever label the rendered plist uses) → macOS notification fires, run-monthly waits for `.ready`.
10. **Wiki hub page**: `cat wiki/projects/premura/premura.md` validates against `wiki/meta/layout.md` frontmatter spec; `wiki/index.md` lists it alphabetically; no broken wikilinks (`/wiki-lint`).

## Edge cases & mitigations (executive summary)

- **Garmin 5y activity / 2y health horizon**: fact tables are append-only, `ingest_batch` tagged. Old rows survive even when not in latest dump.
- **HC schema drift**: defensive `PRAGMA table_info` per table; warn-and-skip missing optional columns; never `SELECT *`.
- **Time zones**: canonical `ts_utc` (UTC) always; `local_tz` IANA when known, else `+HH:MM`. Test DST boundary in sleep stages.
- **Unit drift**: convert at parse, store `unit` per row; range-sanity tests catch config errors.
- **HC `dedupe_hash` column**: ignore — `uuid` is sufficient and more debuggable.
- **BMT unit toggle change** (user flips kg→lb mid-history): rolling-median delta >20% triggers warning.
- **Idempotency**: triple-locked — `dedupe_key UNIQUE`, `ingest_run.source_sha256` skip-if-seen, stage truncate-and-reload.
- **Disk**: `data/exports/` keeps last 3 months locally; `hpipe gc --keep 3`. Drive is durable store.
- **age.key loss = total backup loss**: README + first-run notification reminds user to back up to password manager.
