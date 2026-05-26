# premura — Product Doctrine

> Status: authoritative. Source of truth for the product's operational stance and intended beneficiary.
>
> Companion to [SPEC.md](SPEC.md), [VISION.md](VISION.md), [USERJOURNEY.md](USERJOURNEY.md), [STAGES.md](../architecture/STAGES.md), and [STATUS.md](../operations/STATUS.md).

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

## What Premura is not

- Not a dashboard-first product.
- Not a pure warehouse that expects the human to do all meaningful analysis directly.
- Not a fully autonomous health actor that removes the human from oversight.
- Not a consumer mobile app.

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
