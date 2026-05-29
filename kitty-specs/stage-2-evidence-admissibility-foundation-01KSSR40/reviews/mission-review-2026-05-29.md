# Mission Review Report: stage-2-evidence-admissibility-foundation-01KSSR40

**Reviewer**: Claude (post-merge mission reviewer)
**Date**: 2026-05-29
**Mission**: `stage-2-evidence-admissibility-foundation-01KSSR40` — Stage 2 Evidence Admissibility Foundation
**Baseline commit**: `651afc7` (parent of the squash merge)
**HEAD at review**: `0ce5eb4` ("squash merge of mission")
**WPs reviewed**: WP01–WP05 (all `approved`; board never transitioned to `done` — bookkeeping lag, code is merged)
**Review history**: clean — one cycle per WP, all user-approved, no rejection cycles, no arbiter overrides

## Verdict: **FAIL** — one blocking finding (DRIFT-1)

---

## FR / NFR Coverage Matrix

| ID | Requirement (brief) | Impl | Test adequacy | Finding |
|----|---------------------|------|---------------|---------|
| FR-001 | 4 question types; unsupported → clear outcome | IMPLEMENTED (`_model.py:44`, `_evaluator.py:362`) | PARTIAL — unsupported-policy path tested; no invalid-enum-at-runtime guard | — |
| FR-002 | Family policy classes (≥ research families) | IMPLEMENTED — 12 families / 8 shapes (`_defaults.py:552–718`) | ADEQUATE | — |
| FR-003 | Same evidence admissible per-question, provenance kept | IMPLEMENTED (`_evaluator.py:354`) | ADEQUATE (`test_engine_policy_evaluator.py:219`) | — |
| FR-004 | Distinct machine-readable rejection reasons + plain English | IMPLEMENTED (`_model.py:61`, `_evaluator.py:189–351`) | ADEQUATE | DRIFT-5 (dual MISSING_TIMESTAMP path, low) |
| FR-005 | Admissible vs rejected structurally separate | IMPLEMENTED (`_model.py:389`) | ADEQUATE | — |
| FR-006 | Provenance on every item incl. "policy outcome" | PARTIAL — content present, serialized key is `status` not `policy_outcome`; refusal rollup blank identity | PARTIAL — only `metric_id` asserted | DRIFT-4 |
| FR-007 | Refuse (with reason) when none admissible — not empty/guess | IMPLEMENTED — real distinct refusal, structurally enforced (`_evaluator.py:535`, `_model.py:405`); live path refuses, does not hedge | ADEQUATE | — PASS |
| FR-008 | Method-sensitive families always caveat — admitted or rejected | PARTIAL — admit path only (`_evaluator.py:423`); rejected/insufficient drop standing caveats; live consumer ignores outcome caveats | reject path not tested | DRIFT-2 |
| FR-009 | Descriptive, non-diagnostic | IMPLEMENTED | ADEQUATE | one borderline "treat it as" phrase (`_defaults.py:144`, low) |
| NFR-001 | Deterministic (no clock inside) | IMPLEMENTED — no `datetime.now`/`time` in evaluator; `reference_time` is an arg | ADEQUATE (`test_engine_policy_evaluator.py:301`) | — PASS |
| NFR-002 | Traceable: provenance + policy-outcome fields | PARTIAL | PARTIAL | DRIFT-4 |
| NFR-003 | No diagnostic/prescriptive language | IMPLEMENTED | ADEQUATE | — |
| NFR-004 | Refusal states testable | IMPLEMENTED | ADEQUATE | — |
| NFR-005 | ≥10 family groups | IMPLEMENTED — 12 | one weak test (below) | — |
| NFR-006 | Caveats ≤280 chars | IMPLEMENTED — max 140 | ADEQUATE | — |
| C-001 / C-002 / C-003 | No Stage 3; warehouse-only/no network; no new answer family | PASS — MCP untouched, no `httpx/requests/duckdb/pubmed` in policy surface, `RESULT_FAMILIES` unchanged | — | — PASS |

**Legend**: ADEQUATE = test constrains required behavior; PARTIAL = test exists but does not fully constrain; FALSE_POSITIVE = passes even if impl deleted; MISSING = no test.

---

## Drift Findings

### DRIFT-1 — Pure-declarative ("parameters only") invariant is advertised but not enforced — **HIGH · BLOCKING**
- **Type**: LOCKED-DECISION VIOLATION / PUNTED-DoD (T003)
- **Spec ref**: T003 ("fails early for … non-parameter-like content"), `src/premura/engine/CONTRACT.md`, `_model.py:12` docstring ("No callables, expressions…"), ratified doctrine [ADR 0007](../../../docs/adr/0007-evidence-admissibility-as-a-declared-contract.md)
- **Evidence** (verified directly against source): the only `isinstance` guard is `_model.py:293`, checking `question_rules` **keys** only. `QuestionRule.admissibility` (`_model.py:213`), `MetricFamilyPolicy.required_provenance`, and `applies_to_metrics` have no type/parameter guard. `QuestionRule.__post_init__` (`_model.py:221`) only checks the INADMISSIBLE-needs-reason combination and `.strip()`s caveat/required_context strings. A declaration with `admissibility=lambda c: Admissibility.ADMISSIBLE` constructs, registers, and evaluates to `ADMISSIBLE` for any evidence — the identity check `is Admissibility.INADMISSIBLE` (`_model.py:222`, `_evaluator.py:381`) silently routes a callable to the admissible path. No error, no test. (Independently executed by review: lambda in `admissibility`, `required_provenance`, and `applies_to_metrics` all accepted.)
- **Analysis**: This is the one property that makes agent-authored policies safe to accept, and WP04's public surface plus `CONTRACT.md` explicitly invite agents to author policies under a "parameters-only" promise the model does not keep. Shipped `_defaults.py` are all clean, so there is no runtime exploit yet; the gap is latent but sits directly on the advertised extension path. The instant a future Stage 3 tool or PR-authored policy supplies a declaration containing logic, a policy can mark stale/wrong evidence admissible — the confident-wrong-about-health failure (primary fear) this mission exists to prevent. The WP01 approval claimed T003 covered validation but never tested type enforcement — a per-WP blind spot.
- **Remediation (small, local)**: add construction-time `isinstance` checks for `admissibility` (∈ `Admissibility`) and element types of `required_provenance`/`applies_to_metrics`/`applies_to` (str) in `__post_init__`; add a test injecting a callable that expects `ValueError`.

### DRIFT-2 — FR-008 caveats emitted on admit path only, never on reject/insufficient — **MEDIUM**
- **Spec ref**: FR-008 ("always produce caveat text when admitted **or rejected**")
- **Evidence**: `_evaluator.py:423` merges `policy.standing_caveats` into admissible outcomes only; rejected/insufficient `EvidenceOutcome.caveats` omit them. The sole live consumer `_resting_hr_policy_caveat` (`descriptive_signals.py:305`) returns a hardcoded string and never reads `evaluation.refusal.caveats`. The `hrv_resting_recovery` standing caveat ("only meaningful relative to your own baseline") never reaches the user on the stale/refusal path — where method-sensitivity matters most.
- **Analysis**: premura's recurring "authored-but-never-read metadata" failure mode. The model guarantees the caveat is *declared* (`_model.py:298`) but not that it is *emitted* when rejecting.

### DRIFT-3 — Declaration vocabulary over-promises vs evaluator behavior (dead-metadata cluster) — **MEDIUM**
- **Evidence**:
  - `QuestionRule.refusal_mode` (`OFFER_WITH_CAVEATS`, `SUGGEST_DIFFERENT_QUESTION`) set in 7 built-ins; evaluator has zero references to it — all rejections are hard `REJECTED`/`INSUFFICIENT`.
  - `MissingDataBehavior.CAVEAT` (`_model.py:133`) silently falls through to `INSUFFICIENT` (`_evaluator.py:416–419`) — behaves as REJECT.
  - `applies_to_metrics` never read by the evaluator; `hrv_resting_recovery` lists `"resting_heart_rate"` while the warehouse metric is `"resting_hr"` (`_defaults.py:721` vs `descriptive_signals.py:104`).
- **Analysis**: three declared fields a future policy author will reasonably set and get silently different behavior. Either consume them or remove them from the declared surface.

### DRIFT-4 — `policy_outcome` field naming + refusal rollup identity — **LOW**
`to_dict()` serializes the outcome as `status`, not the spec-named `policy_outcome` (FR-006/NFR-002); `_build_refusal` rollup carries blank `metric_family`/`policy_id` (`_evaluator.py:474`). Semantic content present; literal contract vocabulary not matched.

### DRIFT-5 — Dual-path `MISSING_TIMESTAMP` depending on declaration completeness — **LOW**
`MISSING_TIMESTAMP` can surface from `_missing_context_outcome` or from `_freshness_outcome` (`_evaluator.py:170`) depending on whether `observed_at` is listed in `required_provenance`; the freshness-path variant is untested.

---

## Risk Findings

### RISK-1 — Resting-HR proof passes `reference_time = observed_at` → age always 0 — **MEDIUM (latent)**
- **Location**: `descriptive_signals.py:294`. **Trigger**: any future `CURRENT_STATUS` rule added to `hrv_resting_recovery`.
- **Analysis**: with age≡0 the `BASELINE_RELATIVE` freshness window can never fire; the live refusal actually comes from `hrv_resting_recovery` having no CURRENT_STATUS rule → `UNSUPPORTED_POLICY`, not `STALE_FOR_QUESTION` as the comment (`descriptive_signals.py:224`) claims. Output is correct today (still refuses), but (a) the proof does not exercise the freshness-admissibility logic it purports to demonstrate — the mission's primary scenario (stale rejected *for freshness*) is unit-tested but not integration-proven on the live path; and (b) if a CURRENT_STATUS rule is later added, age=0 will admit arbitrarily stale readings as current, silently. Directly aligned with the primary fear (confident-wrong-about-health).

### RISK-2 — Global mutable `_BUILTINS_LOADED` causes order-dependent test failure — **MEDIUM (pre-existing, propagated)**
- **Location**: `engine/__init__.py:120`; new fixture `test_engine_descriptive_policy_integration.py:40`. Verified pre-existing (diff does not touch the global; reproduces on baseline). The new WP05 fixture snapshots/restores `REGISTRY` without resetting `_BUILTINS_LOADED`, repeating the fragile pattern, so `test_bmi_dispatches_through_compute` can `KeyError` under two-file ordering and break `make test`.

### RISK-3 — `IGNORE_IF_NOT_REQUIRED` admits below-minimum density with no caveat — **LOW**
`_evaluator.py:416` falls through to admissible without flagging that declared density was unmet; untested path.

---

## Silent-Behavior Candidates

| Location | Condition | Silent result | Impact |
|----------|-----------|---------------|--------|
| `_evaluator.py:416–419` | `MissingDataBehavior.CAVEAT` set | treated as `INSUFFICIENT` | DRIFT-3: declared "caveat-and-pass" silently becomes hard reject |
| `_evaluator.py:423` | rejected/insufficient outcome | standing caveats dropped | DRIFT-2: FR-008 method-sensitive caveat never surfaced on refusal |
| `descriptive_signals.py:305` | stale resting-HR | hardcoded caveat; `evaluation` caveats ignored | policy's own caveats orphaned |

No `except: pass` / `return ""` error-swallowing found in production code — the evaluator is clean on that axis.

---

## Test Adequacy Notes

- `test_builtins_register_without_collision` (`test_engine_policy_defaults.py:197`) — FALSE_POSITIVE: passes with empty defaults (no minimum-count assertion). Other coverage (`test_builtin_policies_cover_at_least_ten_family_groups`, `test_registry_round_trips_and_is_deterministic`) does constrain, so family coverage is genuinely tested.
- Pure-declarative invariant (DRIFT-1) is untested — no test injects a callable.
- Provenance round-trip is shallow — only `metric_id` asserted; `source_id`/`observed_at`/`coverage_pct`/`point_count` never checked.
- `MissingDataBehavior.CAVEAT`, `refusal_mode` variants, and `IGNORE_IF_NOT_REQUIRED` admit path are untested.

---

## Security Notes

| Finding | Location | Risk class | Recommendation |
|---------|----------|------------|----------------|
| Public surface exports model constructors, making DRIFT-1 reachable by external callers | `engine/__init__.py` | INPUT-VALIDATION (latent) | harden declaration validation (DRIFT-1) before any runtime policy-authoring surface ships |

Minimal surface otherwise: pure in-memory evaluation over passed-in data; no subprocess, file I/O, network, or auth introduced. C-002 verified — no `httpx/requests/urllib/socket/duckdb/pubmed` reachable from `policies/`.

---

## Verdict Rationale

The mission is well-built: refuse-over-hedge is correctly implemented on the live path (FR-007), evaluation is deterministic (NFR-001), language is non-diagnostic (NFR-003), family coverage and caveat limits are met (NFR-005/006), and the Stage-2/Stage-3 boundary and no-network constraints hold (C-001/C-002/C-003). Test fidelity is mostly real, not synthetic.

It fails on the single property that is the reason this foundation exists: the parameters-only ("form") guarantee it advertises in its own docstring and `CONTRACT.md` is not enforced (DRIFT-1, HIGH). Because the mission's purpose is to be a substrate that agents extend — and the project has ratified that safety must live in the substrate, not the agent's judgment (ADR 0007) — shipping the advertised guardrail unenforced is blocking. The fix is small and local; this is not a redesign.

### Open items (non-blocking)
- DRIFT-2: emit method-sensitive standing caveats on the reject/insufficient path; have `_resting_hr_policy_caveat` read outcome caveats. (FR-008)
- DRIFT-3: consume or remove `refusal_mode`, `MissingDataBehavior.CAVEAT`, `applies_to_metrics`; fix `resting_heart_rate`→`resting_hr`.
- RISK-1: revisit `reference_time=observed_at`; fix the misleading "stale-for-question" comment; add a live integration test exercising freshness rejection (not just `UNSUPPORTED_POLICY`).
- RISK-2: reset `_BUILTINS_LOADED` in registry-snapshot fixtures (pre-existing; track separately).
- DRIFT-4 / DRIFT-5 / test gaps: `policy_outcome` field naming; deepen provenance round-trip asserts; strengthen `test_builtins_register_without_collision`.
