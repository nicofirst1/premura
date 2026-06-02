# Premura

Local-first, agent-operable health reasoning substrate. A human supplies health-data exports, questions, and approvals; agents ingest, normalize, analyze, compare, and explain through deterministic tools over a single DuckDB warehouse. The system captures the metrics Health Connect does not bridge (HRV rMSSD overnight, stress, body battery, training load/readiness, VO₂ max, etc.) while keeping encrypted export and backup artifacts under the human user's control.

This page is the human/operator landing page: what Premura is, how to run it
locally, and where to go next. You do not need the planning or history docs to
start.

> **Who are you?**
> - **Operating Premura for a human through an agent** (tools, not code edits)? Read the [runtime-agent operating guide](docs/operations/RUNTIME_AGENT.md).
> - **A coding agent dropped into this clone** to change the code? Start with [`AGENTS.md`](AGENTS.md).
> - **A contributor opening a PR**? Start with [`CONTRIBUTING.md`](CONTRIBUTING.md).
> - **Just exploring?** Keep reading, then browse the [docs guide](docs/README.md).

> Docs live in [`docs/`](docs/): [Guide](docs/README.md) · [Doctrine](docs/product/DOCTRINE.md) · [SPEC](docs/product/SPEC.md) · [STATUS](docs/operations/STATUS.md) · [Stages](docs/architecture/STAGES.md) · [Roadmap](docs/product/ROADMAP.md) · [Full Plan](docs/product/FULL_APP_DEVELOPMENT_PLAN.md)

Premura is still pre-`v1`: future release tags use the `v0.x.0` line until all
four stages form a coherent user-facing path. The historical `v1.0.0` tag is a
restore point for the first local-ingest pipeline, not the forward version line.

## Quick start

Fresh clone? An agent (or human) in the repo runs **one setup command first**:

```bash
uv run hpipe bootstrap                      # SETUP ONLY: prepare + verify this local checkout, report reload guidance
```

`uv run` is the entry point because `hpipe` is a console script that only exists
after the package is installed — `uv run` provisions the local environment, then
runs bootstrap, so it works on a brand-new clone (it needs only `uv` on PATH;
absence of `uv` is reported as a bounded prerequisite, not a silent failure).

`uv run hpipe bootstrap` prepares/verifies the local checkout (environment + bundled
skills), tells you whether an agent-session reload is needed, and hands off the
next safe step. It is setup-only — it never ingests data, touches the warehouse,
or uploads anything. Then operate normally:

```bash
bash ops/bootstrap.sh                       # one-time: brew installs, age keypair, optional rclone
uv run hpipe doctor                         # verify environment
# drop inputs into data/inbox/, then:
uv run hpipe run-monthly                    # ingest + encrypt (no auto-upload)
uv run hpipe upload --month YYYY-MM         # OPT-IN — push to Drive only when you say so
```

## age key storage

The `age` private key at `~/.config/premura/age.key` is the single secret. Lose it = lose all encrypted backups. Two recommended options:

1. **Local backed-up file** (Time Machine, external drive). Default.
2. **Bitwarden secure note** — `bootstrap.sh` prints a `bw create item …` recipe you can run after `bw login`. Retrieve later with `bw get notes 'premura age key' > ~/.config/premura/age.key && chmod 600 …`.

## What's in the warehouse

`hp.fact_measurement` (point-in-time) and `hp.fact_interval` (bounded events), joined to `hp.dim_metric` + `hp.dim_source`. See [STATUS.md](docs/operations/STATUS.md) for live row counts and [SPEC.md §5](docs/product/SPEC.md) for the data contract.

Query directly:

```bash
duckdb -readonly data/duck/health.duckdb
```

## Surfaces

Point an agent at your data and let it operate Premura through tools — that is
the default path, not raw SQL:

- **`premura-mcp`** — the default, validity-gated agent surface. Every tool
  delegates to the deterministic signal engine (no raw `hp.*` SQL), and tools
  return structured `available` / `missing_input` / `stale_input` /
  `insufficient_data` verdicts instead of free-form claims. It includes the
  literature tools `pubmed_search` and `pubmed_fetch`: search hits are discovery
  candidates only, and final answers may cite only fetched PMID records.
- **`premura-mcp-operator --ack`** — a lower-guarantee expert fallback that adds
  a raw-SQL escape hatch. It refuses to start without explicit acknowledgement,
  so it is never the silent default.

For the full `hpipe` CLI reference and the complete MCP tool inventory, see
[OPERATIONS.md](docs/operations/OPERATIONS.md). For how an agent should operate
Premura honestly on a human's behalf, see the
[runtime-agent operating guide](docs/operations/RUNTIME_AGENT.md). Direct DuckDB
and notebook access remain available as expert fallbacks. Contributors and
coding agents: development setup, checks, and the PR workflow live in
[`CONTRIBUTING.md`](CONTRIBUTING.md).
