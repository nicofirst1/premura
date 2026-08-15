# Issue matrix — substrate-unit-guarantees-01M01A8V

Per FR-037 of the spec-kitty-mission-review skill Gate-4. One row per issue referenced in spec.md.

| Issue | Title                                                                                           | Verdict                | Evidence ref                                                            |
| ----- | ----------------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------------------------------- |
| #113  | Unit enforcement missing at the load boundary: wrong-unit rows landed via unguarded write paths | fixed                  | Loader convert-or-refuse + vocabulary rail + ingest_skip shipped (f31225f, 8438c8e, 2270767); replay test writes zero rows |
| #111  | Fix blood glucose unit mismatch in MCP summaries                                                | fixed                  | Root cause closed at the load boundary; polluted-row cleanup mechanism shipped (028e075), execution documented post-merge |
| #114  | docling table extraction mangles test labels; rows silently dropped at metric resolution        | deferred-with-followup | Out of scope per spec.md C-004; issue #114 remains open as the followup |

Valid `Verdict` values: `fixed`, `verified-already-fixed`, `deferred-with-followup`, `in-mission` (being fixed by a later WP in this mission; must reach a terminal verdict before mission `done`).
