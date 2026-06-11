# Contract: Tool-loop live-trial tier

This contract binds the new module's externally observable behavior. Tests
derive from it (DIRECTIVE_036); internals may change freely beneath it.

## 1. The tool contract (rule, not list — FR-003/FR-004, NFR-005)

A **tool** is a named registration `{name, description, parameters-schema,
handler}` where the handler's reach is **physically bounded**: it may touch
only the capability its registration states, resolved inside the trial's
sandbox or scenario context. No registration may grant reach to the fixture
manifest or any ground-truth mapping; consequently no sequence of tool calls,
at any turn, can observe the answer key (C-005 by construction).

Adding a tool = adding one registration. Editing loop control flow to admit a
tool is a contract violation.

**First registered instances** (the instances, not the bounds):

- `read_context(path)` → returns the **whole** content of the scenario source
  artifact or an allowlisted contract file (`src/premura/parsers/CONTRACT.md`,
  `src/premura/parsers/base.py` — resolved in the sandbox tree). Any other
  path → a refusal string fed back as the tool result (never an exception, and
  never the content). Truncation of an allowlisted file is a contract
  violation (FR-002).
- `write_parser(code)` → writes `code` to the sandbox parser destination
  (`src/premura/parsers/_live_trial_parser.py` inside the sandbox). The first
  call's content is snapshotted as the **first complete parser**. Returns a
  confirmation string.
- `run_ingest()` → executes the real ingest subprocess (the WP03 runner) over
  the scenario source against the sandbox warehouse using the currently
  written parser; returns the runner's JSON envelope verbatim (stage-tagged
  errors included). It never returns grader output.

## 2. The brief (FR-001/FR-002)

Assembled by one function from one canonical source per part, in order:
tool-loop preamble (loop protocol + tool usage rules) → drawer-probe contract
surface (the same curated prompt the one-shot tier serves, with the sharpened
renamed-field declared-gap line, FR-009) → goal (driver's, PHI-safe) → data
sample (same form as the one-shot tier).

Invariants (committed brief test):
- contains every API class name the operator must implement against (SC-006);
- contains the loop protocol;
- contains **no** one-shot-only output directive (the "output ONLY the module,
  no prose/fences" line is replaced by the tool protocol, not joined with it);
- total assembled size is checked against the pinned context budget and fails
  loudly on overflow — never truncates.

## 3. The loop protocol (FR-005/FR-006)

- Transport: local Ollama `/api/chat`; URL validated by the existing
  local-only guard (NFR-001). `options.num_ctx` = `LIVE_TRIAL_NUM_CTX`
  (default 16384); temperature pinned low as the one-shot tier does.
- One assistant response = **one turn**. Cap = `LIVE_TRIAL_MAX_TURNS`
  (default 8). Turn accounting is exact: a malformed or refused tool call
  still consumes its turn, with a corrective message fed back.
- A response with no tool calls ends the working phase → the harness runs the
  manifest-blind self-reconcile gate (the existing in-sandbox probe) on the
  currently written parser. Gate fail + turns remaining → verbatim feedback
  message, loop continues. Gate pass or cap exhausted → trial ends.
- Grading: the existing scenario-parametric run path grades the **first
  complete parser** (snapshot) and the **final parser** independently — two
  verdicts, exactly the one-shot shape. No parser ever written → both
  verdicts are the machinery's deterministic absent-parser FAIL.

## 4. Outcomes (NFR-006)

`run_live_trial_tool_loop(...)` returns exactly one of:

| Outcome | Condition | Record persisted? |
|---------|-----------|-------------------|
| complete record (`tier="tool_loop"`) | trial ran to gate-pass or cap | synthetic source only |
| `model_unavailable=True` | endpoint unreachable | never |
| `tool_calls_unsupported=True` | model template lacks tool support | never |

No path raises out of the entry point before one of these exists. Real
(non-synthetic) sources persist nothing and always tear sandboxes down,
`keep_sandboxes` included (NFR-002).

## 5. Tier record shapes (FR-007)

Scoreboard line (append-only JSONL; one parseable object per line):

```json
{"ts": "...", "operator_model": "...", "driver_model": "...",
 "attempts_used": 3, "first_attempt_pass": false, "final_pass": true,
 "tier": "tool_loop"}
```

- A line without `tier` parses as `tier="one_shot"` (every pre-existing line
  remains valid; the file is never rewritten).
- `current_floor` groups by `(operator_model, tier)`.
- The per-run kept record carries the same `tier` on `LiveTrialRunRecord`.

## 6. Environment knobs (all optional)

| Variable | Default | Meaning |
|----------|---------|---------|
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | operator model (existing) |
| `OLLAMA_URL` | localhost generate URL | existing; chat URL derives from the same validated host |
| `LIVE_TRIAL_MAX_TURNS` | `8` | tool-loop turn cap |
| `LIVE_TRIAL_NUM_CTX` | `16384` | pinned model context window |

## 7. CI containment (NFR-003, C-004)

The real-model test is `@pytest.mark.live_trial` and excluded from the default
suite. Default-suite tests substitute the chat backend at the outside boundary.
Zero CI gates reference the tool loop.
