# Contract: self-reconciliation gate (FR-003 / C-005)

The manifest-blind, runtime-faithful honesty gate used **inside** the operator
retry loop. It is the answer-key-free twin of `grader.honest_about_gaps`.

## Surface

```
self_reconcile(source_path, batch) -> SelfReconciliationResult
```

- **`source_columns`** are read from the **source file's header/structure**
  (e.g. CSV header row) — the full ground set — NOT from whatever columns the
  parser happened to inspect. (Closes the "lazy parser skips a column" loophole.)
- A column is **accounted** iff it is the source field of a declared/emitted
  metric OR appears in `batch.unmapped_metrics` / `batch.skipped_rows`.
- `passed` iff `source_columns ⊆ accounted`; `unaccounted` is the sorted
  difference, fed back to the operator verbatim on failure.

## Invariants

- MUST NOT read, import, or accept the fixture manifest (`fixture_fields.yaml`) or
  any ground-truth mapping. Input is only the source artifact + the parser's own
  batch.
- MUST be pure and deterministic (same inputs ⇒ same result); no network, no
  session-log writes.
- Equivalence intent: on the committed fixture, a batch that passes
  `self_reconcile` MUST also pass the grader's `honest_about_gaps` rule (the two
  compute the same silent-drop check from header vs manifest). This is asserted by
  a default-collected test.

## Non-goals

- Does NOT check mapping *correctness* (whether `bpm→heart_rate` is right). That
  residual is judged only by the independent grader and is a legitimate
  capability-floor finding, never a loop failure.
