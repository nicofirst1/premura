# Recommendation: a dedicated intake-dimension contract

> **Status:** recommendation only. Per **C-003**, the `usable-intake-dimensions`
> mission did **not** build any new abstraction layer for intake dimensions; this
> note records the go/no-go, a sketch of what such a layer would be, and the
> explicit trigger condition that would make it worth building.

## Verdict: NO-GO (do not build it now)

A dedicated intake-dimension contract or registry is **not** warranted today.

The evidence is the mission itself: **two** intake domains
(`nutrition_intake`, `supplement_intake`) were each made usable end-to-end —
resolver → descriptive signal → default-surface tool — by following one written
rule
([`INTAKE_DIMENSIONS.md`](../architecture/INTAKE_DIMENSIONS.md)) over the
**existing** seams, with **no change to the shared resolution path**. That "no
shared-seam change" claim is asserted structurally, not by prose, in
`tests/test_intake_resolvers.py::test_shared_seam_has_no_per_domain_branch`
(NFR-005). When two independent domains ride an existing abstraction cleanly,
adding a *new* abstraction on top would be speculative generality — it would pay
the cost of a contract (more surface to learn, more to keep in sync, another
drift source) before any concrete need has appeared. The right move is to keep
using the `@resolver(domain=...)` seam and the four-step rule, and revisit only
when a *specific, measurable* pressure shows up (see the trigger below).

This matches the DOCTRINE altitude rule: we shipped the **rule** for adding an
intake dimension, not a hardcoded layer — and we hold the deferred abstraction
until a trigger fires, rather than building it on spec.

## Sketch — what a dedicated intake-dimension contract would be, if built later

If the trigger below fires, the smallest honest version of the abstraction would
be a thin **intake-dimension contract** that sits beside the existing resolver
seam, capturing only what the generic seam cannot already express:

- **A per-dimension descriptor** (in the spirit of `SignalSpec` / the resolver
  registry) declaring, for one intake dimension: its storage tables, its
  caller-declared selector shape, its freshness/sufficiency policy, and the
  payload fields its resolver yields. This makes the four-step rule
  *declarative* instead of *prose-plus-convention*.
- **A typed intake payload** richer than today's `ResolvedInput`, for dimensions
  whose resolved value needs to carry structured per-item/per-dose detail that
  the generic `ResolvedInput` cannot represent without ad-hoc dict stuffing.
- **A per-family freshness/sufficiency rule surface**, so a dimension whose
  "is this fresh / sufficient?" logic genuinely differs from the existing
  per-resolver convention can declare it once instead of re-implementing it.
- **A registry + conformance test** that enforces "every declared intake
  dimension has a resolver, a signal, and a tool" — turning the rule's four steps
  into a checked invariant rather than a reviewer checklist.

It would **not** replace the `@resolver` seam; it would formalize the parts of
the four-step rule that are currently carried by convention.

## Trigger condition — build it when ANY of these is measurably true

Treat these as concrete, observable signals, not vibes. Build the dedicated
contract when **any one** of them is met:

1. **Payload pressure.** The **third** intake dimension needs the resolver to
   carry a structured payload field that the generic `ResolvedInput` cannot
   represent without ad-hoc dict stuffing — i.e. a resolver starts smuggling
   nested per-item/per-dose structure through a stringly-typed escape hatch
   because the seam has no place for it.
2. **Freshness/sufficiency pressure.** A new intake dimension's
   freshness-or-sufficiency rule **cannot be expressed per-family** with the
   existing four-state envelope (`available` / `missing_input` / `stale_input` /
   `insufficient_data`) and would force a per-domain branch into the shared
   resolution path — i.e. honoring it would make
   `test_shared_seam_has_no_per_domain_branch` impossible to keep green.
3. **Drift pressure.** A usable intake dimension ships **missing one of the four
   steps** (resolver, signal, or default-surface tool) and the gap reaches review
   or runtime undetected — evidence that the rule needs to be a *checked
   invariant* (a registry + conformance test) rather than reviewer discipline.

Until one of these is measurably true, the recommendation stands: keep adding
intake dimensions with the four-step rule over the existing seam, and do not
build the contract.
