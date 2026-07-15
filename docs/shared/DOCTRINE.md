# premura — Product Doctrine

> Status: authoritative. Source of truth for the product's operational stance and intended beneficiary.
>
> Companion to [SPEC.md](SPEC.md), [USERJOURNEY.md](../using/USERJOURNEY.md), and [STAGES.md](../building/architecture/STAGES.md).

## Core statement

Premura is a local-first, agent-operable health reasoning substrate built to help a human understand their own data.

The agent is the primary operational client. The human is the primary beneficiary.

## In one paragraph

The human brings the source artifacts, states the question or goal, and approves sensitive actions. The agent does most of the operational work: ingesting, normalizing, selecting signals, analyzing, comparing, explaining, and proposing extensions. Premura is therefore agent-first in execution, but human-first in purpose. If the human is not being helped, taught, or guided, the system has missed its point.

## Consequences

1. The default runtime path is **agent-mediated**, not direct SQL or dashboard use.
2. Human-facing teaching and explanation are not optional garnish; they are part of the product's reason to exist.
3. Direct DuckDB, notebook, and raw CLI analysis remain available as **expert fallback** paths.
4. MCP and other tool surfaces are first-class product interfaces, not side integrations.
5. Plug-ins and integrations are primarily for **agents building or adapting the system for a human user's real artifacts and needs**.
6. The human remains on the loop: they supply data, goals, policy, and approvals. The agent runs most inner steps.
7. Deterministic tool boundaries matter because the agent must be inspectable, reproducible, and honest in a health context.
8. **Stable profile facts are captured through an agent-mediated bounded interview, not a human-filled form.** A small closed allowlist of baseline attributes (today `birth_date`, `sex`, `standing_height_cm`) is recorded one fact at a time through the agent surface against that allowlist. Anything outside it — including derived values like `age` — is refused at the store boundary rather than written. There is no general profile form and no open attribute bucket.
9. **New nutrition/supplement source support arrives by the parser/plugin path, not by a built-in importer.** Bulk consumption data lands through the same federated-parser seam as the wearable sources. The system does not ship (and does not assume) a built-in MyFitnessPal-style importer, label scanner, or supplement catalog as the default way to get intake data in.

10. **Design a level above the concrete case.** Because agents extend Premura, its specs, contracts, and docs are written as guided abstractions, not exhaustive enumerations. See the next section.

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

## Capture and source support

Two write paths exist for the personal-context and intake domains, and they have deliberately different shapes:

- **Baseline profile context** is captured by the agent through a bounded interview. The supported attributes are a small, closed allowlist (`birth_date`, `sex`, `standing_height_cm` today); the agent records one fact at a time, each new value supersedes the prior one while history is kept, and unsupported or derived keys (such as `age`) are rejected. This is _agent-mediated capture_, not a human form, and not an open attribute store.
- **Nutrition and supplement consumption** is bulk data that arrives through the **parser/plugin path** — the same federated-parser seam the wearable sources use. The warehouse now has concrete homes for this data, but turning a specific source (a meal-logging app export, a supplement log) into those rows is follow-on parser work, not a built-in importer that already ships.

The point of stating this explicitly: earlier planning kept drifting back into "the human fills out a form" and "we'll add a built-in nutrition importer." Both are wrong defaults. Capture is agent-mediated; new source support is parser/plugin work.

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
