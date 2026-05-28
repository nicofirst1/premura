# premura — Product Doctrine

> Status: authoritative. Source of truth for the product's operational stance and intended beneficiary.
>
> Companion to [SPEC.md](SPEC.md), [../history/product/VISION.md](../history/product/VISION.md), [USERJOURNEY.md](USERJOURNEY.md), [STAGES.md](../architecture/STAGES.md), and [STATUS.md](../operations/STATUS.md).

## Core statement

Premura is a local-first, agent-operable health reasoning substrate built to help a human understand their own data.

The agent is the primary operational client.
The human is the primary beneficiary.

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

## What Premura is not

- Not a dashboard-first product.
- Not a pure warehouse that expects the human to do all meaningful analysis directly.
- Not a fully autonomous health actor that removes the human from oversight.
- Not a consumer mobile app.
- Not a form-first product: baseline profile facts are captured through an agent-mediated bounded interview against a closed allowlist, not by handing the human a profile form to fill in.
- Not a built-in-importer product: it does not bundle a MyFitnessPal-style nutrition importer or supplement catalog. New consumption sources are adapted through parser/plugin work.

## Capture and source support

Two write paths exist for the personal-context and intake domains, and they have deliberately different shapes:

- **Baseline profile context** is captured by the agent through a bounded interview. The supported attributes are a small, closed allowlist (`birth_date`, `sex`, `standing_height_cm` today); the agent records one fact at a time, each new value supersedes the prior one while history is kept, and unsupported or derived keys (such as `age`) are rejected. This is *agent-mediated capture*, not a human form, and not an open attribute store.
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
