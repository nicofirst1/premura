# Contract: Intake Resolution And Signals

Purpose: define the mission-local contract for the two new intake resolvers and
their signal consumers.

## Resolver contract

1. `nutrition_intake` and `supplement_intake` resolve through the existing
   registry-driven `@resolver(domain=...)` seam.
2. No shared-path special casing is added to `resolve_dependency(...)`; the
   common seam remains domain-agnostic.
3. Resolvers return domain-generic resolved payloads plus explicit unusable
   outcomes; they do not compute final user-facing answers.
4. A declared intake dependency is never satisfied from observation rows.

## Signal contract

1. One descriptive signal per intake domain ships in this mission.
2. Both signals accept bounded caller-supplied windows with repo defaults.
3. Both signals remain generic:
   - nutrition: caller-declared quantity key
   - supplement: caller-declared supplement matcher
4. Missing days remain visible; the nutrition trend never imputes them.
5. Signals remain descriptive only: no diagnosis, treatment advice, causation,
   statistical significance, or normative recommendation language.
6. The Stage 2 signal design and the Stage 3 wrapper status classification remain
   distinct: do not force MCP `status` fields into the Stage 2 envelope contract
   if the existing engine signal contract uses a different shape.

## Temporal basis contract

1. When `local_tz` is present on intake events, day/window/freshness semantics are
   based on the event's **local calendar day**, not its raw UTC date.
2. When `local_tz` is absent, the implementation may use Premura's existing
   naive-UTC convention, but that fallback must be explicit.
3. Reported metadata must use the same day basis the computation uses.

## Acceptance-fixture requirements

1. Positive-path fixture per availability clause:
   - data present -> answer surfaced
2. Separate refusal-path fixtures:
   - no matching rows
   - stale rows
   - insufficient data where applicable
3. One representational-divergence fixture:
   - local day != UTC date
   - reported metadata still matches the computed local-day basis
