# premura — Operations

> How to run premura day to day, and the two MCP servers. Written for a human to read.
>
> See also: [../README.md](../../README.md) for first-time setup, [STATUS.md](../shared/STATUS.md) for what currently works.

## The commands

Run `premura --help` for the full list of commands and what each one does. On a fresh clone, put `uv run` in front (so `uv run premura status`). The walkthrough below covers the everyday flow.

### A typical run

1. Put your export files into `data/inbox/` - Health Connect `.db`, Garmin GDPR `.zip`, Sleep as Android / BMT / Withings `.csv`, or lab files.
2. Run `premura ingest`. It finds and loads every supported file automatically.
3. Run `premura status` to confirm the new rows arrived.
4. When you want a backup, run `premura export --month YYYY-MM`, then `premura upload --month YYYY-MM` if you want it on Drive.

### Lab files (PDFs)

Reading real lab PDFs needs an extra local package. Install it once with `uv sync --extra lab`. Then `premura ingest --source lab PATH` will extract them. (Stool-report PDFs on Apple Silicon use a separate package: `uv sync --extra lab-vlm`.)

## The two MCP servers

An MCP server is how your coding agent talks to premura's data. There are two, and the difference is a safety one.

### `premura-mcp` — the standard server

This is the one your agent should use, and the one `install-client` connects. Every question it answers goes through a quality check first: is this metric fresh enough, is there enough data to say anything, is the evidence admissible for this question. If not, it tells you plainly that it can't answer, rather than guessing. It cannot run raw database queries at all.

```bash
uv run premura-mcp
```

By default it finds your warehouse at `PREMURA_DATA_DIR/duck/health.duckdb`. Add `--warehouse-path /path/to/health.duckdb` to point it elsewhere. It is safe to connect to your agent automatically.

### `premura-mcp-operator` — the expert server

This is the standard server plus one extra tool, `query_warehouse`, which runs raw SQL that you write, directly against the database, with none of the quality checks above. That makes it powerful and easy to misuse: a careless query can return stale or mis-joined rows that look like facts. Use it only when you need something the standard tools genuinely cannot answer.

Because of that risk it is fenced off two ways: the raw-SQL tool does not exist on the standard server at all, and this server refuses to start unless you explicitly acknowledge the risk:

```bash
uv run premura-mcp-operator --ack
```

Never connect this server to an agent automatically. For how an agent should use these servers responsibly on your behalf, see [RUNTIME_AGENT.md](../operating/RUNTIME_AGENT.md).

## Querying the database directly

If you want to explore the data yourself with SQL, open it read-only:

```bash
duckdb -readonly data/duck/health.duckdb
```

Notebooks work the same way. Keep it read-only - premura's own commands are the only thing that should ever write to the warehouse.
