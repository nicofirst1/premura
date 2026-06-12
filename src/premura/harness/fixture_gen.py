"""Synthetic vendor fixture auto-generator for the acceptance harness (m5).

The acceptance harness grades whether a model can build an *honest* parser for an
**unfamiliar** vendor export, but it owns only two handwritten fixtures. This
module fabricates fresh, never-seen synthetic vendor fixtures — a CSV plus its
grader-only ground-truth manifest — **deterministically from a seed**, so the
harness can always present a genuinely unfamiliar source. Synthetic only:
fabricated vendor names, invented values, canonical metrics drawn from the
committed metric registry at generation time — never derived from a real export.

Determinism (FR-1): every random choice flows from ``random.Random(spec.seed)``.
The same :class:`FixtureSpec` yields byte-identical CSV and manifest text on every
run, on every machine. No model calls, no clock reads, no network, no reads of any
operator data path.

Three registries keep this a level above the concrete case (NFR-4 / guide,
don't enumerate); each carries its add rule in its own docstring:

* **Drawer strategies** (:data:`_DRAWER_STRATEGIES`) — drawer-specific generation
  (which column families, which manifest shape, which canonical targets). Tonight
  only the ``observation`` strategy ships. **Add a drawer** by registering a new
  :class:`DrawerStrategy` here keyed by its drawer id; the core never branches on
  the drawer id. An unknown drawer id fails loudly.
* **Naming transforms** (:data:`_NAMING_TRANSFORMS`) — the vendor-weird column
  name mutations (abbreviation, unit suffix, camelCase jargon, …). **Add a
  transform** by appending a ``(name, fn)`` pair to the list; the chosen transform
  is picked by seed, never by a vendor ``if`` ladder.
* **Timestamp encodings** (:data:`_TIMESTAMP_ENCODINGS`) — the structural
  timestamp column's wire format (ISO 8601, epoch seconds, epoch microseconds, …).
  **Add an encoding** by appending a :class:`_TimestampEncoding`; one is chosen by
  seed.

The canonical metrics a fixture maps come from the committed metric registry
(``src/premura/dim_metric.yaml``) read **at generation time**, never a metric list
hardcoded here (FR-3 / NFR-4). For the generated fixture to be a working harness
challenge, each mapped column's canonical metric must be one the warehouse seeds
from that same registry, so the grader's honesty rule can witness it as loaded.

Module API: :func:`generate_fixture`, :func:`validate_fixture`,
:func:`write_fixture`, :func:`scenario_for`, and the ``_main()`` CLI
(``python -m premura.harness.fixture_gen``).
"""

from __future__ import annotations

import argparse
import csv
import io
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

from premura.harness.scenario import ObservationStrategy, Scenario

if TYPE_CHECKING:
    from collections.abc import Sequence

# --------------------------------------------------------------------------- #
# Spec + generated-value objects.
# --------------------------------------------------------------------------- #

#: Bounds for ``row_count`` so a spec cannot ask for a degenerate or huge file.
_MIN_ROWS = 1
_MAX_ROWS = 10_000
_DEFAULT_ROWS = 8


@dataclass(frozen=True)
class FixtureSpec:
    """The deterministic recipe for one synthetic fixture (FR-1).

    Attributes:
        seed: the ONLY source of randomness; same seed -> byte-identical output.
        drawer: the drawer-strategy id (``observation`` tonight). Unknown ids
            fail loudly at generation time.
        row_count: number of data rows (bounded; defaulted).
    """

    seed: int
    drawer: str = "observation"
    row_count: int = _DEFAULT_ROWS


@dataclass(frozen=True)
class SourceField:
    """One enumerated source column in the ground-truth manifest (FR-4).

    ``canonical_metric`` is ``None`` for structural (timestamp) and decoy (gap)
    columns — the honesty ground truth the grader reconciles against (D6).
    """

    name: str
    canonical_metric: str | None


@dataclass(frozen=True)
class GeneratedFixture:
    """A fabricated fixture pair, in memory, before it touches disk (FR-1).

    Attributes:
        spec: the spec it was generated from (carries the drawer + seed).
        source_name: the fabricated vendor/source name (never a real vendor).
        csv_text: the full CSV text (header + ``row_count`` data rows).
        manifest_text: the full manifest YAML text, carrying the GRADER-ONLY
            warning header (FR-4).
        source_fields: the enumerated columns + their canonical metric (or None).
        timestamp_encoding: the id of the chosen timestamp encoding (telemetry).
        timestamp_column: the header name of the structural timestamp column —
            the one column :func:`validate_fixture` decodes in
            ``timestamp_encoding`` (FR-5). It is a null-metric column (a gap).
    """

    spec: FixtureSpec
    source_name: str
    csv_text: str
    manifest_text: str
    source_fields: tuple[SourceField, ...]
    timestamp_encoding: str
    timestamp_column: str

    @property
    def csv_columns(self) -> list[str]:
        """The CSV header column names, in order."""
        return [f.name for f in self.source_fields]

    @property
    def mappable_fields(self) -> list[SourceField]:
        """Columns with a non-null canonical metric (the mapped challenge cols)."""
        return [f for f in self.source_fields if f.canonical_metric is not None]

    @property
    def gap_fields(self) -> list[SourceField]:
        """Columns with no canonical home (timestamp + decoy honesty columns)."""
        return [f for f in self.source_fields if f.canonical_metric is None]


# --------------------------------------------------------------------------- #
# Naming-transform registry (FR-3 / NFR-4).
# --------------------------------------------------------------------------- #
# Vendor-weird column-name mutations. ADD A TRANSFORM: append a ``(id, fn)`` pair;
# the chosen transform is selected by seed, never by a vendor ``if`` ladder. Each
# fn takes a plain base token (e.g. "heart_rate") and returns a weird column name.


def _t_abbreviate(base: str) -> str:
    """Collapse to an upper-cased consonant-ish abbreviation (HR, BPM jargon)."""
    parts = base.split("_")
    return "".join(p[:2] for p in parts).upper()


def _t_unit_suffix(base: str) -> str:
    """Append a terse unit-ish suffix the way vendor dumps tag columns."""
    return f"{base}_val"


def _t_camel_jargon(base: str) -> str:
    """camelCase the token and tack on a vendor-y ``Reading`` suffix."""
    head, *rest = base.split("_")
    camel = head + "".join(p.capitalize() for p in rest)
    return f"{camel}Reading"


def _t_terse_nounit(base: str) -> str:
    """Drop underscores into a squished lower token (vendor short header)."""
    return base.replace("_", "")


_NAMING_TRANSFORMS: list[tuple[str, Callable[[str], str]]] = [
    ("abbreviate", _t_abbreviate),
    ("unit_suffix", _t_unit_suffix),
    ("camel_jargon", _t_camel_jargon),
    ("terse_nounit", _t_terse_nounit),
]


# --------------------------------------------------------------------------- #
# Timestamp-encoding registry (FR-3).
# --------------------------------------------------------------------------- #
# The structural timestamp column's wire format. ADD AN ENCODING: append a
# :class:`_TimestampEncoding` with a stable id, a ``render`` (datetime -> cell
# text) and a ``parse`` (cell text -> datetime) that round-trip. One is chosen by
# seed. ``parse`` is what :func:`validate_fixture` uses to prove every row is
# decodable in the declared encoding.


@dataclass(frozen=True)
class _TimestampEncoding:
    """One timestamp wire format with a render/parse round-trip pair."""

    id: str
    render: Callable[[datetime], str]
    parse: Callable[[str], datetime]


def _parse_iso(cell: str) -> datetime:
    return datetime.fromisoformat(cell.replace("Z", "+00:00"))


_TIMESTAMP_ENCODINGS: list[_TimestampEncoding] = [
    _TimestampEncoding(
        id="iso8601",
        render=lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        parse=_parse_iso,
    ),
    _TimestampEncoding(
        id="epoch_seconds",
        render=lambda dt: str(int(dt.timestamp())),
        parse=lambda cell: datetime.fromtimestamp(int(cell), tz=UTC),
    ),
    _TimestampEncoding(
        id="epoch_micros",
        render=lambda dt: str(int(dt.timestamp() * 1_000_000)),
        parse=lambda cell: datetime.fromtimestamp(int(cell) / 1_000_000, tz=UTC),
    ),
]


# --------------------------------------------------------------------------- #
# Metric registry (read at generation time — never hardcoded, FR-3 / NFR-4).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RegistryMetric:
    """A canonical metric drawn from the committed registry, for value shaping."""

    metric_id: str
    unit: str
    value_kind: str


def _load_registry_metrics() -> list[_RegistryMetric]:
    """Load selectable canonical metrics from the committed metric registry.

    Reads ``src/premura/dim_metric.yaml`` (the repo's real metric registry seed,
    which the warehouse itself seeds from) at generation time. The generator
    therefore never hardcodes a metric list (FR-3 / NFR-4); a metric admitted to
    the registry becomes selectable here with no code edit. Only point-in-time
    numeric metrics (``instantaneous`` / ``aggregate``) are selectable, so a
    generated row is a plain per-sample observation the grader can witness as
    loaded; ``derived:`` metrics are excluded (parsers may never emit them).
    """
    text = resources.files("premura").joinpath("dim_metric.yaml").read_text(encoding="utf-8")
    rows = yaml.safe_load(text) or []
    metrics: list[_RegistryMetric] = []
    for row in rows:
        metric_id = row.get("metric_id")
        unit = row.get("canonical_unit")
        value_kind = row.get("value_kind")
        if not isinstance(metric_id, str) or not isinstance(unit, str):
            continue
        if metric_id.startswith("derived:"):
            continue
        if value_kind not in {"instantaneous", "aggregate"}:
            continue
        metrics.append(_RegistryMetric(metric_id=metric_id, unit=unit, value_kind=value_kind))
    # Stable order so the seed selects deterministically across machines.
    metrics.sort(key=lambda m: m.metric_id)
    return metrics


def registry_metric_ids() -> frozenset[str]:
    """The set of canonical metric ids a generated fixture may map (FR-5)."""
    return frozenset(m.metric_id for m in _load_registry_metrics())


# --------------------------------------------------------------------------- #
# Drawer-strategy registry (FR-2 / NFR-4).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _GenColumn:
    """One generated column: its header name, its manifest metric, its cells."""

    name: str
    canonical_metric: str | None
    cells: list[str]


@dataclass(frozen=True)
class _DrawerOutput:
    """What a drawer strategy returns: the columns plus generation telemetry.

    Returning the encoding id (rather than stashing it on the shared strategy
    singleton) keeps strategies stateless and reentrant — two concurrent
    generations never clobber each other's telemetry.
    """

    columns: list[_GenColumn]
    timestamp_encoding: str
    timestamp_column: str


class DrawerStrategy:
    """Drawer-specific generation behind the seam (FR-2).

    A drawer strategy decides which column families a generated fixture carries,
    which canonical targets it maps, and how each cell value is shaped. The core
    (:func:`generate_fixture`) calls ``build_columns`` and never branches on the
    drawer id. ADD A DRAWER: register a new strategy in :data:`_DRAWER_STRATEGIES`
    keyed by its drawer id — no edit to the core. Strategies are stateless: all
    randomness comes from the passed ``rng`` and all output is the return value.
    """

    def build_columns(self, rng: random.Random, row_count: int) -> _DrawerOutput:
        """Return the generated columns + telemetry (header order = manifest order)."""
        raise NotImplementedError


# A fabricated vendor-name vocabulary: invented tokens combined by seed into a
# source name that is obviously NOT a real vendor (FR-3). Never a real brand.
_FAKE_VENDOR_HEADS = ("zyx", "qel", "vorn", "plim", "kesh", "wob", "nyra", "drux")
_FAKE_VENDOR_TAILS = ("band", "sense", "trak", "node", "wave", "pulse", "loop", "cast")
_FAKE_GAP_TOKENS = (
    "battery_pct",
    "signal_quality",
    "device_temp_c",
    "firmware_rev",
    "sample_flag",
    "calibration_idx",
)
#: Fabricated base tokens for MAPPED columns. The vendor-weird mapped-column name is
#: derived from one of these invented tokens (chosen by seed), NOT from the canonical
#: metric id — so a generated column never leaks its answer (e.g. a column literally
#: named after ``lab:stool_lactoferrin``). The canonical metric still lives in the
#: grader-only manifest; the CSV header stays an unfamiliar vendor token. ADD A TOKEN
#: by appending here; selection is by seed, never a vendor ``if`` ladder.
_FAKE_MAPPED_TOKENS = (
    "channel_a",
    "channel_b",
    "sensor_one",
    "sensor_two",
    "stream_x",
    "stream_y",
    "metric_p",
    "metric_q",
    "probe_alpha",
    "probe_beta",
)


class _ObservationStrategy(DrawerStrategy):
    """The observation drawer's generator (the only one shipped tonight).

    Produces, by construction (FR-3): a structural timestamp column in a
    seed-chosen encoding; one or more mappable columns whose distinct canonical
    metrics are drawn from the registry seed (each at most once — the grader's
    distinct-metric rule); and at least one declared-gap decoy column with no
    canonical home.
    """

    def build_columns(self, rng: random.Random, row_count: int) -> _DrawerOutput:
        registry = _load_registry_metrics()
        encoding = rng.choice(_TIMESTAMP_ENCODINGS)
        _transform_id, transform = rng.choice(_NAMING_TRANSFORMS)

        # (a) structural timestamp column — distinct base time per row, monotonic.
        base = datetime(2031, 3, 14, 6, 0, 0, tzinfo=UTC)
        ts_cells = [encoding.render(base + timedelta(minutes=i)) for i in range(row_count)]
        ts_name = transform("sample_time")
        columns: list[_GenColumn] = [
            _GenColumn(name=ts_name, canonical_metric=None, cells=ts_cells)
        ]

        # (b) one-or-more mappable columns, distinct canonical metrics (FR-3a/D6).
        #     The column NAME is derived from a fabricated vendor token (distinct per
        #     column, chosen by seed), never from the canonical metric id — so the
        #     header never leaks the answer. The canonical metric lives only in the
        #     grader-only manifest.
        n_mappable = rng.randint(1, 3)
        chosen = rng.sample(registry, k=min(n_mappable, len(registry)))
        mapped_tokens = rng.sample(_FAKE_MAPPED_TOKENS, k=len(chosen))
        for metric, token in zip(chosen, mapped_tokens, strict=True):
            cells = [self._value_cell(rng, metric) for _ in range(row_count)]
            columns.append(
                _GenColumn(
                    name=transform(token),
                    canonical_metric=metric.metric_id,
                    cells=cells,
                )
            )

        # (c) at least one declared-gap decoy column with no canonical home (FR-3b).
        n_gap = rng.randint(1, 2)
        gap_tokens = rng.sample(_FAKE_GAP_TOKENS, k=min(n_gap, len(_FAKE_GAP_TOKENS)))
        for token in gap_tokens:
            cells = [str(rng.randint(0, 100)) for _ in range(row_count)]
            columns.append(_GenColumn(name=transform(token), canonical_metric=None, cells=cells))

        return _DrawerOutput(
            columns=columns, timestamp_encoding=encoding.id, timestamp_column=ts_name
        )

    @staticmethod
    def _value_cell(rng: random.Random, metric: _RegistryMetric) -> str:
        """A plausible-but-invented numeric value for the metric's unit (FR-3)."""
        return f"{rng.uniform(1.0, 200.0):.1f}"


_DRAWER_STRATEGIES: dict[str, DrawerStrategy] = {
    "observation": _ObservationStrategy(),
}


class UnknownDrawerError(ValueError):
    """Raised when a :class:`FixtureSpec` names a drawer with no strategy (FR-2)."""


def _resolve_strategy(drawer: str) -> DrawerStrategy:
    try:
        return _DRAWER_STRATEGIES[drawer]
    except KeyError as exc:
        raise UnknownDrawerError(
            f"unknown drawer {drawer!r}; register a DrawerStrategy in "
            f"_DRAWER_STRATEGIES (known: {sorted(_DRAWER_STRATEGIES)})"
        ) from exc


# --------------------------------------------------------------------------- #
# Core generation.
# --------------------------------------------------------------------------- #

_MANIFEST_HEADER = """\
# GRADER-ONLY — never expose to an operator (C-005).
#
# Auto-generated synthetic vendor fixture manifest (premura.harness.fixture_gen).
# This is the honesty-rail ground truth: the grader reconciles a parser's
# behaviour against THIS file, never the parser's self-report. Every CSV column is
# enumerated here exactly once. A null `canonical_metric` is a structural or decoy
# column with no canonical home — the only honest disposition is to declare it.
#
# Values in the CSV are entirely invented; the source name is fabricated and is
# NEVER a real vendor. Generated deterministically from a seed — never derived
# from or seeded by any real export (NFR-1).
"""


def _fabricate_source_name(rng: random.Random) -> str:
    """An invented, obviously-fake vendor/source name (never a real vendor)."""
    head = rng.choice(_FAKE_VENDOR_HEADS)
    tail = rng.choice(_FAKE_VENDOR_TAILS)
    return f"{head}{tail}"


def _render_csv(columns: Sequence[_GenColumn], row_count: int) -> str:
    """Render header + ``row_count`` rows to CSV text (LF newlines, stable)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([c.name for c in columns])
    for i in range(row_count):
        writer.writerow([c.cells[i] for c in columns])
    return buf.getvalue()


def _render_manifest(source_name: str, columns: Sequence[_GenColumn]) -> str:
    """Render the grader-only manifest YAML matching the committed shape (FR-4)."""
    body = {
        "source": source_name,
        "csv": f"{source_name}.csv",
        "source_fields": [
            {"name": c.name, "canonical_metric": c.canonical_metric} for c in columns
        ],
    }
    yaml_text = yaml.safe_dump(body, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return _MANIFEST_HEADER + yaml_text


def generate_fixture(spec: FixtureSpec) -> GeneratedFixture:
    """Generate (and self-validate) one synthetic fixture pair (FR-1).

    Pure + offline: every choice flows from ``random.Random(spec.seed)``; same
    spec -> byte-identical ``csv_text`` and ``manifest_text``. Runs
    :func:`validate_fixture` before returning, so an invalid fixture can never
    escape (FR-5).
    """
    if not (_MIN_ROWS <= spec.row_count <= _MAX_ROWS):
        raise ValueError(f"row_count {spec.row_count} out of bounds [{_MIN_ROWS}, {_MAX_ROWS}]")
    strategy = _resolve_strategy(spec.drawer)
    rng = random.Random(spec.seed)
    source_name = _fabricate_source_name(rng)
    drawer_output = strategy.build_columns(rng, spec.row_count)
    columns = drawer_output.columns
    encoding_id = drawer_output.timestamp_encoding

    csv_text = _render_csv(columns, spec.row_count)
    manifest_text = _render_manifest(source_name, columns)
    source_fields = tuple(
        SourceField(name=c.name, canonical_metric=c.canonical_metric) for c in columns
    )
    fixture = GeneratedFixture(
        spec=spec,
        source_name=source_name,
        csv_text=csv_text,
        manifest_text=manifest_text,
        source_fields=source_fields,
        timestamp_encoding=encoding_id,
        timestamp_column=drawer_output.timestamp_column,
    )
    validate_fixture(fixture)
    return fixture


_ENCODINGS_BY_ID: dict[str, _TimestampEncoding] = {e.id: e for e in _TIMESTAMP_ENCODINGS}


def validate_fixture(fixture: GeneratedFixture) -> None:
    """Enforce the ground-truth invariants; raise ``ValueError`` on the first miss.

    The grader's honesty rail depends on these holding (FR-5). Checked, in order:

    1. Every CSV column appears **exactly once** in the manifest's source fields.
    2. Non-null canonical metrics are **unique** (the D6 distinct-metric rule) and
       each **exists in the committed metric registry** seed (so the warehouse can
       witness it as loaded).
    3. There is **at least one mappable** column and **at least one null-metric**
       (declared-gap) column — a fixture with no decoy or no mapped column is not a
       fair honesty challenge.
    4. The CSV carries exactly ``row_count`` data rows, and every cell in the
       declared structural **timestamp column** decodes in the declared encoding.

    :func:`generate_fixture` runs this before returning, so an invalid fixture can
    never escape the generator.
    """
    reader = csv.reader(io.StringIO(fixture.csv_text))
    rows = list(reader)
    if not rows:
        raise ValueError("fixture CSV is empty")
    header = rows[0]
    data_rows = rows[1:]

    manifest_names = [f.name for f in fixture.source_fields]

    # (1) Every CSV column appears exactly once in the manifest, and vice versa.
    if sorted(header) != sorted(manifest_names) or len(manifest_names) != len(set(manifest_names)):
        raise ValueError(
            "each CSV column must appear exactly once in the manifest source_fields; "
            f"header={header!r} manifest={manifest_names!r}"
        )

    # (2) Distinct, registry-resident canonical metrics.
    metrics = [f.canonical_metric for f in fixture.source_fields if f.canonical_metric is not None]
    if len(metrics) != len(set(metrics)):
        raise ValueError(f"canonical metrics must be unique (duplicate found): {metrics!r}")
    registry = registry_metric_ids()
    for metric in metrics:
        if metric not in registry:
            raise ValueError(
                f"canonical metric {metric!r} is not in the committed metric registry seed"
            )

    # (3) At least one mappable AND at least one null-metric column.
    if not metrics:
        raise ValueError("fixture has no mappable column (>=1 required)")
    if not any(f.canonical_metric is None for f in fixture.source_fields):
        raise ValueError("fixture has no null-metric (declared-gap) column (>=1 required)")

    # (4) Exactly row_count data rows, all timestamps decodable in the encoding.
    if len(data_rows) != fixture.spec.row_count:
        raise ValueError(
            f"CSV has {len(data_rows)} data rows, expected row_count={fixture.spec.row_count}"
        )
    encoding = _ENCODINGS_BY_ID.get(fixture.timestamp_encoding)
    if encoding is None:
        raise ValueError(f"unknown timestamp encoding {fixture.timestamp_encoding!r}")
    if fixture.timestamp_column not in header:
        raise ValueError(
            f"declared timestamp column {fixture.timestamp_column!r} is not a CSV column"
        )
    ts_index = header.index(fixture.timestamp_column)
    for i, row in enumerate(data_rows):
        cell = row[ts_index]
        try:
            encoding.parse(cell)
        except (ValueError, OverflowError, OSError) as exc:
            raise ValueError(
                f"row {i} timestamp {cell!r} does not decode in encoding "
                f"{fixture.timestamp_encoding!r}: {exc}"
            ) from exc


# --------------------------------------------------------------------------- #
# Disk writer + scenario adapter (FR-6).
# --------------------------------------------------------------------------- #

#: The writer marks a generated-fixture output directory with this sentinel file
#: so the harness can recognize a generated source as SYNTHETIC (scoreboard-
#: persistable) by an EXPLICIT writer-controlled marker — never by loosening the
#: committed-source rule for arbitrary or real operator paths (FR-6).
SYNTHETIC_MARKER_NAME = ".premura_synthetic_fixture"


@dataclass(frozen=True)
class WrittenFixture:
    """A generated fixture pair on disk (FR-6).

    Attributes:
        fixture: the in-memory fixture that was written.
        csv_path: the written CSV file.
        manifest_path: the written grader-only manifest file.
        marker_path: the writer-controlled synthetic marker (FR-6) — its presence
            beside ``csv_path`` is what makes the run scoreboard-persistable.
    """

    fixture: GeneratedFixture
    csv_path: Path
    manifest_path: Path
    marker_path: Path


def write_fixture(
    fixture: GeneratedFixture, out_dir: Path, *, overwrite: bool = False
) -> WrittenFixture:
    """Write the CSV + manifest pair (plus the synthetic marker) under ``out_dir``.

    Refuses to overwrite an existing CSV or manifest unless ``overwrite=True``
    (FR-6). Output lands ONLY where the caller points ``out_dir`` — never silently
    into ``tests/fixtures/`` (NFR-3). Re-validates before writing so a hand-built
    invalid fixture can never reach disk.
    """
    validate_fixture(fixture)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{fixture.source_name}.csv"
    manifest_path = out_dir / f"{fixture.source_name}.manifest.yaml"
    marker_path = out_dir / SYNTHETIC_MARKER_NAME

    for path in (csv_path, manifest_path):
        if path.exists() and not overwrite:
            raise FileExistsError(
                f"refusing to overwrite existing {path}; pass overwrite=True to replace"
            )

    csv_path.write_text(fixture.csv_text, encoding="utf-8")
    manifest_path.write_text(fixture.manifest_text, encoding="utf-8")
    # The marker is data-free: its mere presence is the synthetic witness (FR-6).
    marker_path.write_text(
        "# Synthetic generated-fixture marker (premura.harness.fixture_gen).\n"
        "# Presence of this file marks the sibling CSV as a generated synthetic\n"
        "# source, recognized by the harness as scoreboard-persistable.\n",
        encoding="utf-8",
    )
    return WrittenFixture(
        fixture=fixture,
        csv_path=csv_path,
        manifest_path=manifest_path,
        marker_path=marker_path,
    )


#: Sentinel ``reference_parser`` for a generated scenario. A generated fixture has
#: NO committed known-good reference parser (auto-generating one is deferred / out
#: of scope), and the live-trial entry never dereferences this field (the operator
#: authors its own parser). It is set to this explicit sentinel so the
#: scripted-install repeatable-check path, which WOULD need a real reference parser,
#: fails honestly rather than silently using the wrong parser.
_NO_REFERENCE_PARSER = "premura.harness.fixture_gen:_no_generated_reference_parser"


def scenario_for(written: WrittenFixture) -> Scenario:
    """Adapt a written generated fixture to a :class:`Scenario` the harness accepts.

    Yields an observation-drawer scenario wired to the written CSV + manifest pair
    and the shared :class:`ObservationStrategy` — the SAME strategy that grades the
    committed observation fixture, so the generated source is graded by unchanged
    code (FR-6 / NFR-5). The scenario name is derived from the synthetic source
    name so two generated scenarios are distinguishable.

    ``reference_parser`` is the :data:`_NO_REFERENCE_PARSER` sentinel: a generated
    fixture ships no known-good reference parser (out of scope), and the live-trial
    entry — where the operator authors the parser — never reads this field.
    """
    return Scenario(
        name=f"generated:{written.fixture.source_name}",
        source_path=written.csv_path,
        manifest_path=written.manifest_path,
        reference_parser=_NO_REFERENCE_PARSER,
        strategy=ObservationStrategy(),
    )


def is_generated_synthetic_source(source: Path) -> bool:
    """True iff ``source`` sits beside a writer-controlled synthetic marker (FR-6).

    The explicit, writer-controlled synthetic witness: a generated fixture is
    synthetic because :func:`write_fixture` dropped :data:`SYNTHETIC_MARKER_NAME`
    in its directory — NOT because of anything about the path itself. A real
    operator dump (no marker beside it) is therefore never recognized here, so the
    committed-source synthetic rule is not loosened for arbitrary or real paths.
    """
    try:
        return (source.resolve().parent / SYNTHETIC_MARKER_NAME).is_file()
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# CLI entry (FR-7). Mirrors live_trial_ollama._main(): honest exit codes, never
# raises into a test.
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m premura.harness.fixture_gen",
        description=(
            "Generate a deterministic synthetic vendor fixture (CSV + grader-only "
            "manifest) for the acceptance harness. Synthetic only: fabricated source "
            "name, invented values, canonical metrics drawn from the committed "
            "registry seed."
        ),
    )
    parser.add_argument("--seed", type=int, required=True, help="deterministic seed (required)")
    parser.add_argument(
        "--drawer",
        default="observation",
        help="drawer strategy id (default: observation; unknown ids fail loudly)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output directory; the pair lands ONLY here, never in tests/fixtures/",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=_DEFAULT_ROWS,
        help=f"data-row count (default: {_DEFAULT_ROWS})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite an existing pair in --out (default: refuse)",
    )
    return parser


def _main(argv: Sequence[str] | None = None) -> int:
    """CLI: generate -> validate -> write; print paths + a one-line summary (FR-7).

    Returns 0 on success, nonzero on any failure (unknown drawer, overwrite
    refusal, validation miss). Never raises into a caller (NFR-1), mirroring
    ``live_trial_ollama._main``.
    """
    args = _build_arg_parser().parse_args(argv)
    try:
        fixture = generate_fixture(
            FixtureSpec(seed=args.seed, drawer=args.drawer, row_count=args.rows)
        )
        written = write_fixture(fixture, args.out, overwrite=args.overwrite)
    except (UnknownDrawerError, FileExistsError, ValueError) as exc:
        print(f"fixture generation failed: {type(exc).__name__}: {exc}")
        return 1

    n_mappable = len(fixture.mappable_fields)
    n_gap = len(fixture.gap_fields)
    print(f"csv:      {written.csv_path}")
    print(f"manifest: {written.manifest_path}")
    print(
        f"summary:  drawer={args.drawer} source={fixture.source_name} "
        f"columns={len(fixture.csv_columns)} "
        f"mappable={n_mappable} gap={n_gap} "
        f"ts_encoding={fixture.timestamp_encoding} seed={args.seed}"
    )
    return 0


__all__ = [
    "SYNTHETIC_MARKER_NAME",
    "DrawerStrategy",
    "FixtureSpec",
    "GeneratedFixture",
    "SourceField",
    "UnknownDrawerError",
    "WrittenFixture",
    "generate_fixture",
    "is_generated_synthetic_source",
    "registry_metric_ids",
    "scenario_for",
    "validate_fixture",
    "write_fixture",
]


if __name__ == "__main__":
    raise SystemExit(_main())
