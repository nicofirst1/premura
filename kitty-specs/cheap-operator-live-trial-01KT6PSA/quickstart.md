# Quickstart: run a cheap-operator live trial

> Local-only, never part of CI (NFR-001/C-004). Needs a running Ollama with a
> model pulled. Over the committed synthetic fixture it touches no private data.

## Run one trial (synthetic fixture)

```bash
# default cheap model
uv run python -m premura.harness.live_trial_ollama

# pick the operator model (capability tier)
OLLAMA_MODEL=qwen2.5-coder:7b uv run python -m premura.harness.live_trial_ollama
```

Prints, per run: attempts used, the **first-attempt** verdict, the **final**
verdict (three rules each), and where the kept session log + verdict were written.

## Read the current capability floor

```bash
# which model tiers currently reach a passing final verdict, first-attempt vs final
uv run python -m premura.harness.scoreboard           # or read data/live_trials/scoreboard.jsonl
```

## Gated end-to-end test (opt-in)

```bash
uv run pytest -m live_trial tests/test_live_trial_ollama.py -s   # needs Ollama
```

## Default suite stays green with no model server

```bash
uv run pytest -q     # deselects live_trial; self_reconcile + scoreboard unit tests run
```

## Real local data (manual, nothing persisted)

Pointing the run at `~/Downloads/MyFitbitData` executes locally but writes **no**
kept log, **no** scoreboard line, and leaves no extracted data in the repo
(FR-012/NFR-002). PHI never enters the repo or a commit (C-001).
