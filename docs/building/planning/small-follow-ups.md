# Mission m7 — small follow-ups (`hpipe inspect`, `gc` raw pruning, `fact_interval.unit`)

> Status: spec + plan for the overnight m7 mission. Author: orchestrator (Fable),
> 2026-06-12. Source: [ROADMAP.md](../../shared/ROADMAP.md) §"Smaller follow-ups"
> (all three items are named there as deferred). Branch:
> `overnight/m7-small-follow-ups`, cut from `overnight/m6-analyze-and-answer`.

## Why these three together

All three are small, named roadmap items that close known gaps in the operating
surface: a routing-preview verb that replaces inline-Python exploration, a gc
that can finally touch `data/raw/` without flying blind, and the
`fact_interval.unit` limitation called out in STATUS.md §Known limitations.
They share no code, so they are three independent work packages on one branch.

## Doctrine check (applies to every FR below)

- **Agent-first:** every surface here is a CLI verb or a schema column an agent
  drives; no human forms, no dashboards.
- **A level above:** `inspect` is specified against a *structural parser
  capability*, not a Garmin if-ladder; gc pruning is specified as one cutoff
  rule applied to N roots, not per-directory bespoke logic; the unit column is
  backfilled from the metric registry, not from an enumerated unit list.

---

## WP1 — `hpipe inspect <path>`: dry-run routing preview

**Problem.** Building the v1 Garmin handler set required inline-Python poking
at the dispatcher. The ROADMAP names `hpipe inspect <file>` as the replacement:
run the parser's dispatcher in dry-run mode, print file→handler routing and
unhandled entries. Today only the Garmin parser has a named dispatcher
(`_HANDLERS` in `garmin_gdpr.py`); other parsers route by extension/header
sniffing in `cli.py`.

**Shape (a level above).** Do **not** special-case Garmin in the CLI. Define a
small structural capability that any parser may expose, and make `inspect`
consume the capability:

- FR-1.1 A parser that can preview routing exposes a method
  `preview_routing(member_names: Sequence[str]) -> RoutingPreview` (exact name
  up to the implementer, but it must be a *structural* check — `hasattr` /
  `Protocol` — not an isinstance ladder or a registry edit). `RoutingPreview`
  is a small dataclass: ordered `(member_name, handler_name | None)` pairs.
  Routing a member through the preview MUST NOT read file contents, open a
  warehouse connection, or mutate anything — it is name-based dry-run only.
- FR-1.2 `hpipe inspect <path>` resolves the parser for `<path>` using the SAME
  discovery logic `ingest` uses (no second routing table), enumerates the
  archive/file member names without ingesting, calls the capability, and
  prints: one line per member with its handler (or `unhandled`), then a
  summary count (`N routed, M unhandled`).
- FR-1.3 A parser without the capability is reported honestly: exit code 0,
  message naming the parser and stating it does not support routing preview
  (plus the rule for adding it: expose the capability). No crash, no fake
  preview.
- FR-1.4 The Garmin GDPR parser implements the capability tonight by
  delegating to its existing `_dispatch`/`_HANDLERS` table (no duplication of
  patterns). Unhandled members appear in the preview exactly as the ingest
  path would log them.
- FR-1.5 `inspect` never writes: no warehouse connection, no `data/` mutation,
  no ingest_run row. (It is the read-only twin of `ingest` discovery.)

**Edge cases (each needs a test):**
- E1.1 path does not exist → non-zero exit, clear message.
- E1.2 path exists but no parser claims it → exit 0, honest "no parser
  matched" message (mirror `ingest`'s unmatched behavior, but read-only).
- E1.3 parser matched but lacks the capability → FR-1.3 message.

## WP2 — `hpipe gc`: prune `data/raw/` + `--dry-run`

**Problem.** `gc` today prunes only `settings.exports_dir`, has no preview
mode, and is called programmatically as `gc(keep=3)` from `run_monthly()`.
`data/raw/` holds the operator's staged source artifacts — for un-exported
files it may be the only local copy.

**Shape.** One cutoff rule, N roots, explicit opt-in for the dangerous root:

- FR-2.1 Add `--dry-run` to `gc`: prints exactly what WOULD be removed (same
  lines as the real run, prefixed so it is unambiguous) and removes nothing.
  Applies to both roots.
- FR-2.2 Extend gc to optionally prune `settings.raw_dir` top-level entries
  older than the same `--keep` cutoff (mtime-based, same rule as exports —
  one rule, two roots; files AND directories under `data/raw/` are eligible,
  since operators stage both).
- FR-2.3 Raw pruning is **opt-in** via a flag (e.g. `--raw`), default OFF.
  Rationale (spec decision, record in CHANGELOG): `run_monthly()` calls
  `gc(keep=3)` unattended; silently flipping it to delete staged source
  artifacts is unacceptable without the human choosing it. `run_monthly`'s
  behavior tonight is unchanged. The ROADMAP wording ("extension to also
  prune data/raw") is satisfied by the capability existing; defaulting it on
  inside an unattended job is a human decision, not an overnight one.
- FR-2.4 The programmatic call in `run_monthly()` keeps working unchanged
  (Typer-default-safe: new params must have defaults compatible with the
  existing `gc(keep=3)` invocation).
- FR-2.5 `--dry-run` with `--raw` previews raw pruning too; dry-run NEVER
  removes anything from either root.

**Edge cases (each needs a test):**
- E2.1 `--dry-run` over a populated exports dir: listed, not deleted.
- E2.2 `--raw` deletes an old raw entry, keeps a fresh one; without `--raw`
  the old raw entry survives.
- E2.3 missing exports dir / missing raw dir → graceful message, exit 0
  (current behavior preserved).

## WP3 — `hp.fact_interval.unit` column + backfill + drop in-memory field

**Problem.** STATUS.md Known limitations: "`fact_interval` has no `unit`
column; carried in memory only." In fact the in-memory `Interval.unit` is
*already dropped silently* in `dedupe._interval_frame` — parser-supplied
values never reach the warehouse. The fix makes the warehouse the single
source of unit truth via `dim_metric.canonical_unit`.

**Shape.**

- FR-3.1 New migration `src/premura/store/migrations/006_interval_unit.sql`
  (NOT `003_...` — the ROADMAP entry predates current numbering; 003–005 are
  taken; follow the existing `NNN_name.sql` + `IF NOT EXISTS`-idempotent
  convention): `ALTER TABLE hp.fact_interval ADD COLUMN IF NOT EXISTS unit
  VARCHAR;` plus a backfill `UPDATE` setting `unit` from the owning
  `dim_metric.canonical_unit` where `unit IS NULL`. The backfill must be
  idempotent (re-running migrations must not error or churn).
- FR-3.2 The interval load path populates `unit` for NEW rows from
  `dim_metric.canonical_unit` (single source: the metric registry — never
  from parser-supplied strings). Implementer chooses the cheapest correct
  point (loader INSERT join/lookup or equivalent); the invariant is: after
  any ingest, every `fact_interval` row whose metric exists in `dim_metric`
  has `unit = canonical_unit`.
- FR-3.3 Drop the in-memory-only `Interval.unit` field: remove it from the
  `Interval` dataclass (`parsers/base.py`), from `_NormalizedRow`/normalize
  plumbing in `store/dedupe.py`, and from all parser construction sites
  (recon found 9 across `health_connect.py`, `sleep_as_android.py`,
  `garmin_gdpr.py`) and any tests constructing `Interval(unit=...)`. The
  parser CONTRACT does not promise `unit` on Interval persistence, but check
  `src/premura/parsers/CONTRACT.md` and update it if it mentions the field.
- FR-3.4 Remove the STATUS.md Known-limitations line about `fact_interval`
  unit (single-home rule: STATUS reflects shipped state) — done in the doc
  sync, not before the code lands.

**Edge cases (each needs a test):**
- E3.1 Migration idempotency: `run_migrations` twice on a warehouse that
  already has the column + backfilled rows → no error, values stable.
- E3.2 Backfill correctness: a pre-006 warehouse with existing interval rows
  gets `unit` matching each row's metric's `canonical_unit`.
- E3.3 New ingest after 006: inserted interval rows carry the canonical unit
  (end-to-end through a parser fixture, not just a unit test on the loader).

## Cross-cutting

- FR-X.1 CHANGELOG entry for the mission (repo convention, one entry,
  newest-first) + ROADMAP "Smaller follow-ups" updated to reflect shipped
  state + STATUS.md CLI verb list gains `inspect` and the gc flags, and the
  Known-limitations line is removed (respect the STATUS line cap enforced by
  `tests/test_docs_structure.py`).
- NFR-1 No existing behavior changes without a flag: `gc` invoked exactly as
  today behaves exactly as today (modulo the new flags existing); `ingest`
  path untouched by WP1; existing tests stay green.
- NFR-2 All four gates green: `uv run ruff check`, `uv run ruff format
  --check`, changed-scope `uv run mypy`, full `uv run pytest`.
- NFR-3 No PHI, no real exports: all fixtures synthetic.

## Plan

Sequential WPs on this branch, /tdd (red-green-refactor), commit at each green
checkpoint:

1. WP3 first (migration + loader + field drop) — it touches the most shared
   code; land it while the diff surface is clean.
2. WP1 (`inspect` + capability + Garmin implementation).
3. WP2 (`gc` flags) — smallest, last.
4. Doc sync (CHANGELOG/ROADMAP/STATUS) as the final commit.

Implementer may reorder WP1/WP2 freely; WP3-before-parsers ordering is only a
suggestion. Deviations from this spec are allowed when the code contradicts a
spec assumption — flag every deviation explicitly in the final report.

## Named deferred (out of scope tonight)

- Routing preview for non-Garmin parsers (capability exists; each parser adopts
  it in its own follow-up).
- Defaulting raw pruning ON in `run_monthly` (human decision).
- Any `unit` column on `fact_measurement` (separate item if ever named).
