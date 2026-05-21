# Contract: Engine Signal Registry

> Mission: `v2-architectural-skeleton-01KS4SHA`
> Phase 1 contract document
> Authoritative implementation location: `src/premura/engine/_registry.py` (defined in this mission) + `src/premura/engine/__init__.py` (re-exports + stub API).

## Purpose

Define the engine-side contract that Stage 2 signal functions register against, that MCP (Stage 3) queries for tool discovery, and that the ingest loader (Stage 1) may consult for auto-precompute decisions.

This contract is the **open boundary** of the engine — it's stable, public, and may be reimplemented by a closed-source `premura-engine-pro` package without breaking callers.

## Symbols

### `SignalSpec(frozen dataclass)` — defined in `src/premura/engine/_registry.py`

See [data-model.md](../data-model.md) §3 for the full field documentation. Recap:

| Field | Type | Default | Required at decoration time? |
|---|---|---|---|
| `name` | `str` | — | yes |
| `domain` | `list[str]` | — | yes |
| `inputs` | `list[str]` | — | yes |
| `output` | `str \| None` | `None` | no |
| `priority` | `str` | `"normal"` | no |
| `auto_safe` | `bool` | `False` | no |
| `revision` | `str` | `"1"` | no |
| `fn` | `Callable \| None` | `None` | populated by decorator |

### `REGISTRY: dict[str, SignalSpec]`

Module-level mutable dict, keyed by `SignalSpec.name`. Empty at import time. Mutated only by the `signal` decorator. Read by `compute`, `list_by_domain`, `list_auto_safe`, `list_unavailable`.

### `signal(**kwargs) -> Callable`

Decorator factory. Returns a decorator that:
1. Constructs a `SignalSpec` from the kwargs and the decorated function.
2. Stores it in `REGISTRY[spec.name]`.
3. Returns the function unchanged (so callers can still invoke it directly).

Mutability rule: re-registering the same `name` overwrites the previous entry. Stage 2 implementation missions must not register two signals with the same `name`; reviewers catch collisions at PR time.

## Engine module API (5 functions)

All five live in `src/premura/engine/__init__.py`. In this skeleton mission, all five raise `NotImplementedError("Stage 2 — see STAGES.md")`. Their semantics, as documented in docstrings + this contract, are the binding behavior contract for the implementation mission.

### `compute(spec_name: str, conn) -> object`

**Semantics**: Look up `REGISTRY[spec_name]`, call its `fn` with the DuckDB connection, return the result.

**Behavior**:
- Raises `KeyError` if `spec_name` not in `REGISTRY`.
- Raises `RuntimeError` if `spec.fn is None` (spec registered without a function body).
- May read `hp.fact_measurement`, `hp.fact_interval`, `hp.dim_metric` via `conn`.
- May write to `hp.fact_measurement` if `spec.output is not None`. The persisted row's `raw_payload` MUST include `{"signal_revision": spec.revision}` so a future `hpipe revalidate` can detect staleness.

**Skeleton behavior**: `raise NotImplementedError("Stage 2 — see STAGES.md")`.

### `list_by_domain(domain: str) -> list[SignalSpec]`

**Semantics**: Return all `SignalSpec`s in `REGISTRY` whose `domain` list contains the given `domain` string. Used by MCP's tool-exposure logic to discover relevant signals for a user-selected health direction.

**Behavior**:
- Empty list if no signals tag that domain (not an error).
- Order: implementation defines (sorted by `name` is a reasonable default).
- Does NOT filter by input-availability — that's `check_inputs_available` / `list_unavailable`.

**Skeleton behavior**: `raise NotImplementedError`.

### `list_auto_safe() -> list[SignalSpec]`

**Semantics**: Return all `SignalSpec`s where `auto_safe is True`. Used by the ingest loader's optional auto-precompute step (per [docs/UPDATE_STRATEGY.md](../../../docs/UPDATE_STRATEGY.md)).

**Behavior**: Empty list if no signals opted into auto-safe (not an error). Order: stable across calls, but specific order is implementation-defined.

**Skeleton behavior**: `raise NotImplementedError`.

### `check_inputs_available(inputs: list[str], conn, within: timedelta | None = None) -> bool`

**Semantics**: Return True if every `metric_id` in `inputs` has at least one measurement in the warehouse. If `within` is provided, restrict the check to measurements within `within` of "now" (according to the metric's `validity_window` from `hp.dim_metric` if the per-metric window is tighter than the global `within`).

**Behavior**:
- Returns False on the first missing input (short-circuit).
- May read `hp.fact_measurement`, `hp.fact_interval`, `hp.dim_metric`.
- If `within` is None: uses each metric's `validity_window` from `hp.dim_metric` if set, else treats the metric as never-stale.
- Empty `inputs` list returns True trivially (no inputs needed = "available").

**Skeleton behavior**: `raise NotImplementedError`.

### `list_unavailable(domain: str, conn) -> list[SignalSpec]`

**Semantics**: Return the subset of `list_by_domain(domain)` whose `inputs` are NOT all available per `check_inputs_available`. MCP uses this to build the `missing_inputs_report` it returns to Learn for user-facing "go get this lab" suggestions.

**Behavior**:
- Caller filters further by `priority` if they only want high-priority gaps.
- Empty list if all signals in the domain have their inputs (happy path).

**Skeleton behavior**: `raise NotImplementedError`.

## Execution modes

The engine operates in two modes; both are documented in `src/premura/engine/__init__.py` docstring:

### Mode A — On-demand (default, called from MCP)

```
MCP receives a tool invocation from the LLM
       │
       ▼
MCP calls engine.compute(spec_name, conn)
       │
       ▼
compute() looks up REGISTRY[spec_name], invokes spec.fn(conn)
       │
       ▼
fn() reads hp.fact_measurement, computes result
       │
       ├── if spec.output is None: returns the result to MCP transient
       │
       └── if spec.output is set: persists a row to hp.fact_measurement with
                                    metric_id = spec.output,
                                    raw_payload = {"signal_revision": spec.revision, ...}
                                  and returns the value to MCP.
       │
       ▼
MCP returns to caller (the LLM)
```

### Mode B — Auto-run at ingest time (opt-in via `auto_safe=True`)

```
hpipe ingest finishes parsing a new batch
       │
       ▼
Ingest loader calls engine.list_auto_safe()
       │
       ▼
For each spec returned:
       engine.check_inputs_available(spec.inputs, conn, within=batch_window)
         if True → engine.compute(spec.name, conn)
                     (which may persist depending on spec.output)
       │
       ▼
Ingest reports successful auto-runs in the structured log
(hp.ingest_run.notes field)
```

The skeleton does not implement Mode B's loader integration. It commits the `auto_safe` field and the `list_auto_safe` stub so the future loader update is mechanical.

## Layering enforcement (C-012)

The engine reads `hp.fact_measurement` directly. **`mcp/` and `learn/` MUST NOT**.

- `mcp/` calls `engine.list_by_domain`, `engine.check_inputs_available`, `engine.compute`. Never `conn.execute("SELECT ... FROM hp.fact_measurement")`.
- `learn/` calls `mcp.register_tools`. Never `engine.compute` directly; never reads DB.

The skeleton enforces this only via module docstrings (the docstrings of `mcp/__init__.py` and `learn/__init__.py` contain literal strings asserting these rules). A future import-graph linting step in CI may enforce it mechanically.

## What the skeleton ships vs. what implementation missions add

| Surface | Skeleton (this mission) | Future implementation mission |
|---|---|---|
| `SignalSpec` dataclass | ✅ Defined in `engine/_registry.py` | (no change) |
| `REGISTRY` dict | ✅ Defined as empty | Populated lazily by signal-module imports |
| `signal` decorator | ✅ Works | (no change) |
| `engine/__init__.py` re-exports + docstring | ✅ Shipped | (refinements possible) |
| 5 API stubs | ✅ All raise `NotImplementedError` | Each replaced by real implementation |
| Actual signal functions (e.g., `ast_alt_ratio`) | ❌ None | One or more Stage 2 missions add them |
| Persistence-vs-views policy | Per-signal `output` field (skeleton committed) | Each signal's body decides |
| Auto-run loader hook in `hpipe ingest` | ❌ Not wired | Future mission adds it; signature already committed via `list_auto_safe` |
| `hpipe revalidate` CLI verb | ❌ Out of scope (C-004) | "Update strategy" follow-up mission |
| `hpipe rebuild` CLI verb | ❌ Out of scope (C-004) | "Update strategy" follow-up mission |

## Acceptance tests this contract implies (covered by `tests/test_skeleton.py`)

- `from premura.engine import signal, SignalSpec, REGISTRY` succeeds; `REGISTRY == {}` at import (NFR-008, SC-008).
- A test decorates a no-op function with `@signal(name="t", domain=["x"], inputs=["a"], output=None)` and asserts `REGISTRY["t"].domain == ["x"]` etc.
- Each of the 5 API stubs raises `NotImplementedError` when called (FR-003).
- The engine `__init__.py` docstring contains the strings `"Stage 2"`, `"on-demand"`, `"auto-run"` (FR-001).
- The `SignalSpec.revision` default is `"1"` (FR-002 verification).
- `mcp/__init__.py` docstring contains `"never reads hp.fact_measurement directly"` (C-012 verification, FR-004).
- `learn/__init__.py` docstring contains `"never reads hp.fact_measurement or calls engine directly"` (C-012 verification, FR-005).

## Open questions deferred to implementation missions

1. **`SignalSpec.priority` semantics for ordering**: when MCP exposes multiple high-priority tools, do they appear in a specific order? Skeleton commits the field; ordering policy is deferred.

2. **Revision-comparison granularity**: when a signal's `revision` bumps from `"1"` to `"2"`, does `revalidate` walk every persisted `derived:*` row, or only rows tagged with `revision="1"`? Deferred to the update-strategy mission.

3. **Auto-run scheduling**: does the ingest loader run all `auto_safe` signals serially, in parallel, or in dependency order based on inputs/outputs? Deferred. Skeleton commits no scheduling contract.

4. **`compute` return type**: the stub signature is `-> object` for maximum flexibility. Should it be tightened to a specific return type (e.g., `SignalResult` with effect-size + CI + n)? Deferred; the existing return-everything contract is fine for skeleton purposes.
