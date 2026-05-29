# Quickstart: Stage 2 Evidence Admissibility Foundation

This quickstart explains how a future agent should approach implementation after `/spec-kitty.tasks` creates work packages.

## 1. Keep The Boundary Clear

This is Stage 2 work.

- Do not add Stage 3 MCP tools.
- Do not call PubMed or any network service at runtime.
- Do not add diagnosis, treatment advice, medication advice, or population-norm interpretation.
- Do not broadly refactor existing signals unless a work package explicitly scopes one proof integration.

## 2. Start Test-First

Before implementation, write failing tests for the behavior in the work package.

Minimum behavior to cover across the mission:

- invalid declaration fails early
- unknown question type fails clearly
- stale evidence is rejected for current status
- sparse evidence becomes insufficient for trend
- missing timestamp is rejected or insufficient, not silently used
- wrong evidence kind is rejected for the selected question
- no admissible evidence produces a refusal
- admissible and rejected evidence stay separate

## 3. Implement The Declaration Surface

Use frozen Python dataclasses and closed enums.

Do not implement policy declarations as YAML unless the mission is explicitly amended.

Do not let declarations contain expressions, conditions, executable callbacks, SQL, or network calls. Declarations are parameters only. The evaluator owns branching.

## 4. Implement Representative Policy Declarations

Cover at least 10 metric families or explicit family groups by assigning them to a smaller number of reusable evidence-rule shapes.

Representative family groups should include examples from the research note, such as acute spot measures, serial short-run averages, rolling recent patterns, long-term control markers, sparse labs, slow trajectory metrics, method-sensitive body composition, sleep metrics, HRV/resting-HR style recovery metrics, activity metrics, and stable profile facts.

## 5. Keep PubMed In The Review Loop Only

If an agent uses PubMed MCP to justify a policy choice, record the settled rationale in the declaration or implementation note. Do not make Stage 2 fetch literature.

## 6. Verify

Run the relevant quality gates for the changed scope:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

If pre-existing failures appear outside the changed scope, report them rather than hiding them.
