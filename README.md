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

> Docs live in [`docs/`](docs/): [Guide](docs/README.md) · [Doctrine](docs/shared/DOCTRINE.md) · [SPEC](docs/shared/SPEC.md) · [STATUS](docs/shared/STATUS.md) · [Changelog](docs/shared/CHANGELOG.md) · [Stages](docs/building/architecture/STAGES.md)

## Quick start

Fresh clone? An agent (or human) in the repo runs **one setup command first**:

```bash
uv run premura bootstrap                    # SETUP ONLY: prepare + verify this local checkout, report reload guidance
```

Then operate normally:

```bash
bash ops/bootstrap.sh                       # one-time: brew installs, age keypair, optional rclone; puts `premura` on your PATH
premura doctor                              # verify environment
# drop inputs into data/inbox/, then:
premura run-monthly                         # ingest + encrypt (no auto-upload)
premura upload --month YYYY-MM              # OPT-IN — push to Drive only when you say so
```

## age key storage

The `age` private key at `$HOME/premura/age.key` is the single secret. Lose it = lose all encrypted backups. Two recommended options:

1. **Local backed-up file** (Time Machine, external drive). Default.
2. **Bitwarden secure note** - `bootstrap.sh` prints a `bw create item …` recipe you can run after `bw login`. Retrieve later with `bw get notes 'premura age key' > $HOME/premura/age.key && chmod 600 …`.

## What's in the warehouse

`hp.fact_measurement` (point-in-time) and `hp.fact_interval` (bounded events), joined to `hp.dim_metric` + `hp.dim_source`. Shipped parsers cover Health Connect, Garmin, Sleep as Android, Withings, Fitbit Takeout, and MyFitnessPal, plus AI-chat recall for supplements and medication. See [STATUS.md](docs/shared/STATUS.md) for live row counts and [SPEC.md §5](docs/shared/SPEC.md) for the data contract.

Query directly:

```bash
duckdb -readonly data/duck/health.duckdb
```

## Surfaces

The default path is an agent operating Premura through tools, not raw SQL:

- **`premura-mcp`** - the default, validity-gated agent surface (34 tools). Every tool delegates to the deterministic signal engine (no raw `hp.*` SQL), and tools return structured `available` / `missing_input` / `stale_input` / `insufficient_data` verdicts instead of free-form claims. Six analytical tools (change point, smoothed average, correlation, rolling mean, paired t-test, condition paired t-test) disclose their confounds and refuse thin samples. The literature tools `pubmed_search` and `pubmed_fetch` enforce one rule: search hits are discovery candidates only, and final answers may cite only fetched PMID records.
- **`premura-mcp-operator --ack`** - a lower-guarantee expert fallback that adds a raw-SQL escape hatch. It refuses to start without explicit acknowledgement, so it is never the silent default.

For the full `premura` CLI reference and the complete MCP tool inventory, see [OPERATIONS.md](docs/using/OPERATIONS.md). Direct DuckDB and notebook access remain available as expert fallbacks.

Using an agent app other than Claude Code (OpenCode, Codex)? See [AGENT_CLIENTS.md](docs/using/AGENT_CLIENTS.md) for the MCP config recipe per client and what each one reads for skills.

## What asking a question looks like

The first run starts with a short interview. The agent asks what you want to look at (sleep, cardio, stress, labs, an overview), then routes only to directions where live analysis exists; a dead end gets a plain refusal, not an improvised answer. Findings reach you through a narrator role that never diagnoses or names causes. Every answer must pass a blocking audit of that exact draft before you see it. Lifestyle facts (supplements, conditions, habits) are captured one confirmed item at a time, and nothing is silently inferred about you.

## Pointers for your agent

When you hand Premura to an AI agent, point it at the right guide:

- **Operating Premura for you** (running tools on your data, no code edits) → [runtime-agent operating guide](docs/operating/RUNTIME_AGENT.md).
- **Changing Premura's code** in this clone → [`AGENTS.md`](AGENTS.md).
- **Opening a pull request** (human or agent) → development setup, checks, and the PR workflow live in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache License 2.0 - see [`LICENSE`](LICENSE).
