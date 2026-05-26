# Research: Harden Grounded Stage 2 Contract

No open unknowns — the post-merge mission review and the spec already determine
the approach. Three small design decisions are recorded here for the
implementers.

## Decision 1 — Where to build the `MissingInputReport`

- **Decision**: Build it in the Stage 3 layer (`src/premura/mcp/server.py`), at
  serialization time, from the signal's declared `inputs` (in the registry) plus
  the result envelope's freshness/availability state.
- **Rationale**: The engine signals already return their family envelopes; the
  Stage 3 serializer is the single chokepoint (`_serialize_signal_result`) where
  every tool response is shaped, and it already classifies the unavailable
  reason. The registry `SignalSpec` carries both `inputs` and
  `missing_input_hint`, both reachable from the server. Keeping the report
  construction in Stage 3 avoids changing every signal's return type.
- **Alternatives considered**: Have each signal return a `MissingInputReport`
  directly — rejected as a larger, riskier change to six signals for no added
  truth. The data needed is already available at the serialization boundary.

## Decision 2 — Deriving required / missing / stale inputs

- **Decision**: `required_inputs` = the signal's declared `inputs`. For a
  single-input signal, an `unavailable` freshness maps the input to
  `missing_inputs`, and a `stale` freshness maps it to `stale_inputs`. The
  user-facing message uses the registered `missing_input_hint`.
- **Rationale**: All six approved signals are single-input, so this mapping is
  unambiguous and honest today. It generalizes cleanly later (per-input state)
  without over-building now.
- **Alternatives considered**: Inventing per-input freshness plumbing through the
  engine — out of scope; no current signal needs it.

## Decision 3 — Keep the loader lazy while tracking load state

- **Decision**: Introduce a module-level `_BUILTINS_LOADED = False` sentinel in
  `src/premura/engine/__init__.py`; `_ensure_builtin_signals_loaded()` returns
  early only when the flag is set, then sets it after importing the static
  built-in modules. Importing `premura.engine` still does not call the loader.
- **Rationale**: Decouples "have built-ins loaded?" from "is the registry
  non-empty?", which is what makes a pre-registered custom signal suppress
  built-ins today. Smallest change that removes the footgun and keeps the lazy
  guarantee.
- **Alternatives considered**: Tracking loaded module names in a set — equivalent
  behavior, marginally more code; a single boolean is sufficient because the
  built-in set is static.
