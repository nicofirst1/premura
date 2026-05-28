# MCP + age Spike

Status: completed 2026-05-23.

## Question

Can Premura expose the warehouse through an existing DuckDB MCP server while preserving Premura's existing `age` protection for exported artifacts?

## Result

No direct path exists for a `*.duckdb.age` file. DuckDB opens the file path it is given, so an MCP server such as `mcp-server-duckdb` immediately fails when pointed at age ciphertext. A workable fallback does exist: decrypt the warehouse into a RAM-backed mount, open that plaintext DuckDB path in read-only mode, then tear the mount down after the MCP session. Premura's chosen default boundary is simpler: keep the working warehouse as the normal local DuckDB file, open it read-only for MCP, and continue using `age` for exported artifacts and any upload path.

## Evidence

Direct open fails because the ciphertext is not a DuckDB file:

```bash
uv run python -c "import duckdb; con=duckdb.connect('test.duckdb'); con.execute('create table t(i integer); insert into t values (1), (2)'); con.close()"
age -R ~/.config/premura/recipients.txt -o test.duckdb.age test.duckdb
uv run python -c "import duckdb; duckdb.connect('test.duckdb.age', read_only=True)"
```

Observed failure:

```text
_duckdb.IOException: IO Error: The file ".../test.duckdb.age" exists, but it is not a valid DuckDB database file!
```

Decrypting to a RAM-backed mount works:

```bash
dev=$(hdiutil attach -nomount ram://32768)
diskutil erasevolume HFS+ premura-m1 "$dev"
age -d -i ~/.config/premura/age.key -o /Volumes/premura-m1/test.duckdb test.duckdb.age
uv run python -c "import duckdb; con=duckdb.connect('/Volumes/premura-m1/test.duckdb', read_only=True); print(con.execute('select sum(i) from t').fetchone()[0]); con.close()"
hdiutil detach "$dev"
```

Observed result:

```text
3
```

## Recommendation

- M2 should point the MCP server at the local warehouse path in read-only mode.
- Keep `age` encryption at the export and upload boundary.
- Do not point MCP at `*.age` artifacts directly.
- Keep the RAM-disk flow as an optional stricter fallback, not the default architecture.
