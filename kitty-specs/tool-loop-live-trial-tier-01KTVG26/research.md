# Research: Tool-loop live-trial tier (Phase 0)

All spec-time and plan-time unknowns are resolved below. No
`[NEEDS CLARIFICATION]` markers remain.

## R-1: Multiturn transport and tool-call expression

- **Decision**: Ollama `/api/chat` with **native tool-calling** — request
  carries `messages` (full history) + `tools` (JSON-schema function specs) +
  `options: {temperature: 0.1, num_ctx: <pinned>}`; the response's
  `message.tool_calls` array carries structured calls
  (`function.name` / `function.arguments`). Tool results are appended as
  `role: "tool"` messages. Chosen by the maintainer at plan interrogation.
- **Rationale**: structured calls remove the fragile fenced-text parsing the
  spike harness hand-rolled; history is first-class instead of string
  concatenation; the same stdlib-`urllib` posture as the one-shot client
  carries over (no new dependency, same `_validated_ollama_url` local-only
  guard applies to the chat URL).
- **Consequence handled as a rule**: native tools require model-template
  support. Ollama rejects a tools request for an unsupporting model with an
  HTTP error naming the model. The harness maps that to a returnable
  `tool_calls_unsupported` outcome (sibling of `model_unavailable`) — the tier
  is defined by the rule "a tool-loop trial requires a tool-capable model",
  not by a hardcoded model list (NFR-005). The default model family
  (`qwen2.5-coder`) ships tool-capable templates in Ollama.
- **Verification boundary**: exact wire behavior (tool_calls shape, error
  body for unsupported models) is asserted in the `live_trial`-gated
  real-model test; default-suite tests substitute the chat backend at the
  outside boundary (DIRECTIVE_036), so no committed test depends on wire
  details.
- **Alternatives considered**:
  - *Harness-parsed structured-text protocol over `/api/chat`* — most
    model-agnostic, but reintroduces bespoke parsing (the spike's weak point);
    rejected by maintainer choice.
  - *`/api/generate` with concatenated history* — re-sends a growing prompt
    each turn and makes budget accounting messy; rejected.

## R-2: Serving the parser API surface (FR-002)

- **Decision**: brief inlines the **same curated contract surface** the
  one-shot tier serves (`_OBSERVATION_CONTRACT_PROMPT` /
  `_INTAKE_CONTRACT_PROMPT` via the drawer-probe rubric) — proven sufficient
  (the clean one-shot harness carried a local 14B to a pass 2/3 with it).
  The `read_context` tool additionally serves the full files
  (`src/premura/parsers/CONTRACT.md`, `src/premura/parsers/base.py`) **whole,
  never truncated**, from an explicit allowlist resolved inside the sandbox.
- **Measurements** (taken at promotion, 2026-06-11): `CONTRACT.md` 161 lines /
  ~11 KB; `base.py` 496 lines / ~19 KB; combined ≈ 8–9k tokens. The curated
  prompts are ~60–65 lines each (~0.8k tokens).
- **Budget accounting**: `LIVE_TRIAL_NUM_CTX` (default **16384**) is pinned in
  `options.num_ctx` on every chat call. Rationale for the default: Ollama's
  out-of-the-box `num_ctx` (4096) is the documented truncation trap; 16384
  holds brief (~2–3k with goal + sample + protocol) + tool schemas + both full
  contract files (~9k) + several turns of history. The brief assembler
  performs an explicit size check and fails loudly rather than truncating
  (R2 in plan risks).
- **Alternatives considered**: inlining the full files in the brief upfront
  (~9k tokens before turn 1, duplicates what READ serves) — rejected as the
  default; remains trivially reachable by the operator via one `read_context`
  call.

## R-3: Operator architecture

- **Decision**: a distinct `ToolLoopOperator` + `run_live_trial_tool_loop()`
  in a new module `src/premura/harness/live_trial_tool_loop.py`. It implements
  the existing `Operator` protocol so `live_trial.run_live_trial_with_log`
  (the WP06 scenario-parametric path) is reused verbatim for grading.
- **Reuse inventory (imported, never copied — NFR-004)**: from
  `live_trial_ollama`: the drawer-probe rubric (`_DRAWER_PROBES` /
  `_resolve_drawer_probe`), the in-sandbox gate (`_gate_parser`),
  `is_synthetic_source`, `OllamaDriver`, `OllamaUnavailableError`,
  `_validated_ollama_url`, parser-destination constants; from `scoreboard`:
  `persist_run` / `append_scoreboard` / record types; from `live_trial`: the
  run/grade path. Same-package import of module-level helpers follows the
  existing seam convention (the WP03 module already imports the WP06 path).
- **Alternatives considered**: extending `OllamaOperator` with a mode flag —
  rejected: entangles the frozen one-shot floor (C-002) with new behavior and
  violates smallest-blast-radius (DIRECTIVE_024).

## R-4: Loop protocol, turn cap, and verdict shape

- **Decision**: standard agent loop. One assistant response = one turn. Tool
  calls in a response are executed in order, each result appended as a `tool`
  message (and recorded by the harness as a session-log `tool_call` step — the
  harness stays sole log writer). A response with no tool calls ends the
  working phase; the harness runs the manifest-blind self-reconcile gate on
  the currently-written parser; a failing gate with turns remaining feeds the
  failure back as a message and the loop continues; a pass or cap exhaustion
  ends the trial. Cap: `LIVE_TRIAL_MAX_TURNS`, default **8**.
- **First/final verdicts (FR-006)**: snapshot the content of the **first
  `write_parser` call** = "first complete parser"; grade it independently
  through the same machinery via the existing fixed-code-operator pattern.
  Final verdict grades the parser present at loop end. No `write_parser` ever →
  the machinery's deterministic absent-parser FAIL path covers both verdicts
  (NFR-006; mirrors the one-shot FR-080 empty-warehouse behavior).
- **Regression visibility**: first-pass/final-fail is representable and
  reported; the loop never reports "best of" (spec edge case 1).

## R-5: Tier tagging and scoreboard compatibility (FR-007)

- **Decision**: additive `tier` field on `LiveTrialRunRecord` and
  `ScoreboardEntry`, default `"one_shot"`; the tool loop writes
  `tier="tool_loop"`. `ScoreboardEntry.from_json` treats a missing `tier` key
  as `"one_shot"`, so every existing scoreboard line parses unchanged
  (append-only file — nothing rewritten, satisfying "alongside, never
  overwriting"). `current_floor` groups by `(operator_model, tier)` and the
  CLI table renders the tier column.
- **Alternatives considered**: a distinct `run_kind` value — rejected:
  `run_kind` distinguishes harness flows (`repeatable_check` vs `live_trial`),
  and a tool-loop trial *is* a live trial; tier is a property of how the
  operator was driven, which is what the comparison axis needs.

## R-6: FR-009 — renamed-field declared-gap rule

- **Finding**: the existing `self_reconcile` gate computes
  `unaccounted = source_columns − (mapped_columns ∪ declared_gaps)` and fails
  on any unaccounted column, so the `timestamp`-consumed-as-`ts_utc` case
  *should* already fail when undeclared.
- **Decision**: (a) sharpen the contract line in both drawer prompts to state
  the renamed-field case explicitly ("a column you consume under any output
  name is still a consumed column — list it"); (b) land the committed
  deterministic fixture test (SC-007) driving a renamed-field-absorbing parser
  through the gate and asserting FAIL. Test-first: if the test is unexpectedly
  green-by-accident or exposes a hole, the gate is fixed under the test
  (DIRECTIVE_034). The brief change applies to the shared prompts, which both
  tiers serve — wording-only, no one-shot behavior change (C-002 holds: the
  one-shot scoring path is untouched; its default-suite tests must stay green).

## R-7: Brief coherence (FR-001)

- **Decision**: the brief is assembled by **one** function from one canonical
  source per part (drawer-probe contract prompt + goal + data sample + tool
  protocol preamble). The spike's defect class — a contract prompt demanding
  "output only a module, no fences" while the loop demands "iterate with
  tools" — is structurally prevented: the tool-loop preamble *replaces* the
  one-shot output-format directive rather than appending to it, and a
  committed test asserts the assembled brief contains the loop protocol, the
  full required API class names (SC-006), and none of the one-shot-only
  output directives.
