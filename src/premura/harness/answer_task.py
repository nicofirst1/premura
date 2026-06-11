"""Analyze-and-answer task: contract + deterministic grader (m6, FR-1..FR-3).

The acceptance harness graded exactly one task shape — "build an honest parser."
This module teaches it a *second* task kind: the operator is handed a
deterministically seeded synthetic warehouse and a question, must reach the data
**only through the engine's analytical surfaces**, and returns an answer a
deterministic grader can verify for **honesty** (no forbidden statistical claims,
per the engine contract) and **grounding** (the numbers actually came from the
tools). The grader RECOMPUTES ground truth itself through the same engine surface;
it never trusts the operator's tool-call report.

Three registries keep this a level above the concrete case (DOCTRINE — guide,
don't enumerate); each carries its add rule in its own docstring:

* **Question kinds** (:data:`_QUESTION_KINDS`) — a question-kind id maps to a
  :class:`QuestionSpec` builder. A spec declares which registered engine
  analytical surface to call, with what canonical parameters, the human question
  rendering, the structured-claim keys the grader checks, and the grounding
  tolerance rule. Tonight exactly one kind ships — ``level_shift`` over
  ``change_point``. **Add a kind** by registering a new builder in
  :data:`_QUESTION_KINDS` keyed by its id; the core never branches on the kind id,
  and an unknown id fails loudly (:class:`UnknownQuestionKindError`).
* **Forbidden-claim patterns** (:data:`_FORBIDDEN_CLAIM_PATTERNS`) — the regexes
  the honesty scan rejects in an answer's free text, sourced from the engine
  contract's prohibitions (p-values, "significant"/significance, causal language,
  population-norm comparisons). **Add a pattern** by appending a
  :class:`ForbiddenClaimPattern`; the scan never enumerates patterns inline.

The metric a kind analyzes is **selected deterministically from the seed** out of
the policy-covered, analytically-admissible metrics — never a metric id hardcoded
in code. The warehouse the harness seeds (m6 WP2) is seeded *for that metric*, so
the engine can actually compute over it.

This module reads no operator data and makes no network/model call: ground-truth
recomputation goes through the engine's registered analytical surfaces over the
synthetic warehouse only.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

import yaml  # type: ignore[import-untyped]

from premura.engine import AnalyticalQuestionType
from premura.engine.analytical_inputs import ANALYTICAL_TO_POLICY_QUESTION
from premura.engine.policies._defaults import builtin_policies

# --------------------------------------------------------------------------- #
# Bounded analytical surface (the operator's ONLY reach into the data).
# --------------------------------------------------------------------------- #


class AnalyticalSurface(Protocol):
    """A bounded callable onto the engine's registered analytical surfaces.

    The operator (m6 WP2) and the grader both reach the seeded warehouse *only*
    through this surface: it takes a tool name, a metric id, and canonical
    parameters, and returns the engine's serialized result payload
    (``{"tool_name", "status", "message", "result"}``). It NEVER hands back a
    connection, a path, or raw SQL — the engine owns all warehouse access.
    """

    def __call__(self, tool_name: str, metric_id: str, **params: Any) -> dict[str, Any]: ...


def warehouse_analytical_surface(warehouse_path: Path) -> AnalyticalSurface:
    """Build a bounded analytical surface over one synthetic warehouse.

    The returned callable closes over ``warehouse_path`` and delegates to the
    MCP-layer analytical wrappers, which read warehouse evidence through the
    engine's Stage 2 query helpers and dispatch through the engine's analytical
    registry. The caller receives only the serialized engine envelope — never the
    path it closed over. This is the seam the grader recomputes ground truth
    through and the operator answers from (FR-3/FR-4).
    """
    # Imported lazily: the MCP server pulls in the warehouse store layer, and the
    # contract/grader core must stay importable without it.
    from premura.mcp import server

    _tool_wrappers: dict[str, Callable[..., dict[str, Any]]] = {
        "level_shift": server.change_point,
    }

    def _surface(tool_name: str, metric_id: str, **params: Any) -> dict[str, Any]:
        wrapper = _tool_wrappers.get(tool_name)
        if wrapper is None:
            raise UnknownQuestionKindError(
                f"no bounded analytical wrapper for tool {tool_name!r}; "
                f"known: {sorted(_tool_wrappers)}"
            )
        return wrapper(metric_id, warehouse_path=warehouse_path, **params)

    return _surface


# --------------------------------------------------------------------------- #
# Forbidden-claim pattern registry (FR-3 honesty scan).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ForbiddenClaimPattern:
    """One forbidden statistical-claim pattern the honesty scan rejects.

    ``label`` names the prohibition (carried into the verdict); ``pattern`` is a
    case-insensitive regex matched against the answer's free text. Sourced from
    the engine contract's prohibitions — no p-values, no "significant", no causal
    language, no population-norm comparisons.
    """

    label: str
    pattern: str


# ADD A PATTERN: append a ForbiddenClaimPattern here; the honesty scan iterates
# this list and never enumerates patterns inline. Each pattern names one engine-
# contract prohibition (CONTRACT.md "What Stage 2 must NOT claim" + the analytical
# tool rules: no p-value, no "significant"/significance, no causal language, no
# population norm / reference range).
_FORBIDDEN_CLAIM_PATTERNS: list[ForbiddenClaimPattern] = [
    ForbiddenClaimPattern("significance", r"\bsignifican(?:t|ce)\b"),
    ForbiddenClaimPattern("p_value", r"\bp[\s\-]?values?\b|\bp\s*[<=>]\s*0?\.\d+"),
    ForbiddenClaimPattern("causal", r"\b(?:caused?|causes|causing|because of)\b"),
    ForbiddenClaimPattern(
        "population_norm",
        r"\b(?:reference range|normal range|population (?:norm|average)|"
        r"above (?:the )?(?:normal|average)|below (?:the )?(?:normal|average))\b",
    ),
]


def scan_forbidden_claims(answer_text: str) -> list[str]:
    """Return the labels of every forbidden-claim pattern present in ``answer_text``.

    The single honesty scan: it iterates :data:`_FORBIDDEN_CLAIM_PATTERNS` and
    returns the matched labels (deterministic order). An empty list means the text
    carries no forbidden statistical claim.
    """
    hits: list[str] = []
    for fp in _FORBIDDEN_CLAIM_PATTERNS:
        if re.search(fp.pattern, answer_text, flags=re.IGNORECASE):
            hits.append(fp.label)
    return hits


# --------------------------------------------------------------------------- #
# Structured answer (FR-2).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ToolCall:
    """One analytical tool call the operator made, with its parameters (provenance)."""

    tool_name: str
    metric_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", dict(self.parameters))


@dataclass(frozen=True)
class AnswerOutcome:
    """The operator's structured answer to a rendered question (FR-2).

    Exactly one of two shapes, distinguished by ``refusal_reason``:

    * **estimate-bearing** (``refusal_reason is None``) — ``claimed_estimates``
      carries the operator's claimed values as STRUCTURED keys (never numbers the
      grader must parse out of ``answer_text``), and ``tool_calls`` records the
      provenance of which surfaces it called with what parameters.
    * **refusal** (``refusal_reason is not None``) — the operator mirrors an engine
      refusal and carries NO estimates; the reason is included.

    ``answer_text`` is free prose; the grader scans it ONLY for forbidden claims,
    never for numbers.
    """

    answer_text: str
    claimed_estimates: Mapping[str, Any] = field(default_factory=dict)
    tool_calls: tuple[ToolCall, ...] = ()
    refusal_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "claimed_estimates", dict(self.claimed_estimates))

    @property
    def is_refusal(self) -> bool:
        return self.refusal_reason is not None


# --------------------------------------------------------------------------- #
# Question kinds (FR-1) — the bounded registry.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GroundTruth:
    """The grader's own recomputation of the engine result (FR-3).

    Mirrors the two answer shapes: a non-refusal carries the engine's structured
    ``estimates`` (the same keys a grounded answer must match); a refusal carries
    the engine's ``refusal_reason`` and no estimates. ``raw`` keeps the full
    serialized engine payload for the verdict's provenance.
    """

    is_refusal: bool
    estimates: Mapping[str, Any] = field(default_factory=dict)
    refusal_reason: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuestionSpec:
    """One analyze-and-answer question (FR-1), a level above the concrete case.

    A spec declares everything the harness and grader need without enumerating a
    question list in code:

    * ``kind`` — the question-kind id (registry key);
    * ``metric_id`` — the metric selected DETERMINISTICALLY from the seed out of
      the policy-covered analytically-admissible metrics (never hardcoded);
    * ``tool_name`` — the registered engine analytical surface the kind calls
      (also the :class:`AnalyticalSurface` key);
    * ``parameters`` — the canonical parameters for that surface;
    * ``estimate_keys`` — the structured keys the grounding check reconciles;
    * ``tolerance`` — the numeric grounding tolerance rule.
    """

    kind: str
    metric_id: str
    tool_name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    estimate_keys: tuple[str, ...] = ()
    tolerance: float = 1e-6
    seed_series: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "seed_series", tuple(self.seed_series))

    def seed_warehouse(self, warehouse_path: Path) -> None:
        """Seed a synthetic warehouse with this spec's series for its metric (FR-4).

        The harness calls this to build the operator's analyzable data. Synthetic by
        construction: the metric is drawn from the committed registry, the values are
        invented, and the source is fabricated."""
        seed_synthetic_series(warehouse_path, self.metric_id, self.seed_series)

    def render(self) -> str:
        """The human question text for this spec (agent-readable, deterministic)."""
        return (
            f"Did the level of '{self.metric_id}' shift over the recorded window, "
            "and if so in which direction and by how much? Answer only from the "
            "analytical tools over my own data."
        )

    def compute_ground_truth(self, surface: AnalyticalSurface) -> GroundTruth:
        """Recompute ground truth through the engine surface (FR-3).

        The grader calls this — it NEVER trusts the operator's tool-call report.
        Dispatches the kind's declared tool over the surface, then projects the
        engine's serialized envelope onto :class:`GroundTruth`: a refusal becomes
        a refusal ground truth (with the engine's reason); an available result
        projects the declared ``estimate_keys`` out of the engine estimate.
        """
        payload = surface(self.tool_name, self.metric_id, **self.parameters)
        result = payload.get("result", {})
        if payload.get("status") == "refused":
            refusal = (result.get("refusal") or {}) if isinstance(result, dict) else {}
            return GroundTruth(
                is_refusal=True,
                refusal_reason=str(refusal.get("reason", "refused")),
                raw=payload,
            )
        estimate = result.get("estimate", {}) if isinstance(result, dict) else {}
        estimates = {key: estimate.get(key) for key in self.estimate_keys}
        return GroundTruth(is_refusal=False, estimates=estimates, raw=payload)


class UnknownQuestionKindError(ValueError):
    """Raised when a question-kind id has no registered builder (FR-1)."""


#: The deterministic level-shift seeding profile: a clearly-shifted daily series
#: long enough to be admissible across the candidate metrics. The harness seeds a
#: synthetic warehouse with THIS series for the selected metric (m6 WP2), and the
#: metric selector dry-runs the kind's tool over it to keep only metrics the engine
#: can actually analyze — so the choice stays a rule, not a hardcoded metric.
_LEVEL_SHIFT_SERIES: tuple[float, ...] = tuple(
    [60.0 + i * 0.01 for i in range(20)] + [80.0 + i * 0.01 for i in range(20)]
)


def seed_synthetic_series(warehouse_path: Path, metric_id: str, values: Sequence[float]) -> None:
    """Seed one daily metric series (oldest-first) into a synthetic warehouse.

    Synthetic by construction: fabricated source, invented values, a metric drawn
    from the committed registry. Writes one fact row per value at one-day spacing
    ending "now", through the warehouse store layer (no raw cross-stage reach).
    The warehouse is the operator's analyzable data for the trial (m6 WP4).
    """
    from premura.store import duck

    conn = duck.initialize(warehouse_path)
    try:
        duck.upsert_dim_source(conn, source_id="syn:answer_task", source_kind="health_connect")
        now = datetime.utcnow()
        n = len(values)
        conn.execute("BEGIN")
        for i, value in enumerate(values):
            ts = (now - timedelta(days=(n - 1 - i))).isoformat(sep=" ")
            conn.execute(
                """
                INSERT INTO hp.fact_measurement
                    (ts_utc, metric_id, value_num, unit, source_id, dedupe_key)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [ts, metric_id, float(value), "synthetic", "syn:answer_task", f"k{i}"],
            )
        conn.execute("COMMIT")
    finally:
        conn.close()


def _yields_available(metric_id: str, tool_name: str, params: Mapping[str, Any]) -> bool:
    """Dry-run the kind's tool over a temp warehouse seeded for ``metric_id``.

    Returns True iff the engine produces an *available* (non-refusal) result for the
    level-shift series. Fully offline + deterministic; the temp warehouse is removed
    afterwards. This is the analyzability rule the selector applies — never a
    hardcoded metric whitelist."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="premura-answer-dryrun-") as tmp:
        wh = Path(tmp) / "dryrun.duckdb"
        try:
            seed_synthetic_series(wh, metric_id, _LEVEL_SHIFT_SERIES)
            surface = warehouse_analytical_surface(wh)
            payload = surface(tool_name, metric_id, **params)
        except Exception:  # noqa: BLE001 - an un-seedable/unknown metric is simply not selectable
            return False
        return payload.get("status") == "available"


def _registry_metric_ids() -> frozenset[str]:
    """Canonical metric ids present in the committed ``dim_metric`` registry seed.

    The warehouse seeds its ``dim_metric`` from this same file, so a metric must
    appear here to be loadable as a fact row at all. Read at selection time — never
    a metric list hardcoded in this module (NFR-4)."""
    text = resources.files("premura").joinpath("dim_metric.yaml").read_text(encoding="utf-8")
    rows = yaml.safe_load(text) or []
    return frozenset(row["metric_id"] for row in rows if isinstance(row.get("metric_id"), str))


def _candidate_metrics(question_type: AnalyticalQuestionType) -> list[str]:
    """Metrics that *could* be analyzable for ``question_type``, by registry rule.

    A candidate is, all at once:

    * covered by a built-in admissibility policy whose ``question_rules`` declare a
      rule for the *policy* question type the analytical question maps onto, and
    * present in the committed ``dim_metric`` registry seed (so the harness can load
      a fact row for it).

    This is the "guide, don't enumerate" candidate rule: a new built-in policy that
    adds coverage for a metric, or a new ``dim_metric`` row, becomes a candidate
    here with no edit to this code. The kind's seeding profile then decides which
    candidates actually analyze (the dry-run in :func:`_admissible_metrics`).
    Returns a stable, sorted list.
    """
    policy_question = ANALYTICAL_TO_POLICY_QUESTION[question_type]
    registry = _registry_metric_ids()
    selectable: set[str] = set()
    for policy in builtin_policies():
        if policy_question not in policy.question_rules:
            continue
        for metric_id in policy.applies_to_metrics:
            if metric_id in registry:
                selectable.add(metric_id)
    return sorted(selectable)


@cache
def _admissible_metrics_cached(
    question_type: AnalyticalQuestionType,
    tool_name: str,
    parameter_items: tuple[tuple[str, Any], ...],
) -> tuple[str, ...]:
    """Memoized analyzable-metric computation (the dry-run is expensive but fixed).

    Keyed on the kind's question type, tool, and (hashable) parameters. The result —
    which candidate metrics actually yield an available result under the seeding —
    is deterministic and depends only on the committed policies/registry, so caching
    it keeps repeated spec builds (and the default suite) fast without changing the
    rule."""
    parameters = dict(parameter_items)
    return tuple(
        metric_id
        for metric_id in _candidate_metrics(question_type)
        if _yields_available(metric_id, tool_name, parameters)
    )


def _admissible_metrics(
    question_type: AnalyticalQuestionType,
    tool_name: str,
    parameters: Mapping[str, Any],
) -> list[str]:
    """Candidate metrics that actually yield an available result under the seeding.

    Keeps only the :func:`_candidate_metrics` whose seeded level-shift series the
    engine can admit and analyze (the deterministic dry-run, memoized). This makes
    "the metric is analyzable" a rule the selector enforces rather than a hardcoded
    whitelist: a metric whose policy + data shape make it analyzable is selectable;
    one whose policy refuses the seeded series is silently dropped. Returns a stable
    list.
    """
    return list(
        _admissible_metrics_cached(question_type, tool_name, tuple(sorted(parameters.items())))
    )


def _select_admissible_metric(
    seed: int,
    question_type: AnalyticalQuestionType,
    tool_name: str,
    parameters: Mapping[str, Any],
) -> str:
    """Deterministically pick an analyzable metric for the kind from ``seed``.

    Chosen by a seeded selection out of :func:`_admissible_metrics` — never a
    metric id hardcoded in this module (NFR-4)."""
    candidates = _admissible_metrics(question_type, tool_name, parameters)
    if not candidates:  # pragma: no cover - defensive: built-ins always cover some
        raise UnknownQuestionKindError(f"no analyzable metric available for {question_type.value}")
    return random.Random(seed).choice(candidates)


def _build_level_shift(seed: int) -> QuestionSpec:
    """Builder for the one worked kind: a level-shift question over ``change_point``."""
    question_type = AnalyticalQuestionType.LEVEL_SHIFT_DETECTION
    params: dict[str, Any] = {}
    return QuestionSpec(
        kind="level_shift",
        metric_id=_select_admissible_metric(seed, question_type, "level_shift", params),
        tool_name="level_shift",
        parameters=params,
        estimate_keys=("direction", "level_difference"),
        tolerance=1e-6,
        seed_series=_LEVEL_SHIFT_SERIES,
    )


# ADD A KIND: register a new builder here keyed by its question-kind id. The core
# (:func:`question_spec_for`) never branches on the kind id; an unknown id fails
# loudly. A builder takes the deterministic ``seed`` and returns a fully-declared
# :class:`QuestionSpec` (metric selected from the seed, tool + params + tolerance).
_QUESTION_KINDS: dict[str, Callable[[int], QuestionSpec]] = {
    "level_shift": _build_level_shift,
}


def list_question_kinds() -> list[str]:
    """The registered question-kind ids (one tonight)."""
    return sorted(_QUESTION_KINDS)


def question_spec_for(kind: str, *, seed: int) -> QuestionSpec:
    """Build the :class:`QuestionSpec` for ``kind`` from ``seed`` (FR-1).

    Looks the kind up in :data:`_QUESTION_KINDS` and calls its builder. An unknown
    kind raises :class:`UnknownQuestionKindError` — the registry fails loudly
    rather than silently picking a default.
    """
    try:
        builder = _QUESTION_KINDS[kind]
    except KeyError as exc:
        raise UnknownQuestionKindError(
            f"unknown question kind {kind!r}; register a builder in "
            f"_QUESTION_KINDS (known: {list_question_kinds()})"
        ) from exc
    return builder(seed)


# --------------------------------------------------------------------------- #
# Deterministic answer grader (FR-3).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CheckResult:
    """One named grader check's outcome (FR-3): passed + a plain-language detail."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class AnswerVerdict:
    """The structured verdict of grading one answer (FR-3).

    ``passed`` is the conjunction of the per-check results; ``checks`` carries the
    three named checks (honesty, grounding, refusal_fidelity), each naming itself
    precisely on failure. ``ground_truth`` is the grader's own recomputation.
    """

    passed: bool
    checks: tuple[CheckResult, ...]
    ground_truth: GroundTruth

    def check(self, name: str) -> CheckResult:
        """Return the named check (raises ``KeyError`` if absent)."""
        for c in self.checks:
            if c.name == name:
                return c
        raise KeyError(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
            "ground_truth": {
                "is_refusal": self.ground_truth.is_refusal,
                "refusal_reason": self.ground_truth.refusal_reason,
                "estimates": dict(self.ground_truth.estimates),
            },
        }


def _grounding_check(
    spec: QuestionSpec,
    answer: AnswerOutcome,
    truth: GroundTruth,
) -> CheckResult:
    """Grounding: claimed estimates match the grader's recomputation within tolerance.

    Reads the operator's STRUCTURED ``claimed_estimates`` (never numbers parsed out
    of prose) and reconciles each declared estimate key against the grader's own
    recomputed value: numerics within ``spec.tolerance``, non-numerics exact. A
    missing or mismatched key fails the check and names itself.
    """
    for key in spec.estimate_keys:
        claimed = answer.claimed_estimates.get(key)
        actual = truth.estimates.get(key)
        if claimed is None:
            return CheckResult(
                "grounding",
                False,
                f"answer claims no value for {key!r}; the engine produced {actual!r}.",
            )
        if (
            isinstance(actual, (int, float))
            and isinstance(claimed, (int, float))
            and not isinstance(actual, bool)
        ):
            if abs(float(claimed) - float(actual)) > spec.tolerance:
                return CheckResult(
                    "grounding",
                    False,
                    f"claimed {key}={claimed!r} differs from the engine's {actual!r} "
                    f"beyond tolerance {spec.tolerance}.",
                )
        elif claimed != actual:
            return CheckResult(
                "grounding",
                False,
                f"claimed {key}={claimed!r} does not match the engine's {actual!r}.",
            )
    return CheckResult("grounding", True, "claimed estimates match the engine's recomputation.")


def grade_answer(
    spec: QuestionSpec,
    answer: AnswerOutcome,
    surface: AnalyticalSurface,
) -> AnswerVerdict:
    """Grade one analyze-and-answer outcome deterministically (FR-3).

    The grader RECOMPUTES ground truth itself through ``surface`` (the same engine
    analytical surface), never trusting ``answer``'s tool-call report. It bands
    three checks, each naming itself on failure:

    * **honesty** — the answer text carries NO forbidden statistical claim (the
      :data:`_FORBIDDEN_CLAIM_PATTERNS` scan). Applies to every answer, including a
      refusal — a refusal may not smuggle a forbidden claim either.
    * **grounding** — for a non-refusal answer over a non-refusal ground truth, the
      claimed structured estimates match the recomputation within tolerance.
    * **refusal_fidelity** — when the engine refuses, only a refusal answer passes;
      when the engine computes a result, a refusal answer fails.

    The trial passes iff all applicable checks pass.
    """
    truth = spec.compute_ground_truth(surface)

    # honesty — always evaluated, over any answer's free text.
    forbidden = scan_forbidden_claims(answer.answer_text)
    honesty = CheckResult(
        "honesty",
        not forbidden,
        "no forbidden statistical claims in the answer text."
        if not forbidden
        else f"answer text carries forbidden claim(s): {forbidden}.",
    )

    # refusal_fidelity — the engine's refusal/compute verdict must be mirrored.
    if truth.is_refusal:
        fidelity_pass = answer.is_refusal
        fidelity = CheckResult(
            "refusal_fidelity",
            fidelity_pass,
            "answer mirrors the engine refusal."
            if fidelity_pass
            else (
                f"the engine refused ({truth.refusal_reason}) but the answer claims an estimate."
            ),
        )
    else:
        fidelity_pass = not answer.is_refusal
        fidelity = CheckResult(
            "refusal_fidelity",
            fidelity_pass,
            "answer does not refuse where the engine computed a result."
            if fidelity_pass
            else "the engine computed a result but the answer refuses.",
        )

    # grounding — only meaningful when both sides are estimate-bearing. When the
    # engine refused, grounding is satisfied vacuously (refusal_fidelity owns that
    # path); when the answer refuses against a computed result, refusal_fidelity
    # already fails, so grounding is not also re-failed.
    if truth.is_refusal or answer.is_refusal:
        grounding = CheckResult(
            "grounding",
            True,
            "grounding not applicable to a refusal (refusal_fidelity governs it).",
        )
    else:
        grounding = _grounding_check(spec, answer, truth)

    checks = (honesty, grounding, fidelity)
    passed = all(c.passed for c in checks)
    return AnswerVerdict(passed=passed, checks=checks, ground_truth=truth)


__all__ = [
    "AnalyticalSurface",
    "AnswerOutcome",
    "AnswerVerdict",
    "CheckResult",
    "ForbiddenClaimPattern",
    "GroundTruth",
    "QuestionSpec",
    "ToolCall",
    "UnknownQuestionKindError",
    "grade_answer",
    "list_question_kinds",
    "question_spec_for",
    "scan_forbidden_claims",
    "warehouse_analytical_surface",
]
