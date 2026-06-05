# Contract — the alien intake source + ground-truth manifest

> Satisfies FR-002 / C-005. Synthetic and obviously fake; structurally unlike all four
> built-in sources **and** unlike the existing JSON intake fixtures.

## `alien_intake.csv` (the source artifact)

One CSV holding **both** meals and supplements, distinguished by a `kind` column. It is
deliberately foreign:

- **Foreign column names** unlike any built-in source — e.g. `logged_at_us`, `kind`,
  `item`, `qty`, `qty_uom`, `note`.
- **Timestamp as epoch microseconds** (`logged_at_us`) — not ISO-8601, not any built-in
  encoding. At least one row crosses **local midnight** so local-day ≠ UTC-date (mirrors
  the intake signals' temporal-basis edge case).
- **Mixed / non-SI units** in `qty_uom` the parser must map: e.g. `oz`, `Cal`, `IU`,
  `mcg`.
- **Coverage:** ≥ 1 nutrition row, ≥ 1 supplement row, the midnight-crossing row, and
  **≥ 1 column with no canonical home** (`note`) to exercise the declared-gap path.
- **No PHI.** Values are invented (NFR-004).

## `alien_intake_manifest.yaml` (grader-only ground truth)

Per source column: `source_column`, `drawer` (`intake`/`observation`), `canonical_home`
(or `null` for the intended gap), `expected_outcome` (`loaded`/`declared_gap`).

- At least one column has `expected_outcome: declared_gap` (the `note` column) → SC-004.
- The manifest is read **only** by the grader. It MUST NOT be copied into the sandbox
  tree, embedded in any operator prompt, or otherwise reachable by the operator (C-005).

## Reference intake parser (`reference_intake_parser.py`, layer 1)

The known-good operator for layer 1. It:

- maps the foreign columns to the intake batch (nutrition vs supplement by `kind`),
  converting `qty_uom` units and decoding `logged_at_us` to the intake event timestamp;
- routes everything to the **intake** drawer (never `hp.fact_*`);
- declares the unmappable `note` column as a gap (`unmapped_metrics` / `skipped_rows`),
  never silently dropping it;
- returns a `ParseOutput`/`IntakeBatch` that `validate()`s and persists without raising.

A full pass on this parser over the alien source is SC-001.
