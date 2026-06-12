# Fixture auto-generator (synthetic vendor fixtures for the acceptance harness)

> Status: spec + plan for the overnight m5 mission. Implements the "fixture
> auto-generator" named as deferred in
> [`docs/shared/ROADMAP.md`](../../shared/ROADMAP.md). Branch:
> `overnight/m5-fixture-auto-generator` (from `overnight/m4-improvement-hook`).
> Companion reading: [`DOCTRINE.md`](../../shared/DOCTRINE.md),
> [`src/premura/parsers/CONTRACT.md`](../../../src/premura/parsers/CONTRACT.md),
> the committed fixture pairs under `tests/fixtures/session_log/` and
> `tests/fixtures/intake_scenario/`, and the grader's three rules in
> `src/premura/harness/grader.py`.

## Why

The acceptance harness grades whether a model can build an honest parser for
an **unfamiliar** vendor export, but it owns exactly two handwritten fixtures.
A model under trial may simply have memorized Fitbit-shaped exports, and two
challenges cannot exercise the contract's breadth (weird field names, odd
timestamp encodings, decoy columns). The auto-generator produces fresh,
never-seen synthetic vendor fixtures — a CSV plus its grader-only ground-truth
manifest — on demand, deterministically from a seed, so the harness can always
present a genuinely unfamiliar source. Synthetic only: fabricated vendor
names, invented values, never derived from or seeded by a real export.

## Scope (one sentence)

A deterministic, seeded, offline generator that fabricates a synthetic vendor
fixture (CSV + grader-only manifest, matching the committed fixture pairs'
exact shapes), self-validates it against the grader's ground-truth invariants,
can hand it to the existing harness as a `Scenario`, and is invocable as
`python -m premura.harness.fixture_gen` — observation drawer tonight, with a
drawer-strategy seam so further drawers are an add-a-strategy change.

## Functional requirements

- **FR-1 (deterministic generation core).** A new
  `src/premura/harness/fixture_gen.py` exposes
  `generate_fixture(spec: FixtureSpec) -> GeneratedFixture`, where
  `FixtureSpec` carries at least `seed: int`, `drawer: str`, and `row_count`
  (bounded, defaulted). Generation is pure and offline: all randomness flows
  from `random.Random(spec.seed)` — the same spec yields byte-identical CSV
  and manifest text on every run, on every machine. No model calls, no clock
  reads, no network, no reads of any operator data path.
- **FR-2 (drawer strategies, a level above).** Drawer-specific generation
  (column families, manifest shape, canonical targets) lives behind a small
  strategy registry keyed by drawer id, mirroring how the harness keys drawer
  probes. Tonight only the `observation` strategy is implemented; the registry
  plus a documented add-a-strategy rule (module docstring) is the extension
  point — adding `intake` later must require no edits to the core. An unknown
  drawer id fails loudly.
- **FR-3 (challenge content).** A generated observation fixture must be a fair
  parser-generation challenge, by construction: (a) one or more mappable
  columns whose canonical metrics are drawn from the repo's metric registry
  seed (`tests/fixtures/dim_metric_seed.yaml` — never a list hardcoded in
  code), each canonical metric appearing at most once (the grader's
  distinct-metric rule); (b) at least one declared-gap column with no
  canonical home (the honesty decoy); (c) a structural timestamp column in one
  of several encodings (e.g. ISO 8601, epoch seconds, epoch microseconds)
  chosen by seed; (d) vendor-weird column names produced by a registry of
  naming transforms (abbreviation, unit suffix, camelCase jargon, …) with a
  documented add-a-transform rule — the fabricated vendor/source name is
  invented, never a real vendor's. Values are plausible for the metric's unit
  but entirely invented.
- **FR-4 (manifest fidelity).** The generated manifest matches the committed
  observation manifest shape exactly — `source`, `csv`, `source_fields` with
  `name` + `canonical_metric` (null for structural/decoy columns) — and its
  text carries the GRADER-ONLY warning header, so existing grader/manifest
  consumers need no changes to read it.
- **FR-5 (self-validation).** `validate_fixture(fixture) -> None` (raising
  `ValueError` with a precise message on the first violation) enforces the
  ground-truth invariants: every CSV column appears exactly once in the
  manifest; non-null canonical metrics are unique and exist in the metric
  registry seed; at least one mappable and at least one null-metric column;
  `row_count` rows, all parseable in the declared timestamp encoding.
  `generate_fixture` runs it before returning, so an invalid fixture can never
  escape.
- **FR-6 (disk writer + scenario adapter).** `write_fixture(fixture, out_dir)
  -> WrittenFixture` writes the CSV + manifest pair (refusing to overwrite
  unless told to), and a `scenario_for(written) -> Scenario` adapter yields a
  scenario the existing harness entry accepts unchanged. The harness's
  synthetic-source recognition must treat a generated fixture as synthetic
  (scoreboard-persistable) via an explicit marker the writer controls — never
  by loosening the rule so that arbitrary or real operator paths start
  counting as synthetic; a test proves a real-looking path is still
  non-synthetic.
- **FR-7 (CLI entry).** `python -m premura.harness.fixture_gen --seed N
  [--drawer observation] [--out DIR] [--rows K]` generates, validates, writes,
  and prints the written paths plus a one-line summary (drawer, source name,
  column count, mappable/gap split). Exit code is nonzero on any failure. The
  pattern mirrors `live_trial_ollama`'s `_main()`.

## Non-functional requirements

- **NFR-1 (synthetic only).** The generator never reads operator data, real
  exports, or the warehouse; its only inputs are the spec and the committed
  metric registry seed. No PHI can exist in its output by construction.
- **NFR-2 (no new dependencies).** No new third-party packages
  (`test_no_new_third_party_dependency` stays green).
- **NFR-3 (no default-path behavior change).** Existing harness runs, tests,
  and committed fixtures are byte-for-byte unaffected; the generator only acts
  when explicitly invoked, and generated artifacts land where the caller
  points `--out` (never silently into `tests/fixtures/`).
- **NFR-4 (altitude).** No vendor enumeration (`if source == "garmin"`
  ladders) and no hardcoded metric lists in code: metrics come from the
  registry seed, drawer behavior from the strategy registry, naming weirdness
  from the transform registry — each with its add rule documented where it
  lives.
- **NFR-5 (offline deterministic tests).** All tests run in the default suite
  (no `live_trial` marker, no Ollama); determinism is asserted by generating
  twice from one seed and comparing bytes.

## Out of scope

The `intake` drawer strategy (the seam ships; the strategy is follow-on),
non-CSV formats (JSON/SQLite/zip exports), auto-generated reference parsers,
committing generated fixtures as new permanent scenarios, model-generated
content of any kind, and difficulty-tier/curriculum policies — all named
deferred in ROADMAP.md.

## Plan — work packages

- **WP1 — generation core (FR-1, FR-2, FR-3).** `FixtureSpec`,
  `GeneratedFixture`, the drawer-strategy registry with the observation
  strategy, metric selection from the registry seed, naming transforms,
  timestamp encodings; tests in `tests/test_fixture_gen.py`: determinism
  (same seed → identical bytes; different seeds → different fixtures),
  challenge invariants present, unknown drawer fails loudly, no real-vendor
  source names.
- **WP2 — validation + writer + adapter (FR-4, FR-5, FR-6).**
  `validate_fixture` with each invariant individually violated in tests,
  manifest-shape fidelity (parse the generated manifest with the same code
  path that reads the committed one), `write_fixture` overwrite refusal,
  `scenario_for` accepted by the harness, synthetic-recognition marker plus
  the real-path-stays-non-synthetic proof.
- **WP3 — CLI + doc sync (FR-7, NFR-3).** `_main()` with arg parsing and
  honest exit codes; CHANGELOG entry; ROADMAP/STATUS updated so the fixture
  auto-generator moves to shipped and the remaining deferred items (including
  the intake strategy and non-CSV formats) stay named.

One Opus implementation agent builds all three WPs in order on this branch,
test-first (`/tdd`), committing at each green checkpoint; an independent Opus
reviewer then verifies FR/NFR coverage and runs all four gates (`ruff check`,
`ruff format --check`, changed-scope `mypy`, full `pytest`).

## Acceptance

On `overnight/m5-fixture-auto-generator`: all four gates green; an end-to-end
test proves spec in → generated pair out → validated → written to a temp dir →
adapted to a `Scenario` the harness accepts, with byte-identical regeneration
from the same seed; with the generator never invoked, the existing live-trial
and fixture tests pass unchanged.
