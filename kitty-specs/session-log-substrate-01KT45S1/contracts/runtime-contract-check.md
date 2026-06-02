# Contract: runtime contract checker (`premura.parsers.contract_check`)

The minimal runtime-valid checker that **does not exist today** (FR-050). A pure
function over **captured evidence** so the grader can recompute, never trust
(FR-061).

```python
@dataclass(slots=True)
class ContractCheckResult:
    runtime_valid: bool
    violations: list[str]          # "<clause>: <detail>", sorted

def check_runtime_contract(
    *,
    declared_metrics: list[str],
    emitted_metric_ids: list[str],
    warehouse_conn: duckdb.DuckDBPyConnection,   # sandbox warehouse (boundary truth)
    ingest_run_ok: bool,                         # the ingest_run step status
) -> ContractCheckResult: ...
```

## Clauses recomputed (the runtime-valid subset only)

1. `no_derived_emitted` — no `emitted_metric_ids` entry starts with `derived:`
   (mirrors `base.py:387`, recomputed from captured emitted set).
2. `declared_equals_emitted` — `set(declared_metrics) == set(emitted_metric_ids)`.
3. `declared_exist_in_dim_metric` — every declared metric present in
   `hp.dim_metric` (mirrors `loader.validate_batch_against_warehouse`, recomputed
   against the sandbox warehouse).
4. `produced_batch_without_raising` — `ingest_run_ok` is true.

## Out of scope (reviewer checklist, not runtime — `CONTRACT.md` §Reviewer checklist ~line 116)

- decision-tree / standards-first order followed (needs a per-field resolution
  map — deferred);
- fixture-driven test present; PR note per unmapped/skipped field; same-PR
  ontology diff; clinically-standard aliases.

`contract_pass` written to `log_ingest_provenance` = this function's
`runtime_valid` as computed **by the grader** on captured evidence (FR-065).
