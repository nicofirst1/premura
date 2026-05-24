# 04 — Current Stage 2 Seam + Baseline-Profile Dependency

> Mission: `grounded-extensible-engine-research-01KSD0D1` · WP04 · supports FR-006, FR-007
> Purpose: audit the Stage 2 signal-engine seam that **already exists in code**, element by element, and decide for each whether the contribution model should **keep / change / defer** it — then make the **baseline personal profile** dependency explicit and route it to issue [#6](https://github.com/nicofirst1/premura/issues/6) instead of solving it here.

This document stays at the **contract level** — what each seam element promises a caller or a contributor — not at code-design level. It builds on the WP01 baseline (`research/01-repo-baseline.md`) and reuses its vocabulary: *signal*, *derived signal*, *engine function* ("a registered Stage 2 signal function"), *health direction* (the user-facing routing area, kept distinct from a signal's `domain` tag), and *contribution contract* ("the package a contributor must hand in to add a new engine function").

Every top-level claim carries an inline reference to repo source or to issue #6. Where WP01 already settled something, this WP cites WP01 rather than re-deriving it.

---

## How to read this document

- **§1 Seam audit (T014)** — an inventory of the seam elements that *actually exist today* in `src/premura/engine/` and the architecture docs. Nothing aspirational.
- **§2 Keep / Change / Defer (T015)** — exactly one disposition per element, one sentence of rationale, contract-level only.
- **§3 Baseline-profile dependency (T016)** — which stable personal attributes early engine functions will need, and why they do not fit the ordinary observed-measurement model.
- **§4 Connect to issue #6 (T017)** — what stays unresolved about storing/updating that data, and how later implementation work should behave until #6 is decided.

What this WP does **not** do: design the contribution contract (WP03), pick the quick-win functions (WP05), or decide where profile data is stored (issue #6). It only dispositions the existing seam and names the profile dependency.

---

## 1. Seam audit — the Stage 2 elements that already exist (T014)

The Stage 2 engine ships today as an **open boundary**: importing `premura.engine` registers no signals; the registry is empty until a signal module opts in, so a proprietary engine could reimplement the boundary without breaking callers (`src/premura/engine/__init__.py` module docstring; WP01 Stable Commitment 4). The inventory below lists the contract-level elements a future *contribution contract* would either inherit or revise.

### 1.1 `SignalSpec` — the registration record

A frozen dataclass that is the entire data shape a signal function registers against (`src/premura/engine/_registry.py` `SignalSpec`). Its fields, at contract level:

| Field | Contract meaning (from the field docstrings) |
|---|---|
| `name` | Unique snake_case identifier within the registry; re-registering the same name overwrites the prior entry (`_registry.py` `SignalSpec.name`, `signal` docstring). |
| `domain` | One or more **domain tags** the signal serves (e.g. `["liver", "blood"]`); consumed by `list_by_domain` discovery. A domain tag is narrower than a user-facing *health direction* (WP01 terminology table). |
| `inputs` | The canonical `metric_id`s the signal reads (e.g. `["lab:ast", "lab:alt"]`) — the contract used by the availability checks. |
| `output` | The canonical `metric_id` the signal produces, or `None` for transient output; when set it **must** start with `derived:` (`_registry.py` `SignalSpec.output`; WP01 Stable Commitment 6). |
| `priority` | `high` / `normal` / `low`; only `high`-priority signals get their missing-input gaps surfaced to the user (`_registry.py` `SignalSpec.priority`). |
| `auto_safe` | Opt-in flag marking a derivation conservative enough for a future auto-precompute-on-ingest flow; defaults `False` (`_registry.py` `SignalSpec.auto_safe`). |
| `revision` | A string bumped when derivation logic materially changes; stamped into each persisted `derived:` row so a future `hpipe revalidate` can find stale outputs (`_registry.py` `SignalSpec.revision`; `docs/architecture/UPDATE_STRATEGY.md` §(d)). |
| `fn` | The actual function, set by the `@signal(...)` decorator; `None` means declared without a body (`_registry.py` `SignalSpec.fn`). |

### 1.2 The registry model — `REGISTRY` + the `@signal(...)` decorator

`REGISTRY` is a module-level `dict[str, SignalSpec]`, empty at import time and populated when a signal module is imported and its `@signal(...)` decorators run (`src/premura/engine/_registry.py` `REGISTRY`, `signal`). The decorator takes the keyword fields above, builds a `SignalSpec`, and stores it under `name`; collisions silently overwrite and are expected to be caught by reviewers at PR time (`_registry.py` `signal` docstring). The three built-in lab ratios are loaded lazily — `_ensure_builtin_signals_loaded()` imports `premura.engine.lab_ratios` and calls `register_builtin_signals()` only when a query or compute helper first needs them (`src/premura/engine/__init__.py` `_ensure_builtin_signals_loaded`; `src/premura/engine/lab_ratios.py` `register_builtin_signals`).

### 1.3 Compute entrypoint — `compute(spec_name, conn)`

The single execution path: look up `REGISTRY[spec_name]` (raising `KeyError` if absent), refuse a spec with no `fn` (`RuntimeError`), call `spec.fn(conn)` with a DuckDB connection, and — if `spec.output` is set — persist the result as `derived:` rows before returning (`src/premura/engine/__init__.py` `compute`). The function's only ambient input is the warehouse connection: by contract a signal reads what it needs from `hp.fact_measurement` / `hp.fact_interval` / `hp.dim_metric` and returns rows. There is no parameter channel for caller-supplied context beyond `conn`.

### 1.4 Domain listing — `list_by_domain(domain)`

Returns every `SignalSpec` whose `domain` tag list contains the requested tag (`src/premura/engine/__init__.py` `list_by_domain`). It is pure discovery: it does **not** check whether the signal's inputs are actually present — that is the availability seam below. MCP's tool-exposure logic uses it to find signals relevant to a user-selected direction. A sibling `list_auto_safe()` returns specs with `auto_safe=True`, and is explicitly **metadata only** today (`src/premura/engine/__init__.py` `list_auto_safe`; WP01 Known Debt 4).

### 1.5 Input-availability checks — `check_inputs_available` + `list_unavailable`

`check_inputs_available(inputs, conn, within)` returns `True` only if every requested `metric_id` has at least one usable measurement, where "usable" is **validity-gated, not just presence-gated**: it reads each metric's `validity_window` from `hp.dim_metric`, takes the tighter of that window and a caller-supplied `within`, and treats data older than the effective window as unavailable (`src/premura/engine/__init__.py` `check_inputs_available`, `_lookup_validity_window`, `_effective_window`; WP01 Stable Commitment 8). `list_unavailable(domain, conn)` is the user-facing complement: the subset of `list_by_domain(domain)` whose inputs are not all available, which MCP turns into a "go get this lab" missing-inputs report (`src/premura/engine/__init__.py` `list_unavailable`). **Crucially, the availability contract is built entirely on `metric_id`s that live as time-stamped rows in the fact tables** — this is the exact assumption profile data breaks (§3).

### 1.6 Revisions — the `revision` field as a staleness anchor

`revision` is a single seam element worth calling out on its own because it spans two stages of the data model: it lives on `SignalSpec`, is written into the `raw_payload` of every persisted `derived:` row at compute time (`src/premura/engine/__init__.py` `_persist_derived_rows`, which sets `payload["revision"] = spec.revision`), and is the hook a deferred `hpipe revalidate` verb will key on (`docs/architecture/UPDATE_STRATEGY.md` §(d)). Today it is **metadata only**: the metadata is in place but no revalidation command consumes it (WP01 Known Debt 3).

### 1.7 The `derived:` persistence pattern

When a signal declares an `output`, `compute` calls `_persist_derived_rows`, which coerces the function result into rows requiring `ts_utc`, `unit`, `source_id`, `source_uuid`, and `dedupe_key`, stamps `revision` into `raw_payload`, and writes to `hp.fact_measurement` via `INSERT … ON CONFLICT (dedupe_key) DO UPDATE` (`src/premura/engine/__init__.py` `_persist_derived_rows`, `_coerce_derived_rows`). The canonical worked example is the lab-ratio family: each row joins a numerator and a denominator measurement **on the same `source_id` and the same `ts_utc`**, divides them, and emits a `derived:` row whose `dedupe_key` is `{output_metric}:{source_id}:{ts}` (`src/premura/engine/lab_ratios.py` `_ratio_rows`, `_derived_row`). This same-source, same-timestamp join is the engine's only demonstrated way of combining inputs — and it has no slot for a stable, source-less, timeless attribute like sex or birth date (§3).

### 1.8 What is *not* in the seam yet (context, not inventory)

For completeness, three Stage 2 responsibilities are named in the docs but **not shipped**, so they are not seam elements to disposition: the **signal selector** (ranking which signals answer a question) exists only as `list_by_domain` / `list_unavailable` discovery, not ranking (WP01 Known Debt 2); the **missing-data imputation path** is declared per-metric in `dim_metric.yaml` and described as an `is_imputed` mask in `STAGES.md`, but no public engine function applies it (WP01 Known Debt 5); and **derived-signal revalidation** is the `revision` metadata with no command behind it (§1.6). These are gaps, not contracts — later missions own them.

---

## 2. Keep / Change / Defer disposition (T015)

For each seam element above, exactly one disposition and a one-sentence, contract-level rationale. "Keep" = the contribution contract should inherit it unchanged; "Change" = the contract should revise what it promises; "Defer" = leave the disposition to a later mission because it depends on work this mission does not own.

| # | Seam element | Disposition | Rationale (contract-level) |
|---|---|---|---|
| 1 | `SignalSpec` core fields: `name`, `domain`, `inputs`, `output`, `fn` | **Keep** | These already carry exactly what a registration needs — identity, discovery tags, input/output `metric_id`s, and the body — and WP01 confirms they are the fields a contribution model needs (WP01 Stable Commitment 6). |
| 2 | `SignalSpec.priority` | **Keep** | A three-level `high`/`normal`/`low` knob that only drives missing-input surfacing is a stable, low-commitment contract field worth inheriting as-is. |
| 3 | `SignalSpec.auto_safe` | **Keep** | The flag is harmless metadata that future auto-precompute can consume; keeping it costs nothing and preserves the conservative `False` default (WP01 Known Debt 4). |
| 4 | `SignalSpec.revision` | **Keep** | It is the only staleness anchor the warehouse has for `derived:` rows and is already wired into persistence; the missing piece is a *command*, not the field (WP01 Known Debt 3). |
| 5 | The `SignalSpec` record as the **whole** contributor surface | **Change** | A registration record is not a *contribution contract*: it has no slot for the rationale, grounding evidence, caveats, tests, or review notes a new engine function must ship with, so the contract WP03 designs must wrap or extend it rather than treat `SignalSpec` as sufficient (WP01 Open Question 1; mission spec FR-004). |
| 6 | `REGISTRY` + `@signal(...)` decorator + lazy load | **Keep** | A module-level dict populated by a decorator, with collisions caught at review time, is a simple open-boundary mechanism that already supports the proprietary-reimplementation goal (`_registry.py`; WP01 Stable Commitment 4). |
| 7 | `compute(spec_name, conn)` entrypoint | **Change** | The contract that a signal's *only* input is a DuckDB `conn` cannot express functions that also need baseline profile context (height, sex, age); the entrypoint contract must gain an explicit, declared way to receive that context rather than letting a function reach for it out of band (§3; issue #6). |
| 8 | `list_by_domain` (+ `list_auto_safe`) | **Keep** | Pure tag-based discovery is correct as a contract and deliberately separate from availability; nothing about it blocks the contribution model. |
| 9 | `check_inputs_available` / `list_unavailable` (validity-gated availability) | **Change** | The availability contract assumes every input is a time-stamped fact-table `metric_id` with a `validity_window`; it must be extended to express a *profile precondition* (e.g. "needs the operator's height") that is checked differently from a time-series freshness check (§3.3; issue #6). |
| 10 | `derived:` persistence pattern (`_persist_derived_rows`, `dedupe_key`, same-source/same-timestamp join) | **Defer** | The persistence mechanics are sound for measurement-derived signals, but whether profile-dependent functions persist `derived:` rows at all — and how those rows get a `ts_utc` / `source_id` when one input is timeless — depends on the storage decision in issue #6, so the disposition cannot be settled here. |

Summary: the **mechanism** of the seam (registry, decorator, discovery, validity-gated availability of *measurements*, revision metadata, persistence mechanics) is largely **keep**. The two **change** items are both about *what a function is allowed to depend on*: the contributor surface must grow beyond a bare `SignalSpec` (item 5), and the `compute` + availability contracts must learn to express a baseline-profile precondition (items 7 and 9). The one **defer** is persistence of profile-dependent outputs, which is downstream of issue #6.

---

## 3. Baseline-profile dependency analysis (T016)

### 3.1 The categories of baseline profile data early functions will need

WP05 will pick the actual quick-win functions; this WP only names the *data* they will plausibly require. The categories are **stable or slowly-changing personal context** about the operator, not events that happened at a timestamp:

- **Sex / biological sex** — fixed for the purposes of nearly every reference range; needed for sex-specific lab interpretation (many `lab:*` markers have sex-specific normal ranges), body-composition norms, and HR/HRV context.
- **Birth date → age** — birth date is fixed; *age* is derived from it and "now," and changes continuously. Needed for any age-adjusted interpretation (resting HR norms, fitness benchmarks, lab reference ranges that shift with age).
- **Height** — effectively fixed for an adult; needed by ratio-style functions (most obviously BMI = weight / height², the example issue #6 itself names).
- **Other stable context of the same shape** — e.g. a self-reported baseline the operator sets once and rarely revisits.

These are exactly the attributes issue #6 enumerates ("height, age, sex, and similar operator-specific context") and the attributes WP01 flagged as Open Question 5.

### 3.2 Why these do not fit the ordinary observed-measurement model

Premura's measurement model — `hp.fact_measurement` / `hp.fact_interval` — stores **what was observed, at a timestamp, in canonical units, with provenance**, and Stage 2 reads those rows as time-series facts (`docs/architecture/STAGES.md` §1, §2). Baseline profile attributes break that model in several concrete ways:

1. **They are context, not observations.** Sex and birth date are not "measured at a time"; they are stable facts about the person. Forcing them into `fact_measurement` means inventing a `ts_utc` and a `source_id` for something that was never observed by a device, which corrupts the meaning of those columns.
2. **The validity model is built for freshness, not permanence.** `check_inputs_available` treats anything past its `validity_window` as unavailable (`src/premura/engine/__init__.py` `check_inputs_available`). A birth date or sex never goes stale, so the freshness machinery is the wrong gate for them; modeling sex with a `validity_window` is a category error.
3. **The combination pattern has no slot for them.** The one demonstrated way the engine combines inputs is the lab-ratio join on identical `source_id` **and** `ts_utc` (`src/premura/engine/lab_ratios.py` `_ratio_rows`). A timeless, source-less attribute like sex has neither key to join on, so a sex-adjusted function cannot use the existing pattern to pull sex in.
4. **The repo already shows the awkwardness in practice.** `height` and `bmi` are present in the ontology but modeled as device-emitted *measurements* with `value_kind: instantaneous`, a `validity_window` (`P1Y` for height, `P1W` for BMI), and `last_observation_carried_forward` imputation (`src/premura/dim_metric.yaml` `height`, `bmi`). That works only because a smart scale happens to emit them; it does **not** give a function a reliable way to know the operator's height when no scale reported it. And the attributes with no device source at all — **sex** and **birth date / age** — simply do **not exist** as metrics in `dim_metric.yaml` today (verified: the ontology has `fitness_age`, a wearable's *estimate*, and `lab:shbg`'s "sex hormone…" label, but no `sex`, `gender`, `birth_date`, or operator `age` row). So the data a sex- or age-adjusted function needs is not merely awkward to model — for the most important attributes it is **absent**.

### 3.3 Tie to plausible early function ideas

The dependency is not hypothetical; it lands on the most obvious quick wins:

- **BMI as a grounded engine function** — needs height; the only height available is whatever a scale happened to report, with no profile fallback (issue #6 names BMI explicitly).
- **Age-adjusted resting-HR or fitness interpretation** — needs age, which is derived from a birth date that is not stored anywhere.
- **Sex-specific lab reference ranges** — needed to interpret many `lab:*` markers correctly; sex is not stored anywhere.

In each case the *signal math* is simple and grounded, but the function quietly depends on stable context that the measurement model cannot supply cleanly. That is precisely why §2 marks the `compute` entrypoint (item 7) and the availability contract (item 9) as **change**: a function must be able to **declare** that it needs height/sex/age as a precondition, rather than silently assuming a measurement row exists.

---

## 4. Connect the gap to issue #6 (T017)

This profile-data problem is not for this mission to solve; it is tracked as GitHub issue [#6 — "Model baseline personal profile attributes for engine functions"](https://github.com/nicofirst1/premura/issues/6). Issue #6 was spotted during discovery for *this* Stage 2 research mission and frames the same gap from the data-model side: even simple grounded functions like BMI or age-adjusted interpretations need data that "does not naturally belong in `hp.fact_measurement` / `hp.fact_interval`."

### 4.1 What remains unresolved in #6

Issue #6 leaves the **storage and update model open** — explicitly, these questions are unanswered:

- **Scope**: which attributes belong in Premura's core data model versus stay out of scope.
- **Where they live**: warehouse tables, config, metadata, or another explicit seam — undecided.
- **Stable vs time-varying representation**: how to represent permanent attributes (sex), mostly-stable ones (height), and derived-from-stable ones (age from birth date).
- **Provenance and recompute**: how profile data participates in provenance and in future recompute flows for derived signals (the same `revision` / revalidation story §1.6 leaves open).
- **Privacy and UX**: what rules apply when agents use these attributes in health interpretations (consistent with the local-first, no-telemetry posture — WP01 Stable Commitment 10).

Until those are decided, **how baseline profile data is stored and updated is genuinely undecided.** This WP names the dependency; it does not pick an answer.

### 4.2 How later implementation work should treat this dependency until #6 is resolved

Concrete guidance for WP05's shortlist and for any future Stage 2 implementation mission:

1. **Treat profile data as an explicit precondition, never a silent assumption.** A function that needs height/sex/age must *declare* that need (the §2 "change" to the `compute` entrypoint and the availability contract), so a missing attribute fails loudly and surfaces a "we need your height/sex/birth date" prompt — the same way `list_unavailable` surfaces a missing lab — rather than producing a wrong or empty result.
2. **Do not back-door profile data into `fact_measurement`.** Reusing the measurement table for sex or birth date would corrupt the "what was observed at a timestamp" contract (§3.2) and pre-empt the storage decision #6 owns. If a quick win is blocked on profile data, prefer one whose inputs are already real measurements (WP05 should bias toward commonly-available metrics per WP01's guidance), or mark the function **blocked on #6**.
3. **Keep the boundary clean for #6 to fill.** The contribution contract WP03 designs should leave a named, explicit slot for "this function depends on baseline profile attribute X," so that when #6 lands a storage decision, functions can bind to it without rewriting the seam.
4. **Carry the dependency forward as a first-class risk, not an aside.** Any engine function in the quick-win set that touches height, sex, or age must cite issue #6 as its blocking design dependency until #6 closes with a documented decision (issue #6 "Success shape": a documented representation, a clear profile/measurement boundary, and a path for Stage 2 functions to depend on the data without hidden assumptions).

---

## 5. Handoff to later WPs

- **WP03 (contribution contract + grounding + gate)** owns the §2 item 5 "change": grow the contributor surface beyond a bare `SignalSpec` and add an explicit slot for a baseline-profile precondition (§4.2 item 3).
- **WP05 (quick wins + follow-on)** should read §3.3 and §4.2 before ranking: any function depending on height/sex/age is **blocked on #6** and should be flagged as such rather than assumed shippable.
- **Issue #6** remains the single home for the storage/update decision; this WP deliberately stops at naming the dependency and the two contract-level "change" implications (`compute` entrypoint and availability), per mission constraint C-004 / FR-007 (WP01 Open Question 5).
