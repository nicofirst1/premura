# premura — Agent Client Setup

> Status: live reference. How to point a coding-agent app at Premura's MCP surfaces and skills.
>
> Companion to [OPERATIONS.md](OPERATIONS.md) (the MCP tool inventory) and [../operating/RUNTIME_AGENT.md](../operating/RUNTIME_AGENT.md) (how an agent should behave once connected).

Premura's client-surface direction is text-through-coding-agents, and the agent talks to Premura over MCP — so supporting another agent app is a setup recipe, not new architecture (see [DOCTRINE.md](../shared/DOCTRINE.md) rule 2). This page states the one recipe pattern once, then gives the per-client config delta for each agent app in current use. Adding a new client app means adding one more delta section here, not a new doc.

## The recipe pattern

Every MCP-capable agent app needs the same three facts to register Premura as a tool server:

1. **A server name** — `premura` (or `premura-operator` if you also register the operator surface).
2. **A launch command + args** — one of:
   - `uv run premura-mcp` — the default, validity-gated surface. Safe to register by default.
   - `uv run premura-mcp-operator --ack` — the operator fallback surface. It **refuses to start without `--ack`** (or `PREMURA_OPERATOR_ACK=1`), so never register it without the flag, and treat registering it at all as a deliberate, user-approved step — see [OPERATIONS.md](OPERATIONS.md#operator-fallback-surface-premura-mcp-operator).
3. **Optional env / working directory** — `PREMURA_DATA_DIR` if the warehouse isn't at the default location, or pass `--warehouse-path /absolute/path/to/health.duckdb` as an extra arg instead.

Each client below just spells those three facts in its own config syntax. Run the commands from the repo root (or an installed Premura checkout) so `uv run` resolves the project environment.

## Claude Code

Project-scoped, shared via version control: add to `.mcp.json` at the repo root —

```json
{
  "mcpServers": {
    "premura": {
      "command": "uv",
      "args": ["run", "premura-mcp"]
    }
  }
}
```

Or register it from the CLI (writes to the same project scope):

```bash
claude mcp add --transport stdio premura -- uv run premura-mcp
```

Operator surface, same pattern with the required flag:

```bash
claude mcp add --transport stdio premura-operator -- uv run premura-mcp-operator --ack
```

Claude Code prompts for approval on project-scoped `.mcp.json` servers the first time you trust the workspace — see the [MCP reference](https://code.claude.com/docs/en/mcp) for scopes and approval details.

## OpenCode

Add to `opencode.json` (project root) or `~/.config/opencode/opencode.json` (user scope):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "premura": {
      "type": "local",
      "command": ["uv", "run", "premura-mcp"],
      "enabled": true
    }
  }
}
```

Operator surface: same shape, `"command": ["uv", "run", "premura-mcp-operator", "--ack"]`.

## Codex

Add a `[mcp_servers.<name>]` table to `~/.codex/config.toml`:

```toml
[mcp_servers.premura]
command = "uv"
args = ["run", "premura-mcp"]
```

Operator surface:

```toml
[mcp_servers.premura-operator]
command = "uv"
args = ["run", "premura-mcp-operator", "--ack"]
```

## Skills story per client

`premura install-skills` (run by `premura bootstrap`) materializes every shipped skill under the single home `.claude/skills/` — that one target is a deliberate decision, not an oversight (see [ROADMAP.md](../shared/ROADMAP.md), 2026-06-12 entry): **Claude Code and OpenCode both read `.claude/skills/` directly**, so one install target already serves both.

**Codex reads something different.** It does not read `.claude/skills/`; its own skill-directory convention is `.agents/skills`, which Premura does not populate. What Codex _does_ always read is `AGENTS.md` at the repo root — and this repo's `AGENTS.md` is already written as a router that explicitly points to the relevant `SKILL.md` files by path (for example, "If you are using Claude Code to generate a parser, also read `src/premura/skills/parser-generator/SKILL.md`"). That gives Codex the same guidance as a skill, delivered as a doc reference instead of an auto-loaded skill package — no second `install-skills` target needed today.

If an operator later needs Codex to auto-load skills natively via `.agents/skills` (rather than following the `AGENTS.md` pointer), that is new installer behavior, not a docs fix — file it as its own issue instead of building it here.

## Verifying a connection

Whatever client you configured, confirm the tool list loads before trusting it:

```bash
uv run premura-mcp   # should start and stay running (it waits silently on stdin); Ctrl-C to stop
```

Then, from the client itself, ask it to list available tools and confirm the default-surface tool names from [OPERATIONS.md](OPERATIONS.md#default-agent-facing-surface-premura-mcp) appear.
