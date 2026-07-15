# premura — Agent Client Setup

> Status: live reference. How to point a coding-agent app at Premura's MCP surfaces and skills.
>
> Companion to [OPERATIONS.md](OPERATIONS.md) (the MCP tool inventory) and [../operating/RUNTIME_AGENT.md](../operating/RUNTIME_AGENT.md) (how an agent should behave once connected).

Premura's client-surface direction is text-through-coding-agents, and the agent talks to Premura over MCP — so supporting another agent app is a setup recipe, not new architecture (see [DOCTRINE.md](../shared/DOCTRINE.md) rule 2). This page states the one recipe pattern once, then gives the per-client config delta for each agent app in current use. Adding a new client app means adding one more delta section here, not a new doc.

## The recipe pattern

Every MCP-capable agent app needs the same three facts to register Premura as a tool server:

1. **A server name** — `premura` (or `premura-operator` if you also register the operator surface).
2. **A launch command + args** — one of:
   - `uvx --from git+https://github.com/nicofirst1/premura premura-mcp` — the default, validity-gated surface. This is the **portable** form: uvx fetches and runs it straight from the public repo, so it needs no clone and no PyPI publish (uv is the only prerequisite). Safe to register by default. Pin a release with `@vX.Y.Z` on the URL for reproducibility. _Working in a clone?_ Use `uv run premura-mcp` instead, which runs your local edits.
   - `uvx --from git+https://github.com/nicofirst1/premura premura-mcp-operator --ack` — the operator fallback surface. It **refuses to start without `--ack`** (or `PREMURA_OPERATOR_ACK=1`), so never register it without the flag, and treat registering it at all as a deliberate, user-approved step — see [OPERATIONS.md](OPERATIONS.md#operator-fallback-surface-premura-mcp-operator).
3. **Optional env / working directory** — the warehouse defaults to a durable XDG path (`$XDG_DATA_HOME/premura`), independent of where the server is launched from; set `PREMURA_DATA_DIR` only to point at a non-default location (see [ADR 0016](../building/adr/0016-one-command-install-uvx-and-durable-data-dir.md)).

**The one-command path.** `premura install-client <client>` does the config merge for you — no hand-editing — and can itself run without a clone:

```bash
uvx --from git+https://github.com/nicofirst1/premura premura install-client claude   # or: opencode | codex
```

It writes the portable entry the manual recipes below spell out, idempotently (re-running is a no-op). By design it only ever registers the default `premura-mcp` surface; the operator surface stays a deliberate manual step (its recipes below). Each client below spells the same three facts in its own config syntax — the manual snippets remain as reference for what gets written and for the operator surface.

## Claude Code

Register it from the CLI (no clone needed):

```bash
claude mcp add --transport stdio premura -- uvx --from git+https://github.com/nicofirst1/premura premura-mcp
```

Or write `.mcp.json` at the repo root directly (project-scoped, shared via version control):

```json
{
  "mcpServers": {
    "premura": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nicofirst1/premura", "premura-mcp"]
    }
  }
}
```

Operator surface, same pattern with the required flag (deliberate, manual only):

```bash
claude mcp add --transport stdio premura-operator -- uvx --from git+https://github.com/nicofirst1/premura premura-mcp-operator --ack
```

_Developing in a clone?_ Swap the command for `uv run premura-mcp` to run your local edits.

Claude Code prompts for approval on project-scoped `.mcp.json` servers the first time you trust the workspace — see the [MCP reference](https://code.claude.com/docs/en/mcp) for scopes and approval details.

## OpenCode

Add to `opencode.json` (project root) or `~/.config/opencode/opencode.json` (user scope):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "premura": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/nicofirst1/premura", "premura-mcp"],
      "enabled": true
    }
  }
}
```

Operator surface: same shape, appending `"premura-mcp-operator", "--ack"` in place of `"premura-mcp"`. Clone dev: `["uv", "run", "premura-mcp"]`.

## Codex

Add a `[mcp_servers.<name>]` table to `~/.codex/config.toml`:

```toml
[mcp_servers.premura]
command = "uvx"
args = ["--from", "git+https://github.com/nicofirst1/premura", "premura-mcp"]
```

Operator surface (deliberate, manual only):

```toml
[mcp_servers.premura-operator]
command = "uvx"
args = ["--from", "git+https://github.com/nicofirst1/premura", "premura-mcp-operator", "--ack"]
```

Clone dev: `command = "uv"`, `args = ["run", "premura-mcp"]`.

## Skills story per client

`premura install-skills` (run by `premura bootstrap`) materializes every shipped skill under the single home `.claude/skills/` — that one target is a deliberate decision, not an oversight: **Claude Code and OpenCode both read `.claude/skills/` directly**, so one install target already serves both.

**Codex reads something different.** It does not read `.claude/skills/`; its own skill-directory convention is `.agents/skills`, which Premura does not populate. What Codex _does_ always read is `AGENTS.md` at the repo root — and this repo's `AGENTS.md` is already written as a router that explicitly points to the relevant `SKILL.md` files by path (for example, "If you are using Claude Code to generate a parser, also read `src/premura/skills/parser-generator/SKILL.md`"). That gives Codex the same guidance as a skill, delivered as a doc reference instead of an auto-loaded skill package — no second `install-skills` target needed today.

If an operator later needs Codex to auto-load skills natively via `.agents/skills` (rather than following the `AGENTS.md` pointer), that is new installer behavior, not a docs fix — file it as its own issue instead of building it here.

## Verifying a connection

Whatever client you configured, confirm the tool list loads before trusting it:

```bash
# no clone:
uvx --from git+https://github.com/nicofirst1/premura premura-mcp   # starts and waits silently on stdin; Ctrl-C to stop
# in a clone: uv run premura-mcp
```

Then, from the client itself, ask it to list available tools and confirm the default-surface tool names from [OPERATIONS.md](OPERATIONS.md#default-agent-facing-surface-premura-mcp) appear.
