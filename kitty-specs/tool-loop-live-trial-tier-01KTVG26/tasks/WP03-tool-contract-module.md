---
work_package_id: WP03
title: Tool contract module (chat client, registry, brief)
dependencies: []
requirement_refs:
- C-003
- C-005
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-005
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
agent: "claude:opus:implementer:implementer"
shell_pid: "24168"
history:
- date: '2026-06-11T14:19:42Z'
  action: created
  by: /spec-kitty.tasks
authoritative_surface: src/premura/harness/tool_loop_contract.py
execution_mode: code_change
owned_files:
- src/premura/harness/tool_loop_contract.py
- tests/test_tool_loop_contract.py
tags: []
---

# WP03 — Tool contract module (chat client, registry, brief)

## Objective

Create `src/premura/harness/tool_loop_contract.py` — the deterministic
contract surface of the tool-loop tier, fully testable without a model server:

1. a stdlib chat client for Ollama `/api/chat` with native tool-calling,
   inheriting the local-only URL guard and pinning `num_ctx` (NFR-001);
2. the **bounded tool registry** — `ToolRegistration` + the three first
   instances (`read_context`, `write_parser`, `run_ingest`) whose capability
   bounds make the fixture manifest physically unreachable (FR-003, FR-004,
   C-005, NFR-005);
3. the **single-source brief assembler** with explicit context-budget
   accounting that fails loudly, never truncates (FR-001, FR-002, SC-006).

The binding behavior contract is
`kitty-specs/tool-loop-live-trial-tier-01KTVG26/contracts/tool-loop-tier.md`
§§1–2 and §6 — read it before coding; tests derive from it (DIRECTIVE_036).

## Context you need

- Read first: `docs/shared/DOCTRINE.md`, then the mission's `spec.md`
  (FR-001..004), `research.md` (§R-1, §R-2, §R-7), `data-model.md` (the
  `ToolRegistration` table), `contracts/tool-loop-tier.md`.
- Reuse (import, NEVER copy — NFR-004) from `src/premura/harness/live_trial_ollama.py`:
  `_validated_ollama_url`, `OllamaUnavailableError`, `OLLAMA_URL`,
  `DEFAULT_MODEL`, `_DRAWER_PROBES` / `_resolve_drawer_probe` / `_DrawerProbe`,
  `_PARSER_DEST_RELPATH`, `_MAPPED_COLUMNS_CONST`. Same-package private import
  follows the existing seam convention (that module already imports the
  `live_trial` path). Do not edit that file (WP02 owns it).
- The one-shot client `_ollama` (same file) is your reference for the stdlib
  `urllib` posture: request shape, timeout, error mapping to
  `OllamaUnavailableError`, JSON-decode handling. Mirror its discipline.
- Sandbox shape: `premura.harness.sandbox.Sandbox` has `.root`; the parser
  destination inside a sandbox is `_PARSER_DEST_RELPATH`
  (`src/premura/parsers/_live_trial_parser.py`). The ingest runner subprocess
  pattern lives in `live_trial._run_ingest_subprocess` — `run_ingest`'s
  handler should reuse that function (import from `live_trial`; it is
  module-level).
- Env knobs you introduce here (contract §6): `LIVE_TRIAL_NUM_CTX`
  (default `16384`).
- PHI/containment: nothing in this module reads
  `tests/fixtures/session_log/fixture_fields.yaml` or accepts a path that
  resolves to it. The allowlist is the *only* read surface.

## Module-level design (write this as the module docstring)

State the boundaries the way sibling harness modules do: what a tool is (the
rule), why the manifest is physically unreachable (C-005 by construction),
that the brief is assembled from one canonical source per part (FR-001), and
that the budget check fails loudly rather than truncating (the 2026-06-04
audit's truncation defect is the thing this module exists to prevent).

## Subtasks

### T008 — Failing tests first: error mapping, registry bounds, brief invariants

**Purpose**: pin the contract before implementation (DIRECTIVE_034).

**Steps**: create `tests/test_tool_loop_contract.py` with failing tests, all
black-box through the module's public names:

1. **URL guard**: chat client refuses a non-local URL (reuses the same rule as
   the one-shot tier — assert `OllamaUnavailableError` or the shared guard's
   error, matching existing behavior).
2. **Tools-unsupported mapping**: with a fake transport injected (see T009 —
   the client takes an injectable transport/urlopen seam at the OUTSIDE
   boundary, per DIRECTIVE_036), an HTTP 400 whose body names tool support
   raises `ToolCallsUnsupportedError`; a connection error raises
   `OllamaUnavailableError`.
3. **num_ctx pinning**: the fake transport captures the request body; assert
   `options.num_ctx` equals `LIVE_TRIAL_NUM_CTX`'s default 16384 and respects
   the env override (monkeypatch the env var).
4. **Registry bounds (the C-005 tests — most important in this WP)**:
   - `read_context` over a temp sandbox-shaped tree returns the WHOLE content
     of an allowlisted file (write a multi-thousand-line temp file; assert
     full length — the no-truncation FR-002 witness);
   - `read_context` with the manifest filename, an absolute path outside the
     sandbox, a `../` traversal, and an arbitrary repo file each return a
     refusal STRING (fed back as the tool result; never file content, never an
     exception);
   - the registry has no registration whose handler can reach the manifest
     (assert the allowlist contents directly via the public registry surface).
   - `write_parser` writes to exactly `<sandbox>/src/premura/parsers/_live_trial_parser.py`
     and returns a confirmation string; a second call overwrites.
5. **Brief invariants (FR-001/FR-002/SC-006)**, per drawer probe (parametrize
   over `observation` and `intake_alien`):
   - contains every Target-API class name of that drawer's contract prompt
     (`IngestBatch`, `Measurement`, `SourceDescriptor`, `SkippedRow` for
     observation; `IntakeBatch`, `ParseOutput`, the intake input classes for
     intake);
   - contains the loop-protocol preamble (stable phrase, e.g. the tool names);
   - does NOT contain the one-shot-only directive (assert the absence of
     "Output ONLY the python module" — the phrase both one-shot prompts end
     with);
   - includes the goal and the data sample (first lines of the source file,
     same form the one-shot operator gets).
6. **Budget check**: an assembler called with a tiny budget (parameter or
   monkeypatched env) raises a clear error naming the overflow — never
   returns a truncated brief.

**Validation**: all new tests FAIL (module doesn't exist); collection clean.

### T009 — Chat client + `ToolCallsUnsupportedError`

**Purpose**: the transport (research §R-1; contract §3 first bullet).

**Steps**:
1. Derive the chat URL from the validated host of `OLLAMA_URL` (replace the
   path with `/api/chat`) so the existing env knob keeps working and the
   local-only guard applies to the derived URL too.
2. `ollama_chat(messages, *, model, tools, num_ctx, timeout=300) -> dict`:
   POST `{model, messages, tools, stream: False, options: {temperature: 0.1,
   num_ctx}}`; return the response `message` dict (`content` +
   optional `tool_calls`). Stdlib `urllib` only — no new dependency.
3. Error mapping: connection/timeout/garbled-JSON → `OllamaUnavailableError`
   (reuse the existing exception); an HTTP error whose body mentions tool
   support (Ollama's "does not support tools" family — match loosely,
   lowercase substring "tool") → new `ToolCallsUnsupportedError(RuntimeError)`.
   Any other HTTP error → `OllamaUnavailableError` (a reachable-but-broken
   endpoint is "unavailable" to callers, mirroring the one-shot posture).
4. Injectable transport seam for tests: accept an optional `transport`
   callable (defaults to the real urlopen-based one) — the outside-boundary
   substitution point (DIRECTIVE_036); WP04's fake backend will reuse it.

**Validation**: T008 groups 1–3 green.

### T010 — `ToolRegistration` + registry + the three bounded handlers

**Purpose**: FR-003/FR-004 — the rule, then its first three instances.

**Steps**:
1. `@dataclass(frozen=True, slots=True) ToolRegistration`: `name`,
   `description`, `parameters` (JSON schema dict for the chat `tools` param),
   `handler` (callable taking validated args + a small `TrialContext`).
2. `TrialContext` (frozen dataclass): `sandbox_root: Path`, `source: Path`,
   `read_allowlist: tuple[Path, ...]`, plus whatever `run_ingest` needs
   (warehouse path / parser spec come from sandbox conventions). Build it from
   a `Sandbox` + scenario source in one factory function. The allowlist is
   the source + `CONTRACT.md` + `base.py` resolved INSIDE the sandbox tree —
   `fixture_fields.yaml` is not in it, and handlers resolve ONLY against it
   (resolve + compare real paths; reject anything else including traversals).
3. Handlers (each returns a STRING — the tool result message):
   - `read_context(path)`: whole-file read of an allowlisted path; refusal
     string for anything else (name the allowlist in the refusal so the model
     can self-correct).
   - `write_parser(code)`: write to the parser destination
     (`_PARSER_DEST_RELPATH` under `sandbox_root`), mkdir parents, return
     confirmation with byte count. (The first-call snapshot is WP04's loop
     concern — keep this handler stateless.)
   - `run_ingest()`: call `live_trial._run_ingest_subprocess` against the
     context's sandbox/source/parser-spec; return the JSON envelope as a
     compact string, verbatim — never grader output (contract §1).
4. `default_tool_registry() -> dict[str, ToolRegistration]` returning the
   three; `registry_as_chat_tools(registry)` → the `tools` list for the chat
   call. Registering a new tool = adding an entry; document that rule in the
   docstring (NFR-005 — and resist any `if tool_name == ...` ladder in
   handlers' callers).

**Validation**: T008 group 4 green; mypy clean.

### T011 — Brief assembler with loud budget check

**Purpose**: FR-001/FR-002/SC-006 (research §R-2, §R-7).

**Steps**:
1. `assemble_brief(probe, goal, source, *, num_ctx=None) -> str`, one function,
   parts in contract §2 order:
   - tool-loop preamble: the loop protocol (you have tools; one response per
     turn; read what you need; write the parser with `write_parser`; verify
     with `run_ingest`; reply with NO tool calls when done) — this REPLACES
     the one-shot output directive, so strip nothing from the probe prompt
     except that final directive line;
   - the drawer probe's contract prompt **minus its one-shot-only output
     directive** (the trailing "Output ONLY the python module..." line):
     remove it structurally (e.g. partition on the known sentence), and assert
     in tests it's gone — if the upstream prompt wording drifts, the test
     catches the contradiction rather than shipping it (FR-001);
   - `GOAL:` line; `DATA SAMPLE (<name>):` block — same 8-line head the
     one-shot operator serves (mirror `OllamaOperator.operate`'s sample
     construction).
2. Budget accounting: estimate tokens conservatively (`len(brief) // 3` is an
   acceptable explicit overestimate — document the rule) and compare against
   the effective `num_ctx` minus a documented response/history reserve (e.g.
   half). On overflow raise `BriefBudgetError` naming sizes. NEVER truncate
   (the defect class this mission exists to prevent — say so in the error).
3. Expose `LIVE_TRIAL_NUM_CTX` parsing here (single home; WP04 imports it).

**Validation**: T008 groups 5–6 green. Full gates on owned files: `uv run
pytest -q`, `ruff check` + `ruff format --check`, `mypy`.

## Definition of Done

- [ ] New module + tests exactly in `owned_files`; no edits elsewhere; no new
      third-party dependency.
- [ ] Manifest unreachable through every registered handler (tests prove
      refusal by path, traversal, and absolute escape).
- [ ] Allowlisted reads are whole-file (length-asserted), FR-002.
- [ ] Brief invariant tests green for BOTH drawer probes (FR-008 symmetry).
- [ ] Budget overflow raises; nothing truncates.
- [ ] Default suite green; ruff + mypy clean; no test touches a network or a
      model server (fake transport only).

## Risks / notes for the reviewer

- Reviewer: the one-shot-directive stripping in T011 is the FR-001 crux —
  verify the assembled brief cannot simultaneously demand "output only a
  module" and "use tools" (the spike's defect). The structural strip + absence
  assertion is the control.
- Reviewer: check `read_context` resolves symlinks/`..` before the allowlist
  compare (use `Path.resolve()` on both sides).
- The token estimate is deliberately crude-but-conservative; precision is not
  the requirement — *loud failure instead of silent truncation* is (plan risk
  R2).
- Importing private names (`_DRAWER_PROBES`, `_run_ingest_subprocess`) from
  sibling harness modules follows the existing intra-package convention;
  do NOT copy their bodies (NFR-004). If the import feels wrong, the
  alternative is promoting them to public in those files — which you do not
  own; flag it rather than fork it.

## Activity Log

- 2026-06-11T17:46:53Z – claude:opus:implementer:implementer – shell_pid=24168 – Started implementation via action command
