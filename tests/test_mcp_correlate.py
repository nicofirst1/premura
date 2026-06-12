"""WP04 — default-surface tests for the agent-facing ``correlate`` wrapper.

These lock the contract from ``contracts/correlate-contract.md`` at the MCP
boundary:

* the DEFAULT agent-safe surface publishes ``correlate`` (taking the prior
  twelve tools to thirteen);
* a success payload carries ``tool_name`` / ``status`` / ``message`` / ``result``
  and the non-refusal ``result`` carries the full association envelope metadata
  (estimate with Spearman rho, observed/expected direction, association band,
  raw + effective sample size, lag, overlap, imputation, validity, confounds);
* a refusal payload carries a distinct reason and NO estimate, and serializes
  cleanly (JSON-safe, byte-stable);
* common-cause and opposite-direction hypothesis metadata are preserved verbatim;
* the wrapper DELEGATES to the engine analytical path — it prepares the two
  paired series through the engine, builds the hypothesis, and dispatches
  ``correlate`` — and performs NO statistics, NO pairing, NO raw fact-table
  analysis, and NO network/PubMed work.

Synthetic data only. The wrapper serializes and delegates; tests assert on the
structured payloads and on the engine being the one that computes.
"""

from __future__ import annotations

import ast
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from premura.mcp import server
from premura.mcp.entrypoint import build_operator_server, build_server
from premura.store import duck

# WP04 adds ``correlate`` to the prior twelve default tools (WP06 left twelve).
# session-research-trace WP03 adds the three trace tools to the same surface.
# WP05 (finish-analytical-tool-set) adds rolling_mean + paired_t_test (-> 18).
_DEFAULT_TOOLS_WITH_CORRELATE = sorted(
    [
        "list_metrics",
        "metric_summary",
        "resting_hr_status",
        "resting_hr_trend",
        "steps_trend",
        "weight_trend",
        "sleep_deep_pct_baseline",
        "hrv_change_around_date",
        "supplement_intake_adherence",
        "nutrition_intake_trend",
        "profile_context_supported_fields",
        "profile_context_record",
        "change_point",
        "smoothed_average",
        "correlate",
        "rolling_mean",
        "paired_t_test",
        "condition_paired_t_test",
        "pubmed_search",
        "pubmed_fetch",
        "research_trace_open",
        "research_trace_mark_surfaced",
        "research_trace_disclosure",
    ]
)

# Two real metrics from different families, each covered by a
# LAGGED_ASSOCIATION-admissible built-in policy, so a fresh seeded daily series
# is admissible and the tool actually computes a Spearman estimate over it.
_LEFT_METRIC = "resting_hr"
_RIGHT_METRIC = "sleep_efficiency"


def _now() -> datetime:
    return datetime.utcnow()


def _empty_warehouse(tmp_path: Path) -> Path:
    db_path = tmp_path / "empty.duckdb"
    duck.initialize(db_path).close()
    return db_path


def _low_autocorr(n: int, *, sign: float = 1.0, seed: int = 12345) -> list[float]:
    """A deterministic low-autocorrelation sequence (shuffled 0..n-1).

    Used identically on both sides it yields a clean monotone association with
    little serial correlation, so the effective sample size clears the floor and
    an available estimate is produced — mirroring the engine test fixtures.
    """
    import random

    rng = random.Random(seed)
    vals = list(range(n))
    rng.shuffle(vals)
    return [sign * float(v) for v in vals]


def _seed_metric(conn, metric_id: str, values: list[float], *, unit: str, key_prefix: str) -> None:
    now = _now()
    n = len(values)
    for i, value in enumerate(values):
        ts = (now - timedelta(days=(n - 1 - i))).isoformat(sep=" ")
        conn.execute(
            """
            INSERT INTO hp.fact_measurement (
                ts_utc, metric_id, value_num, unit, source_id, dedupe_key
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [ts, metric_id, value, unit, "test:source", f"{key_prefix}{i}"],
        )


def _warehouse_with_pair(
    tmp_path: Path, left_values: list[float], right_values: list[float]
) -> Path:
    """Seed two daily metric series (oldest-first) and return the warehouse path."""
    db_path = tmp_path / "correlate.duckdb"
    conn = duck.initialize(db_path)
    duck.upsert_dim_source(conn, source_id="test:source", source_kind="health_connect")
    conn.execute("BEGIN")
    _seed_metric(conn, _LEFT_METRIC, left_values, unit="bpm", key_prefix="l")
    _seed_metric(conn, _RIGHT_METRIC, right_values, unit="pct", key_prefix="r")
    conn.execute("COMMIT")
    conn.close()
    return db_path


# --------------------------------------------------------------------------- #
# Default-surface membership: correlate is published; count moves 12 -> 13.
# --------------------------------------------------------------------------- #
def test_default_surface_includes_correlate() -> None:
    async def run() -> None:
        names = {tool.name for tool in await build_server().list_tools()}
        assert "correlate" in names

    asyncio.run(run())


def test_default_surface_lists_exactly_the_expected_tools() -> None:
    async def run() -> None:
        names = sorted(tool.name for tool in await build_server().list_tools())
        assert names == _DEFAULT_TOOLS_WITH_CORRELATE
        # WP05 added rolling_mean + paired_t_test to the default surface (-> 18).
        assert len(names) == len(_DEFAULT_TOOLS_WITH_CORRELATE)

    asyncio.run(run())


def test_correlate_also_on_operator_surface() -> None:
    async def run() -> None:
        default_names = {tool.name for tool in await build_server().list_tools()}
        operator_names = {tool.name for tool in await build_operator_server().list_tools()}
        assert "correlate" in default_names
        assert "correlate" in operator_names

    asyncio.run(run())


# --------------------------------------------------------------------------- #
# Available outcome — full association envelope metadata, serialized.
# --------------------------------------------------------------------------- #
def test_correlate_available_payload_shape(tmp_path: Path) -> None:
    base = _low_autocorr(40)
    db_path = _warehouse_with_pair(tmp_path, base, base)

    payload = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=0,
        expected_direction="positive",
        warehouse_path=db_path,
    )

    assert set(payload) >= {"tool_name", "status", "message", "result"}
    assert payload["tool_name"] == "correlate"
    assert payload["status"] == "available"
    assert isinstance(payload["message"], str) and payload["message"]

    result = payload["result"]
    assert result["refusal"] is None
    est = result["estimate"]
    assert est is not None
    # Spearman rho + direction metadata (contract: available outcome).
    assert est["coefficient_method"] == "spearman_rho"
    assert est["coefficient"] == pytest.approx(1.0)
    assert est["observed_direction"] == "positive"
    assert est["expected_direction"] == "positive"
    assert est["direction_matches_hypothesis"] is True
    assert est["lag_days"] == 0
    # Sample counts + effective sample size + association band.
    assert est["raw_paired_sample_size"] == 40
    assert est["effective_sample_size"] is not None
    band = est["association_band"]
    assert -1.0 <= band["lower"] <= band["upper"] <= 1.0
    # Envelope-level metadata.
    assert result["inputs"] == [_LEFT_METRIC, _RIGHT_METRIC]
    assert result["sample_size"] == 40
    assert result["is_imputed_pct"] is not None
    assert result["validity_status"] is not None
    assert result["parameters"]["lag_days"] == 0
    assert result["parameters"]["expected_direction"] == "positive"
    assert result["parameters"]["overlap_start"] is not None
    assert result["parameters"]["overlap_end"] is not None
    assert isinstance(result["confound_checklist"], list)


def test_correlate_available_payload_is_json_safe_and_byte_stable(tmp_path: Path) -> None:
    base = _low_autocorr(40)
    db_path = _warehouse_with_pair(tmp_path, base, base)

    a = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=0,
        expected_direction="positive",
        warehouse_path=db_path,
    )
    b = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=0,
        expected_direction="positive",
        warehouse_path=db_path,
    )
    # JSON-safe at the boundary and deterministic for identical fixtures.
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_correlate_preserves_common_cause_and_direction_metadata(tmp_path: Path) -> None:
    base = _low_autocorr(60)
    db_path = _warehouse_with_pair(tmp_path, base, base)

    payload = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=0,
        expected_direction="negative",  # opposite the observed +1 association
        common_cause_candidates=["ambient temperature"],
        warehouse_path=db_path,
    )
    assert payload["status"] == "available"
    est = payload["result"]["estimate"]
    # Opposite-direction metadata preserved (observed != expected).
    assert est["observed_direction"] == "positive"
    assert est["expected_direction"] == "negative"
    assert est["direction_matches_hypothesis"] is False
    # Common-cause candidate flows into the confound checklist.
    keys = {c["key"] for c in payload["result"]["confound_checklist"]}
    assert "common_cause_plausible" in keys


# --------------------------------------------------------------------------- #
# Refusal outcome — distinct reason, no estimate, serializes cleanly.
# --------------------------------------------------------------------------- #
def test_correlate_refuses_missing_evidence_with_no_estimate(tmp_path: Path) -> None:
    payload = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=0,
        expected_direction="positive",
        warehouse_path=_empty_warehouse(tmp_path),
    )
    assert payload["status"] == "refused"
    result = payload["result"]
    refusal = result["refusal"]
    assert refusal is not None
    assert refusal["reason"]
    assert refusal["message"]
    assert payload["message"] == refusal["message"]
    # Honesty rule: a refusal carries no estimate / validity metadata.
    assert result["estimate"] is None
    assert result["validity_status"] is None
    # The refusal envelope serializes cleanly to the MCP boundary.
    assert json.loads(json.dumps(payload)) == payload


def test_correlate_refuses_unsupported_lag_with_no_estimate(tmp_path: Path) -> None:
    base = _low_autocorr(40)
    db_path = _warehouse_with_pair(tmp_path, base, base)
    payload = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=99,  # abs(lag) > 14 -> refused
        expected_direction="positive",
        warehouse_path=db_path,
    )
    assert payload["status"] == "refused"
    assert payload["result"]["estimate"] is None
    assert payload["result"]["refusal"]["reason"]


# --------------------------------------------------------------------------- #
# Caller-facing parameter-shape validation (wrapper responsibility only).
# --------------------------------------------------------------------------- #
def test_correlate_rejects_empty_metric_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        server.correlate(
            "  ",
            _RIGHT_METRIC,
            lag_days=0,
            expected_direction="positive",
            warehouse_path=_empty_warehouse(tmp_path),
        )


def test_correlate_rejects_unknown_direction(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        server.correlate(
            _LEFT_METRIC,
            _RIGHT_METRIC,
            lag_days=0,
            expected_direction="up a bit",
            warehouse_path=_empty_warehouse(tmp_path),
        )


# --------------------------------------------------------------------------- #
# Boundary discipline — wrapper DELEGATES; computes/pairs nothing of its own.
# --------------------------------------------------------------------------- #
def test_correlate_delegates_paired_prep_and_dispatch_to_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrapper must build the two series + hypothesis and hand off to the
    engine: ``prepare_paired_input`` then ``invoke_analytical_tool('correlate')``.
    Spy on both engine seams; a future refactor that inlined pairing or the
    statistic would trip this.
    """
    base = _low_autocorr(40)
    db_path = _warehouse_with_pair(tmp_path, base, base)
    seen: dict[str, object] = {}

    real_paired = server.engine.prepare_paired_input
    real_invoke = server.engine.invoke_analytical_tool

    def spy_paired(left, right, hypothesis, **kwargs):  # type: ignore[no-untyped-def]
        seen["paired_called"] = True
        seen["hypothesis"] = hypothesis
        return real_paired(left, right, hypothesis, **kwargs)

    def spy_invoke(tool_name, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen["tool_name"] = tool_name
        return real_invoke(tool_name, *args, **kwargs)

    monkeypatch.setattr(server.engine, "prepare_paired_input", spy_paired)
    monkeypatch.setattr(server.engine, "invoke_analytical_tool", spy_invoke)

    payload = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=0,
        expected_direction="positive",
        warehouse_path=db_path,
    )

    assert payload["status"] == "available"
    assert seen.get("paired_called") is True
    assert seen.get("tool_name") == "correlate"
    # The wrapper built a pre-registered hypothesis and handed it off.
    assert isinstance(seen.get("hypothesis"), server.PreRegisteredAssociationHypothesis)


def test_correlate_wrapper_does_no_statistics_or_network() -> None:
    """Static guard (T020): the wrapper module must not implement statistics,
    raw fact-table analysis, or any network/PubMed work. Statistical primitives,
    pairing logic, and network/HTTP imports belong to the engine — not the MCP
    boundary. This fails if a future change moves computation into MCP.
    """
    source = Path(server.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    forbidden_modules = {
        "requests",
        "httpx",
        "urllib",
        "urllib3",
        "http",
        "socket",
        "aiohttp",
        "scipy",
        "numpy",
        "statistics",
        "pubmed",
    }
    assert not (imported_modules & forbidden_modules), (
        "MCP server must not import statistics/network modules; "
        f"found {imported_modules & forbidden_modules}"
    )

    # Inspect string LITERALS only (not comments/docstrings, which legitimately
    # explain that the engine — not this layer — owns the fact tables and the
    # statistic). Authored fact-table SQL or a computed statistic would surface
    # as a literal here.
    literals = [
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    # Exclude the module docstring (prose, not executable) from SQL-literal scan.
    module_doc = ast.get_docstring(tree)
    sql_literals = [lit for lit in literals if lit != (module_doc or "").lower()]
    for lit in sql_literals:
        assert "from hp.fact_measurement" not in lit, "wrapper must not author fact-table SQL"
        assert "from hp.fact_interval" not in lit, "wrapper must not author fact-table SQL"

    # No statistical computation is *performed* here. Comments/docstrings may
    # name the engine's statistic to explain the boundary, so we scan the
    # executable surface (function/attribute names + literals) rather than prose:
    # a Spearman/rank computation or PubMed/HTTP call would surface as a Name,
    # Attribute, or string literal — never only inside a comment.
    forbidden_call_names = {
        "spearmanr",
        "rankdata",
        "pearsonr",
        "corrcoef",
        "urlopen",
        "get",
        "post",
    }
    forbidden_attr = {"spearman", "spearmanr", "rankdata", "pearsonr"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                assert func.id not in forbidden_call_names, f"MCP wrapper must not call {func.id!r}"
            elif isinstance(func, ast.Attribute):
                assert func.attr not in forbidden_attr, (
                    f"MCP wrapper must not call statistics primitive {func.attr!r}"
                )
    # And no statistical/network library appears as a literal token in code.
    for lit in literals:
        for token in ("scipy.stats", "pubmed.ncbi", "https://", "http://"):
            assert token not in lit, f"MCP wrapper must not embed {token!r}"


def test_correlate_returns_engine_envelope_verbatim(tmp_path: Path) -> None:
    """The serialized result is the engine's envelope to_dict() verbatim: the
    wrapper authored no estimate of its own (method_revision comes from engine).
    """
    base = _low_autocorr(40)
    db_path = _warehouse_with_pair(tmp_path, base, base)

    payload = server.correlate(
        _LEFT_METRIC,
        _RIGHT_METRIC,
        lag_days=0,
        expected_direction="positive",
        warehouse_path=db_path,
    )
    assert payload["status"] == "available"
    assert "method_revision" in payload["result"]["estimate"]
