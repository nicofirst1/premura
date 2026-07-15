# premura — Product Doctrine

> Status: authoritative. Source of truth for the product's operational stance and intended beneficiary.
>
> Companion to [SPEC.md](SPEC.md), [USERJOURNEY.md](../using/USERJOURNEY.md), and [STAGES.md](../building/architecture/STAGES.md).

## Core statement

Premura is a local-first, agent-operable health reasoning substrate built to help a human understand their own data.

The agent is the primary operational client. The human is the primary beneficiary.

## In one paragraph

The human brings the source artifacts, states the question or goal, and approves sensitive actions. The agent does most of the operational work: ingesting, normalizing, selecting signals, analyzing, comparing, explaining, and proposing extensions. Premura is therefore agent-first in execution, but human-first in purpose. If the human is not being helped, taught, or guided, the system has missed its point. MCP and other tool surfaces are the product's first-class interfaces; direct DuckDB, notebook, and CLI analysis remain available as an expert fallback.

## Design altitude: guide, don't enumerate

Premura is extended by agents, so its specs, contracts, and docs must be written **a level above** the concrete case. Provide bounded extension points — registries, rubrics, contracts, allowlists-with-rules — that an agent fills in. Do **not** enumerate the full set of domains, metrics, questions, or policies and call that the design.

The test, applied at specify/plan time and again at review:

> **Does this artifact hardcode a list where it should define the rule for adding to the list?**

The two failure modes, in the maintainer's words:

- **Too broad / under-specified** → "the agents will end up creating their own custom conventions and then PR becomes impossible."
- **Too narrow / over-enumerated** → "the agent might decide it's too strict and limiting and come up with their own solution anyway, or violate the boundaries."

The target is the middle: _guide agents to create their own policies; don't strictly limit them, but don't give so much freedom that they invent random stuff._ When you catch yourself listing every domain, metric, question, or policy, stop and define the abstraction that lets an agent add the next one correctly without a central edit.

**Right (a level above):** the federated parser seam — a `PluginParser` contract, a fixed `suggest_metric()` resolution order, and an `unmapped_metrics` surface — so any agent can add a vendor without anyone editing a central list. **Wrong (enumerated):** an `if source == "garmin" … elif source == "fitbit" …` ladder, or a spec that lists every supported metric instead of the rule for admitting a new one.

## Docs altitude: separate the audiences

Premura is roughly **agent-first in execution, human-first in purpose** ("~80% for agents, 20% for humans"). Documentation must keep three audiences distinct rather than blur them into one developer-facing voice (tracked in issue #8):

- **Human using the app** — what it is, how to point an agent at their data. (README, top of `AGENTS.md`.)
- **Agent operating/extending the repo** — the contracts, rubrics, and this doctrine. (`AGENTS.md` router → `CONTEXT.md`, `DOCTRINE.md`, contracts.)
- **Contributor (human or agent) opening a PR** — how to extend correctly. (`CONTRIBUTING.md`, parser contract.)

Building and using a parser for the operator's own data is part of operating an installed Premura: at runtime an agent may build a parser and use it immediately for the operator's own data, with no reviewer. Review enters only if the human consents to contribute that parser back — the PR (the contributor audience above), not the local use, goes through the existing development/review process.

**Single home per shipped-state fact.** A count or inventory of what is shipped (tool counts, signal lists, test totals) has exactly one home — its live source in the code (`premura --help`, `premura status`, `engine.list_*()`, the pinned inventory tests) — and docs link there or omit it rather than restating it; a restated count is a future stale count. Mission narratives are append-only entries in [CHANGELOG.md](CHANGELOG.md). The self-check, applied whenever a doc is written or reviewed alongside the altitude test above: _does this doc restate a fact that already has a home?_

## What Premura is not

- Not a dashboard-first product.
- Not a pure warehouse that expects the human to do all meaningful analysis directly.
- Not a fully autonomous health actor that removes the human from oversight.
- Not a consumer mobile app.
- Not a form-first product: baseline profile facts are captured through an agent-mediated bounded interview against a closed allowlist, not by handing the human a profile form to fill in.
- Not a built-in-importer product: it does not bundle a MyFitnessPal-style nutrition importer or supplement catalog. New consumption sources are adapted through parser/plugin work.

## Default workflow

1. Human exports or downloads the source artifacts.
2. Human points Premura or an attached agent at the artifacts.
3. Human asks a question, names a concern, or states a goal.
4. Agent ingests, normalizes, analyzes, and explains through deterministic tools.
5. Human reviews the result, asks follow-ups, and approves any sensitive next step.

## Doc rule

When a top-level product doc has to choose what to emphasize, prefer this framing:

- **Primary runtime client**: agent
- **Primary beneficiary**: human
- **Default interface**: agent-mediated tool use
- **Fallback interface**: direct human expert analysis
