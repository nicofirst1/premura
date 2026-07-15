# premura — Agent Client Setup

> Reference for connecting a coding-agent app to Premura by hand. Written for a human to read.
>
> Most people do not need this page. The normal way to connect is one command - see [the README quick start](../../README.md#quick-start). This page covers the two things that command deliberately does not do: registering the raw-SQL **operator** server, and getting skills to **Codex**.

## The one-command install (what you normally do)

```bash
uvx --from git+https://github.com/nicofirst1/premura premura install-client claude   # or: opencode | codex
```

This registers the default, validity-gated `premura-mcp` server with the app, editing its config file for you. Re-running it changes nothing (it is idempotent). It only ever registers the safe default server - never the operator server below. If you would rather edit config by hand, or you use an app not listed above, the manual recipe is the same three facts every MCP app needs: a server name (`premura`), a launch command (`uvx --from git+https://github.com/nicofirst1/premura premura-mcp`), and optionally `PREMURA_DATA_DIR` if your warehouse is not in the default location. See [ADR 0016](../building/adr/0016-one-command-install-uvx-and-durable-data-dir.md) for why the launch command is portable and where data lives.

## The operator server (manual only, on purpose)

The operator server (`premura-mcp-operator`) adds a raw-SQL tool with no quality checks. `install-client` never registers it, and you should only add it deliberately, knowing the risk (see [OPERATIONS.md](OPERATIONS.md#the-two-mcp-servers)). It refuses to start unless you pass `--ack`. To add it by hand:

**Claude Code:**

```bash
claude mcp add --transport stdio premura-operator -- uvx --from git+https://github.com/nicofirst1/premura premura-mcp-operator --ack
```

**OpenCode** (`opencode.json`):

```json
{
  "mcp": {
    "premura-operator": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/nicofirst1/premura", "premura-mcp-operator", "--ack"],
      "enabled": true
    }
  }
}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.premura-operator]
command = "uvx"
args = ["--from", "git+https://github.com/nicofirst1/premura", "premura-mcp-operator", "--ack"]
```

## Skills per client

`premura bootstrap` installs Premura's bundled skills under `.claude/skills/`. **Claude Code and OpenCode both read that directory**, so one install serves both.

**Codex does not read `.claude/skills/`.** It reads `AGENTS.md` at the repo root instead, and this repo's `AGENTS.md` already points to the relevant `SKILL.md` files by path. So Codex gets the same guidance as a doc reference rather than an auto-loaded skill - no extra step needed today.

## Working in a clone (developers)

If you have cloned the repo and want your local edits to run, replace `uvx --from git+... premura-mcp` with `uv run premura-mcp` everywhere above (and `uv run premura install-client ...` for the install command).

## Verifying a connection

Confirm the server starts before trusting it:

```bash
uvx --from git+https://github.com/nicofirst1/premura premura-mcp   # starts and waits on stdin; Ctrl-C to stop
```

Then, from the client itself, ask it to list its available tools and confirm Premura's tools appear.
