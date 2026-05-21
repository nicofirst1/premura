---
work_package_id: WP03
title: Parser And UI Contract Stubs
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-v2-architectural-skeleton-01KS4SHA
base_commit: d530b084ba4492e8e67bbbfed0462ddcdb7b40c6
created_at: '2026-05-21T12:14:49.060767+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
agent: claude:opus-4-7:reviewer:reviewer
shell_pid: '20147'
history:
- timestamp: '2026-05-21T09:53:12Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/parsers/
execution_mode: code_change
owned_files:
- src/premura/parsers/base.py
- src/premura/parsers/lookup.py
- src/premura/parsers/_lang/**
- src/premura/parsers/CONTRACT.md
- src/premura/mcp/**
- src/premura/ui/**
tags: []
---

# Work Package Prompt: WP03 - Parser And UI Contract Stubs

## Objective

Create the additive parser contract, the agent-facing parser contract document, and the stub packages for Stage 3 (`mcp`) and Stage 4 (`ui`).

This WP is where the future contributor workflow becomes real: parsers have a formal extensibility contract, and the higher-level stages have named homes with explicit layering boundaries.

## Owned Surface

- `src/premura/parsers/base.py`
- `src/premura/parsers/lookup.py`
- `src/premura/parsers/_lang/__init__.py`
- `src/premura/parsers/CONTRACT.md`
- `src/premura/mcp/__init__.py`
- `src/premura/ui/__init__.py`

Do not modify concrete v1 parsers in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP03 --agent <name>`

## Subtasks

### T008 - Append `PluginParseResult` to `parsers/base.py`

**Purpose**

Add the richer federated-parser return type without disturbing the existing v1 parser contract.

**Required changes**

- Append a frozen `PluginParseResult(ParseResult)` dataclass.
- Include the three additive fields:
  - `language_detected: str | None = None`
  - `unmapped_metrics: list[str] = field(default_factory=list)`
  - `confidence: float = 1.0`
- Keep existing `Measurement`, `Interval`, `ParseResult`, and `Parser` unchanged.

**Important**

- This is append-only work in a shared file.
- Do not refactor existing parser types for style.
- Do not alter current dedupe/file-hash behavior.

### T009 - Append `PluginParser` to `parsers/base.py`

**Purpose**

Define the additive structural protocol that future community parsers implement.

**Required changes**

- Add `PluginParser(Parser, Protocol)`.
- Include:
  - `language_hint: str | None`
  - `def declares_metrics(self) -> list[str]: ...`
  - `def parse(self, path: Path) -> PluginParseResult: ...`
- Keep the existing `Parser` protocol untouched.

**Compatibility rule**

- Existing v1 parsers must remain valid against the original `Parser` protocol with no migration in this mission.

### T010 - Create `parsers/lookup.py`

**Purpose**

Reserve the ontology lookup location that future parser-generation work calls first.

**Required changes**

- Create `src/premura/parsers/lookup.py`.
- Add a module docstring describing the future reverse-index behavior over canonical IDs and aliases.
- Add `suggest_metric(field_name: str) -> str | None` stub that raises `NotImplementedError`.

**Keep it focused**

- No real YAML loading.
- No alias index building.
- No fallback logic in this mission.

### T011 - Create `parsers/_lang/__init__.py`

**Purpose**

Reserve the local-only language detection/translation boundary for future parser work.

**Required changes**

- Create `src/premura/parsers/_lang/__init__.py`.
- Add a docstring that explicitly contains `"local-only"`.
- Document that translation is a TODO and no external API calls are allowed.
- Add `detect_language(text: str) -> str` stub raising `NotImplementedError`.

**Constraint**

- Do not add dependencies such as `langdetect`, `pycld3`, or translation libraries in this mission.

### T012 - Create `parsers/CONTRACT.md`

**Purpose**

Ship the authoritative agent-facing parser contract inside the package.

**Required content**

- Explain the `PluginParser` and `PluginParseResult` symbols.
- Encode the standards-first decision tree in this order:
  1. existing alias,
  2. LOINC for labs,
  3. IEEE 1752.1 for wearables,
  4. bare English canonical name for reusable concepts,
  5. `vendor:*` fallback for source-specific concepts.
- State that aliases must be clinically standard names/abbreviations only.
- State that `derived:*` is reserved for engine outputs and parsers must not emit it.
- Describe the same-PR expectation for parser code + ontology additions.

**Authoritative source**

- Use the planning contract doc as the reference, but materialize the shipped file at `src/premura/parsers/CONTRACT.md`.

### T013 - Create `mcp` and `ui` stubs

**Purpose**

Give Stages 3 and 4 their importable homes with clear layering rules.

**Required changes**

- Create `src/premura/mcp/__init__.py`.
- Create `src/premura/ui/__init__.py`.
- `mcp` docstring must:
  - name `Stage 3 - MCP`,
  - describe querying `engine.list_by_domain`,
  - include the literal string `"never reads hp.fact_measurement directly"`.
- `ui` docstring must:
  - name `Stage 4 - User interface`,
  - describe the six health directions / interview flow,
  - include the literal string `"never reads hp.fact_measurement or calls engine directly"`.
- Add stub functions:
  - `register_tools(server, domains=None)` in `mcp`
  - `start_interview()` in `ui`
- Both stubs raise `NotImplementedError`.

**Naming rule**

- Use `ui/`, not `learn/`.

## Validation Strategy

Primary checks for this WP:

```bash
uv run python -c "from premura import mcp, ui; from premura.parsers import _lang, lookup; from premura.parsers.base import PluginParser, PluginParseResult; print('contracts import OK')"
```

Also expect:

- calling each stub raises `NotImplementedError`,
- v1 parser tests remain green,
- the shipped contract doc contains `LOINC`, `IEEE 1752.1`, and `derived:`.

## Definition Of Done

- `PluginParseResult` and `PluginParser` are appended to `parsers/base.py`.
- `lookup.py` and `_lang/__init__.py` exist with the required docstrings and stubs.
- `src/premura/parsers/CONTRACT.md` exists and matches the agreed policy.
- `src/premura/mcp/__init__.py` and `src/premura/ui/__init__.py` exist with required literal docstring assertions.

## Risks And Watchouts

- `parsers/base.py` is a shared contract file; avoid any cleanup churn.
- The parser contract is easy to get subtly wrong if the decision tree order or alias rule drifts.
- Stage naming drift (`learn` vs `ui`) is a known footgun; keep all new files and docs on `ui`.

## Reviewer Guidance

Review this WP in two passes:

1. additive type safety in `parsers/base.py`,
2. exact contract/docstring wording in the new stub/document files.

The highest-value check is whether the shipped `CONTRACT.md` fully matches the spec-approved vocabulary policy.

## Activity Log

- 2026-05-21T11:13:18Z – claude:opus-4-7:implementer:implementer – shell_pid=77625 – Started implementation via action command
- 2026-05-21T11:20:48Z – claude:opus-4-7:implementer:implementer – shell_pid=77625 – Ready for review: PluginParser Protocol + PluginParseResult added to parsers/base.py (additive); parsers/lookup.py, parsers/_lang/__init__.py, parsers/CONTRACT.md, mcp/__init__.py, ui/__init__.py created with required literal docstrings and NotImplementedError stubs; 25/25 existing tests green; ruff clean on owned files
- 2026-05-21T11:21:25Z – claude:opus-4-7:reviewer:reviewer – shell_pid=93528 – Started review via action command
- 2026-05-21T11:24:10Z – claude:opus-4-7:reviewer:reviewer – shell_pid=93528 – Review passed: PluginParser Protocol + PluginParseResult appended additively to parsers/base.py (ParseResult byte-for-byte unchanged); lookup.py, _lang/, CONTRACT.md, mcp/, ui/ stubs all carry required verbatim docstring tokens and raise NotImplementedError; 25/25 tests green, ruff clean on owned files; frozen=True deviation on PluginParseResult accepted because Python forbids frozen subclass of non-frozen ParseResult and T008 mandates ParseResult unchanged
- 2026-05-21T11:59:04Z – claude:opus-4-7:reviewer:reviewer – shell_pid=93528 – Done override: Mission v2-architectural-skeleton-01KS4SHA merged to master in 723bdeb
- 2026-05-21T12:10:49Z – claude:opus-4-7:reviewer:reviewer – shell_pid=93528 – Mission review failed: rollback for parser contract drift on PluginParseResult mutability
- 2026-05-21T12:19:56Z – claude:opus-4-7:reviewer:reviewer – shell_pid=20147 – Aligned CONTRACT.md and parser-generator/SKILL.md with mutable PluginParseResult; explained constraint inline
