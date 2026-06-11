# Quickstart: Tool-loop live-trial tier

## Run a tool-loop trial (synthetic fixture, local model)

Requires a running Ollama with a tool-capable model pulled
(default `qwen2.5-coder:7b`):

```bash
uv run python -m premura.harness.live_trial_tool_loop
# pick a model / raise the cap:
OLLAMA_MODEL=qwen2.5-coder:14b LIVE_TRIAL_MAX_TURNS=10 \
  uv run python -m premura.harness.live_trial_tool_loop
```

Prints turns used, the first-parser and final verdicts (three-rule grader
output), and the kept run dir (synthetic runs only). Exit codes: `0` ran,
`2` model unavailable, `3` model lacks tool support.

## Compare tiers on the scoreboard

```bash
uv run python -m premura.harness.scoreboard
```

The floor table groups by `(operator_model, tier)` — `one_shot` rows (all
pre-existing history) and `tool_loop` rows side by side.

## Run the intake drawer instead of observation

The entry point is scenario-parametric; pass the registered intake scenario
the same way `run_live_trial_ollama` accepts one (see the module docstring).
No drawer-specific flags exist — that is the point.

## Tests

```bash
uv run pytest -q                              # default suite: fake-backend loop tests, no model needed
uv run pytest -q -m live_trial                # gated: real local model (skips if Ollama is down)
```

## Containment reminders

- Real (non-synthetic) sources: nothing persists, sandboxes always torn down.
- The model endpoint must be localhost — non-local `OLLAMA_URL` is refused.
- The fixture manifest is unreachable through any tool; do not "help" the
  operator by adding it to the `read_context` allowlist.
