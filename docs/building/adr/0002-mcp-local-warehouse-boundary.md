# Use the local warehouse directly for MCP; keep age for exports and uploads

Premura will use the local DuckDB warehouse directly for Stage 3 MCP access and will keep `age` encryption at the export and upload boundary, not on the live working warehouse file. The M1 spike on 2026-05-23 confirmed that DuckDB cannot open a `*.duckdb.age` artifact directly; although decrypting to a RAM-backed mount works, Premura does not need that extra complexity for the default single-user local workflow because the local machine is already the trusted boundary and off-site artifacts remain age-encrypted.
