# Add a new intake dimension

> **Audience:** an agent (or contributor) making a _declared_ intake dimension actually **usable** — resolvable through the input-resolution seam and answerable on the default agent surface.
>
> **Altitude (DOCTRINE, "guide, don't enumerate"):** this is the **rule** for adding an intake dimension, not a list of nutrients or supplements. Every step below is domain-agnostic. The two shipped domains (`nutrition_intake`, `supplement_intake`) are cited only as _proof the rule generalizes_ — not as the catalogue of what intake can be.

## What "usable" means here

A semantic domain can already be _declared_ (a signal may say it `depends_on_domain="<domain>"`) and its rows can already be _stored_ long before anything can _read_ them. Premura shipped `nutrition_intake` and `supplement_intake` in exactly that half-built state: declarable storage targets with a working `IntakeBatch -> persist_intake_batch` load path, but every declared dependency resolved to the explicit `unsupported_domain` outcome, so no signal could use them and no agent tool could answer over them.

Making a declared intake dimension _usable_ means closing that gap **without adding a new abstraction layer** — by riding the existing `@resolver(domain=...)` seam, the existing signal registry, and the existing default MCP surface. This document is the written rule for doing that; it is the generalization the two shipped domains validate.

## The rule — four domain-agnostic steps

Adding a usable intake dimension is fill-in-the-blank against the seams that already exist. No step changes the shared resolution path.

### Step 1 — the domain already exists in `SEMANTIC_DOMAINS`

The domain string must already be a member of `premura.engine._resolution.SEMANTIC_DOMAINS` (a closed `frozenset`). That set is the registry of valid declaration targets; adding a _brand-new_ domain string is a separate, deliberate decision (the domain-vs-shape rubric), **not** part of making an already-declared domain usable. If your domain is not in the set, stop — that is a different, larger change.

The `@resolver(domain=...)` decorator and `resolve_dependency(...)` both validate membership and raise `ValueError` for an unknown domain, so a typo cannot silently create a phantom domain.

### Step 2 — add a resolver module under `engine/views/` and register it

Write one module under `src/premura/engine/views/<domain>.py` exposing a function decorated with `@resolver(domain="<domain>")` (`premura.engine._registry.resolver`). The function has the resolver signature `(*, request, conn) -> ResolvedInput` and must:

- read **only** that domain's dedicated tables — never fall back to `hp.fact_measurement` or another domain (NFR-003: no hidden cross-domain substitution);
- turn a caller-declared selector + window into a **domain-level payload** (the raw material a signal needs), and return an explicit non-usable `ResolvedInput` (missing / stale) when no matching, fresh row exists — never a fabricated value;
- stay **generic** — interpret a caller-declared selector, never enumerate known nutrients/supplements (DOCTRINE / C-007);
- report its temporal basis explicitly (`day_basis`): bucket each event by its **local calendar day** via `premura.engine._localtime.local_calendar_day` when `local_tz` is present and parseable, else fall back to the naive-UTC day, and never silently mix the two (NFR-006).

Then append the module's dotted name to `_BUILTIN_RESOLVER_MODULES` in `src/premura/engine/__init__.py`. Registration is a **side effect of import** (the decorator writes into `premura.engine._registry.RESOLVERS`); the lazy loader `_ensure_builtin_resolvers_loaded()` imports every listed module on first resolution. No filesystem scanning, no entry points — one module, one line.

### Step 3 — add a descriptive signal in an already-registered signal module

Add a signal function and its `SignalSpec` registration to an **already-registered** signal module (e.g. `register_builtin_signals()` in `src/premura/engine/descriptive_signals.py`, which is already listed in `_BUILTIN_SIGNAL_MODULES`). The signal:

- declares the intake dependency and reads **only** through the Step-2 resolver (it never re-reads the intake tables itself);
- returns the **standard signal envelope** with the four structurally-distinct states `available` / `missing_input` / `stale_input` / `insufficient_data`, plus authored missing-input guidance — consistent with the existing six signals (FR-005);
- stays **descriptive, non-diagnostic**: no reference ranges, no "you should", no significance/causation, and (for trends) it never imputes a missing day (NFR-001 / FR-004);
- takes a **caller-declared field** (which supplement, which nutrient/energy key, which window) rather than enumerating specific ones (C-007), and chooses one of the four `family` values (`status` / `trend` / `baseline` / `change`).

Because the family belongs to an already-listed module, no change to `_BUILTIN_SIGNAL_MODULES` is needed — the signal is registered the next time the built-in signals load.

### Step 4 — expose it as a default-surface tool

Add a **thin** tool to the default agent (MCP) surface so the signal is genuinely usable by an agent, not just resolvable internally (FR-006). The wrapper:

- lives as a plain function in `src/premura/mcp/server.py` that validates only the caller-facing parameter shape, then delegates **entirely** to the signal through `_run_signal(...)` / `compute(..., params=...)` — no raw SQL, no re-read of the intake tables, no re-derived coverage/trend math;
- is registered on the default surface by a `@mcp.tool()`-decorated shim in `_register_default_tools(...)` in `src/premura/mcp/entrypoint.py`, following the same validity-gated pattern as the existing signal-backed tools;
- passes the four engine states straight through, so an empty / stale / too-thin domain comes back as an honest refusal with its own state.

## Both shipped domains followed exactly these steps — and the shared seam did not change

This is the proof: adding the _next_ intake dimension requires the four steps above and **no change to the shared resolution seam**, because both shipped domains rode exactly those steps.

| Step                                         | `nutrition_intake` (worked example)                                                                                                           | `supplement_intake` (worked example)                                                                                                             |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1. Domain in `SEMANTIC_DOMAINS`              | `"nutrition_intake"` already a member                                                                                                         | `"supplement_intake"` already a member                                                                                                           |
| 2. Resolver module + registration            | `engine/views/nutrition_intake.py` → `@resolver(domain="nutrition_intake")` `resolve_nutrition_intake`; listed in `_BUILTIN_RESOLVER_MODULES` | `engine/views/supplement_intake.py` → `@resolver(domain="supplement_intake")` `resolve_supplement_intake`; listed in `_BUILTIN_RESOLVER_MODULES` |
| 3. Descriptive signal in a registered module | `nutrition_intake_trend` (`family="trend"`) registered in `descriptive_signals.register_builtin_signals()`                                    | `supplement_intake_adherence` (`family="status"`) registered in `descriptive_signals.register_builtin_signals()`                                 |
| 4. Default-surface tool                      | `nutrition_intake_trend(quantity_key, window_days=...)` wrapper in `mcp/server.py`, shim in `entrypoint._register_default_tools`              | `supplement_intake_adherence(matcher, window_days=...)` wrapper in `mcp/server.py`, shim in `entrypoint._register_default_tools`                 |

**No shared-seam change.** Neither domain added a branch to `premura.engine._resolution.resolve_dependency`: that path still dispatches purely by registry lookup and never names an intake domain. This is asserted structurally, not by prose, in `tests/test_intake_resolvers.py::test_shared_seam_has_no_per_domain_branch` (NFR-005) — it reads the source of `resolve_dependency` and fails if either intake domain string appears as a per-domain branch. The registration-completeness half (both resolver modules registered, both signals in `REGISTRY`) is covered by `tests/test_intake_resolvers.py` and `tests/test_intake_signals.py`.

## Caller-declared selector semantics (the matcher / quantity key)

Step 2 says the resolver interprets a _caller-declared selector_. To keep the rule honest about what "selector" means — and so no later domain re-invents it — the two shipped selectors are pinned **once, authoritatively, in code**:

- **Supplement matcher** — the single authoritative implementation is `matches_supplement(matcher, product_label, ingredient_label)` in `src/premura/engine/views/supplement_intake.py`. Its semantics (also stated in that module's docstring) are:
  - **no hardcoded supplement list** — the caller declares the matcher;
  - **case-insensitive substring** — a token matches when it appears, case-folded, anywhere inside a label;
  - **label precedence: product label, then ingredient label** — a token matches an item if it is a substring of `product_label`, or, failing that, of `ingredient_label`;
  - **multiple tokens combine as AND** — whitespace splits the matcher into tokens and _every_ token must match.
- **Nutrition quantity key** — the resolver (`resolve_nutrition_intake`) selects on a caller-declared `quantity_key` (e.g. `"energy"`, `"protein"`); quantity keys are intrinsic to the intake seam, not observation `metric_id` values, and are never enumerated in tree form.

> **Note.** The supplement matcher semantics are pinned authoritatively in `engine/views/supplement_intake.py` (the docstring + the exported `matches_supplement` function); this doc summarizes them.

## Why no new abstraction layer (C-003)

Premura deliberately did **not** build a dedicated intake-dimension contract or registry. Two domains rode the existing `@resolver` seam cleanly with no special-casing, which is the evidence that the seam already generalizes. Whether a dedicated intake-dimension contract ever earns its place is left open until a concrete need arises.
