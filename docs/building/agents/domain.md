# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- `CONTEXT.md` at the repo root, if it exists.
- `docs/building/adr/`, reading ADRs relevant to the area being changed.
- If `CONTEXT-MAP.md` is later added at the repo root, treat the repo as multi-context and follow it to the relevant per-context `CONTEXT.md` files.

If any of these files do not exist, proceed silently. Do not suggest creating them up front.

## File structure

Single-context layout for this repo:

```text
/
├── CONTEXT.md
├── docs/building/adr/
└── src/
```

## Use the glossary's vocabulary

When naming a domain concept in an issue, proposal, hypothesis, or test, use the terms defined in `CONTEXT.md` when present.

## Flag ADR conflicts

If a proposed change contradicts an existing ADR, surface that conflict explicitly instead of silently overriding it.
