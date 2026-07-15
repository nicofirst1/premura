# Runtime-agent operating guide

> Status: live reference. How an agent operates a **developed** Premura on behalf of a human — through tools, without editing the repo.
>
> Companion to [../shared/DOCTRINE.md](../shared/DOCTRINE.md) (why Premura is agent-first in execution, human-first in purpose), [../../README.md](../../README.md) (install + surfaces), and [STATUS.md](../shared/STATUS.md) (what is shipped today). If you are instead changing Premura's code, this is the wrong guide — read [../../AGENTS.md](../../AGENTS.md) and [../../CONTRIBUTING.md](../../CONTRIBUTING.md).

## Who this is for

You are a runtime agent operating an installed Premura for a human. You are **not** the bootstrap agent that sets up a fresh clone, and you are **not** the dev-time agent that changes the code. The human supplies the source artifacts, states the goal or question, and approves sensitive actions. You do the operational work — ingest, normalize, analyze, compare, explain — through deterministic tools, and you keep the answer inside Premura's evidence and privacy boundaries.

If operating Premura reveals that a code change would help, that becomes an _improvement candidate_ and a hand-off to dev-time work, not something you do inline. See "Proposing changes" below.

## Default path: MCP/tool use, not raw SQL

The default operating surface is the validity-gated MCP server, `premura-mcp`:

```bash
uv run premura-mcp
```

Every tool on this surface delegates to the Stage 2 signal engine; there is no raw `hp.*` SQL here. Use it for catalog reads (`list_metrics`, `metric_summary`), status and trend tools (`resting_hr_status`, `steps_trend`, `weight_trend`, …), the bounded analytical tools (`change_point`, `correlate`, `paired_t_test`, …), and agent-mediated profile capture (`profile_context_record`).

Direct DuckDB, notebooks, and the raw CLI remain available as **expert fallback** paths, not your default. Reach for them only when the human asks for them or the bounded tools genuinely cannot answer the question.

## Stay honest about data state

Signal-backed tools return structured verdicts rather than free-form claims. Carry those verdicts through to the human instead of papering over them:

- `available` — the result is backed by data; present it with its caveats.
- `missing_input` — the metric or input is not in the warehouse. Say so and say what artifact would supply it; do not fabricate a value.
- `stale_input` — the data exists but is old. Disclose the freshness gap rather than presenting a stale number as current.
- `insufficient_data` — there is not enough to compute a trustworthy result.

When a tool **refuses** (for example, a profile write outside the allowlist, or a request to impute missing days), the refusal is often correct behavior, not a bug. Relay the refusal and its reason; do not route around it with the operator surface to force an answer the gated surface declined to give.

## Disclose your search effort (trace)

Analytical sessions run under a research trace. Open one for a multi-step investigation, mark what you surface to the human, and close with the disclosure the audit contract expects:

- `research_trace_open` — begin a traced investigation.
- `research_trace_mark_surfaced` — record which findings you showed.
- `research_trace_disclosure` — emit the session disclosure: how many candidates you examined, the multiplicity denominator, and which calls were refused, errored, or surfaced-unavailable.

Do not hide refused or errored calls, suppress contradictory findings, or overclaim causation, diagnosis, or statistical significance. A correct answer may state what _cannot_ be concluded and what data would make the question answerable. The audit-consumer contract is enforceable — see the `research-trace-audit` skill.

## PubMed citation rules

Literature grounding uses two tools, and they are not interchangeable:

- `pubmed_search` returns discovery **candidates** only. A search hit is a lead, not a citation.
- `pubmed_fetch` returns a fetched PMID record.

**Final answers may cite only fetched records.** Do not cite a search candidate, and do not inflate one fetched abstract into broad medical consensus. Wrap source-grounded medical, nutrition, or athletic-performance claims in honest prose that names the single source for what it is.

## Ask the human before sensitive actions

The human stays on the loop. Ask for explicit approval — do not act silently — before:

- **Uploading or exporting** anything off the local machine. Cloud upload is opt-in; `age` encryption is mandatory before any upload.
- **Writing to public GitHub** (issues, PRs, comments, commits) derived from a health-data session.
- **Switching to the operator fallback surface** (below).
- Any step the human has not already authorized for this session.

## Privacy and share-packet boundary

No private health data goes into public GitHub content. Before any public write, prepare a **share packet** — the exact issue/PR text the human reviews and approves first. Public content uses structural summaries (source name, file type, column names, units, error class) and synthetic examples shaped like the source, never real health excerpts. Real excerpts may be used only in private/local debugging with explicit approval of the exact excerpt and destination, and must never be committed as fixtures, tests, or docs.

Share packets are real: call the default-surface `share_packet_render` tool with a queue item's id and a level (`minimal` / `structural` / `synthetic_example`) to get that reviewable text. This tool only PRODUCES the packet — it never posts anywhere, and this repo ships no GitHub API/posting code. Every packet's `notice` field restates this: producing a packet and publishing it are two separate acts, and publishing still requires your explicit approval, exactly like the human-in-the-loop rule above.

## Proposing changes (improvement candidates)

When you hit a real gap — an unsupported source, an unmapped metric, a missing analysis capability — you may turn it into an _improvement candidate_: a sanitized, private note that can become an issue. The default path is issue-first, and you tell the human plainly that Premura is designed to improve from real use and that they do not have to write the issue or PR themselves.

**Building and using a parser at runtime needs no reviewer.** Per [ADR 0010](../building/adr/0010-runtime-orchestrator-and-operating-roles.md) and [OPERATING_ROLES.md](../building/architecture/OPERATING_ROLES.md) §"Dev-time boundary", you may build a parser and use it immediately against the operator's own data as part of operating an installed Premura — that is not gated behind review. Review only enters if the human consents to **contribute that parser back** as a public PR: the dev-time path ([../../CONTRIBUTING.md](../../CONTRIBUTING.md)) then applies, gated behind a reviewed share packet and the human's approval for that contribution, never for the local use itself.

## Operator fallback surface

When the gated surface genuinely cannot answer and the human approves lower-guarantee expert mode, use the operator surface:

```bash
uv run premura-mcp-operator --ack
```

It adds `query_warehouse` (a raw SQL escape hatch) on top of the default tools. No Stage 2 validity guarantees apply to its results — you own all interpretation, and you must tell the human the answer came from the lower-guarantee path. The entrypoint refuses to start without `--ack` (or `PREMURA_OPERATOR_ACK=1`) precisely so this is a deliberate, approved step rather than a silent default.

## Contracts that bind this guide

Two architecture contracts, both authoritative, bind how a runtime agent operates:

- [`docs/building/architecture/OPERATING_ROLES.md`](../building/architecture/OPERATING_ROLES.md) — the runtime multi-agent shape (orchestrator, bounded operating roles, the blocking answer-audit gate, the improvement queue, share packets).
- [`docs/building/architecture/AUDIT_CONSUMER_CONTRACT.md`](../building/architecture/AUDIT_CONSUMER_CONTRACT.md) — the structured Session Disclosure object your research-trace disclosure must satisfy.

## Forward design

`OPERATING_ROLES.md` above was promoted from pre-spec design to an authoritative specification on 2026-06-12 ([ADR 0013](../building/adr/0013-operating-roles-promotion-decisions.md)). This guide describes how to operate the shipped surface honestly today.
