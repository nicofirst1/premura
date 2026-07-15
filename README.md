<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo.svg" width="180" alt="Premura">
  </picture>
</p>

<h1 align="center">Premura</h1>

<p align="center">
  <em>Your health data, gathered in one place and read by an AI that refuses to guess.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-0f766e?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/data-local%20·%20encrypted-14b8a6?style=flat-square" alt="Local encrypted data">
  <img src="https://img.shields.io/badge/MCP-ready-e8707e?style=flat-square" alt="MCP ready">
  <img src="https://img.shields.io/badge/license-Apache--2.0-334155?style=flat-square" alt="Apache 2.0 license">
</p>

---

Health data does not live in one place. Nutrition sits in a food app, workouts in a sport platform, sleep and heart data in a wearable's cloud, medications in a notes file, labs in PDFs. Every vendor exports its slice in its own format, none of them agree on a standard, and most would prefer you never leave. Collecting your own health picture is work before you can learn anything from it.

Gathering it is only half the problem. A doctor cannot give fifteen years of your data their full attention in a ten-minute visit. An AI can read all of it, but a plain AI makes things up: wrong citations, invented effect sizes, confident answers where the honest answer is "not enough data".

Premura is a health AI harness built from that tension. It pulls your vendor exports into one local, encrypted warehouse (nothing uploads unless you ask) and lets an AI agent analyze them only through gated tools: deterministic statistics, refusals instead of guesses, citations only from literature the tools fetched. The AI does the reading; the harness keeps it honest.

## Why I built this

I struggled with weight gain and a fatty liver for fifteen years. I saw many doctors in those years and collected as many different diagnoses, and nothing helped. Then I handed all my data to an AI, and it suggested I get checked for insulin resistance. A blood test confirmed it. That gave me a concrete path to follow, and five months after that diagnosis my liver looks good and my body feels healthy.

I can't describe the feeling of empowerment this gave me, and I want other people to have the same chance. The AI did not do the work for me: I changed how I eat and how I move. It gave me a place to start, and Premura exists so that start is available to anyone, with the guardrails I wish I had on day one.

**Premura is not medical advice and not a diagnostic tool.** It helps you organize and understand your own health data; it does not diagnose, treat, or replace a clinician. Talk to a qualified healthcare professional about any medical decision.

> Docs live in [`docs/`](docs/): [Guide](docs/README.md) · [Doctrine](docs/shared/DOCTRINE.md) · [SPEC](docs/shared/SPEC.md) · [Changelog](docs/shared/CHANGELOG.md) · [Stages](docs/building/STAGES.md)

## Quick start

Premura is operated _and improved_ from a local clone, so the fastest start is to let your coding agent set it up. Paste this into your agent:

> Clone https://github.com/nicofirst1/premura and `cd` into it. Run `uv run premura bootstrap` to prepare the checkout, then `uv run premura install-client claude` to register Premura's default, validity-gated MCP surface with this agent (swap `claude` for `opencode` or `codex`). Reload if it tells you to.

That lands you in a working clone with the safe agent surface registered. Open a fresh agent session and ask it to help with your health data: the first run interviews you about what you want to learn and what devices you have, then guides you through collecting and reading it. The raw-SQL operator surface is never registered this way - see [OPERATIONS.md](docs/using/OPERATIONS.md#the-two-mcp-servers).

Once cloned, the setup and monthly commands work on any OS. First install [`uv`](https://docs.astral.sh/uv/), then run the rest:

```bash
uv tool install --editable .
premura bootstrap                    # SETUP: sync deps, install skills, create the age keypair
premura install-client claude        # register the safe MCP surface (or: opencode | codex)
premura doctor                        # verify environment
# drop inputs into data/inbox/, then:
premura run-monthly                   # ingest + encrypt (no auto-upload)
```

`bootstrap` creates the `age` keypair for you at `$HOME/.config/premura/age.key` when the `age` binary is present (macOS: `brew install age`; Debian/Ubuntu: `apt install age`). The `age` private key is the single secret. Lose it = lose all encrypted backups.

**macOS operator automation (optional).** `bash ops/bootstrap.sh` adds the Mac-only extras on top: Homebrew prerequisites, a launchd job for the monthly run, and rclone/Drive upload. It is not needed to try or use Premura.

## What's in the warehouse

`hp.fact_measurement` (point-in-time) and `hp.fact_interval` (bounded events), joined to `hp.dim_metric` + `hp.dim_source`. Shipped parsers cover Health Connect, Garmin, Sleep as Android, Withings, Fitbit Takeout, and MyFitnessPal, plus AI-chat recall for supplements and medication. Run `premura status` for live row counts; see [SPEC.md §5](docs/shared/SPEC.md) for the data contract.

Query directly:

```bash
duckdb -readonly data/duck/health.duckdb
```

## Surfaces

The default path is an agent operating Premura through the mcp:

- **`premura-mcp`** - the default, validity-gated agent surface. Every tool delegates to a deterministic signal engine, and tools return structured `available` / `missing_input` / `stale_input` / `insufficient_data` verdicts.
- **`premura-mcp-operator --ack`** - a lower-guarantee expert fallback that adds a raw-SQL escape hatch. It refuses to start without explicit acknowledgement.

For the `premura` CLI and how the two servers differ, see [OPERATIONS.md](docs/using/OPERATIONS.md). Direct DuckDB and notebook access remain available as expert fallbacks.

## Pointers for your agent

When you hand Premura to an AI agent, point it at the right guide:

- **Operating Premura for you** (running tools on your data, no code edits) → [runtime-agent operating guide](docs/operating/RUNTIME_AGENT.md).
- **Changing Premura's code** in this clone → [`AGENTS.md`](AGENTS.md).
- **Opening a pull request** (human or agent) → development setup, checks, and the PR workflow live in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache License 2.0 - see [`LICENSE`](LICENSE).
