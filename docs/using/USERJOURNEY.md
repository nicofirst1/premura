# premura — User Journey

> Status: authoritative. Source of truth for the **intended human experience over time**.
>
> Companion to [DOCTRINE.md](../shared/DOCTRINE.md) (product stance), [SPEC.md](../shared/SPEC.md) (what the system must do), and [STATUS.md](../shared/STATUS.md) (what works today). Per DOCTRINE, the human is the primary beneficiary; the agent is the default operational client. The human supplies data, goals, and approvals - the agent operates the pipeline and explains findings.

## Persona

Single user, single subject, single operator. EU resident (GDPR jurisdiction applies). Wears wearables and logs measurements across a few apps that each silo their own data. Wants a durable, private, queryable union of that data - and does **not** want to build an app, run a server, pay a SaaS, or depend on a third-party bridge that could disappear.

The human does not have to be a terminal or SQL user. Anyone who can install a tool and talk to a coding agent can operate premura; expert direct-warehouse access stays available but is never the required path.

## The arc

Everything below is one continuous flow. The human is interviewed, then guided, then answered - they never hand-run the pipeline.

1. **Install once.** One command registers premura's default (validity-gated) MCP surface with whatever coding-agent harness the human already uses. The human reads no config. The raw-SQL operator surface is never auto-registered - it stays behind a deliberate step.
2. **Launch with `/premura`** in that harness (Claude Code, OpenCode, Codex, …).
3. **Interview - what to know.** The session opens by asking what the human wants to understand about their health. Each direction resolves to real analysis behind it; a direction with nothing to answer it is refused, not offered, so the interview never dead-ends. (Open registry, not a fixed menu - see DOCTRINE rule 2.)
4. **Interview - what data exists.** The agent inventories what devices and exports the human has and guides collection toward only the sources premura can actually parse (same never-a-dead-end rail, keyed on registered parsers). "Android → enable bedtime mode → sleep data"; "Garmin → here's the GDPR export."
5. **Data flows in, analysis follows.** The agent ingests what the human provides, then answers questions against the unified warehouse through the grounded MCP tools - explaining what it found, what's missing, and what to look at next. The human decides whether to continue, correct, or approve any sensitive step.

### Refresh cadence

Wearable/app data is refreshed by the human dropping new exports when they have them - some sources (notably Garmin's GDPR export) can only be requested manually, by policy. The agent ingests idempotently, so re-dropping the same export is safe. There is no live/real-time path by design.

### Expert fallback (not the default)

The warehouse is local DuckDB and stays directly queryable for a human who wants raw SQL, notebooks, or custom analysis outside the grounded tool surface. Analysis is read-only by convention (`read_only=True`) whoever the caller is - the pipeline owns writes.

## Durability and recovery (the "why local" story)

The human is the custody-of-record holder of the `age` private key. No vendor, no escrow, no recovery service - lose the key and the encrypted history is gone. In exchange, the story survives anything: the encrypted Drive snapshot + the age key + this repo are sufficient to rebuild.

Catastrophic recovery (new machine, ~30 min): install the tools, restore `~/.config/premura/age.key` from a password manager, reconnect the Drive remote, clone the repo, fetch the latest encrypted snapshot, `age -d` it back into place, and verify with `premura doctor`. Recovery depends on none of the source vendors staying online or unchanged.

## Anti-journeys (deliberately not optimized for)

- **"Show me my data on my phone."** Out of scope - use the source apps; premura is the union-and-analysis layer.
- **"Push corrections back into the source apps."** Out of scope - no documented import path.
- **"Real-time alerts."** Out of scope by design - refresh is human-paced, not live.
- **"Share my data with X."** Single-subject system; sharing is a separate, human-approved act, not a default flow.

## Implicit user contract

By using premura the human accepts: they hold the `age` key and no one can recover it for them; refresh is manual and human-paced, not live; some source exports (Garmin GDPR) can only be requested by hand; and a source changing its format can drift a parser - the fix is to patch the parser and let ingest catch up.
