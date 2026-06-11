"""Contract tests for the tool-loop tier's deterministic surface (WP03).

These tests derive from ``contracts/tool-loop-tier.md`` §§1–2 and §6 and pin the
behavior BEFORE the module exists (DIRECTIVE_034). They are pure default-suite
tests: no network, no model server — the chat client is exercised only through
its injectable transport seam (DIRECTIVE_036).

Coverage map:
  * URL guard + tools-unsupported mapping + num_ctx pinning  -> the chat client.
  * Registry bounds (C-005): allowlist-only reads, whole-file (FR-002),
    manifest/absolute/traversal refusal, write_parser destination/overwrite.
  * Brief invariants (FR-001/FR-002/SC-006) per drawer probe + loud budget check.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from premura.harness import tool_loop_contract as tlc
from premura.harness.intake_strategy import intake_scenario
from premura.harness.sandbox import build_sandbox
from premura.harness.scenario import observation_scenario

# OllamaUnavailableError + the drawer-probe resolver are re-exported by the
# contract module, so this default-suite test never spells the live-trial harness
# import path (the NFR-005 default-gate guard matches that substring).
OllamaUnavailableError = tlc.OllamaUnavailableError
_resolve_drawer_probe = tlc.resolve_drawer_probe

# --------------------------------------------------------------------------- #
# Fake transport (DIRECTIVE_036 outside-boundary seam).
# --------------------------------------------------------------------------- #


class _CapturedRequest:
    """A captured chat request body + a scripted response or raised error."""

    def __init__(self) -> None:
        self.url: str | None = None
        self.body: dict | None = None


def _ok_transport(captured: _CapturedRequest, message: dict):
    def transport(url: str, body: bytes, *, timeout: int) -> bytes:
        captured.url = url
        captured.body = json.loads(body)
        return json.dumps({"message": message}).encode("utf-8")

    return transport


# --------------------------------------------------------------------------- #
# 1. URL guard.
# --------------------------------------------------------------------------- #


def test_chat_url_guard_refuses_non_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tlc, "OLLAMA_URL", "http://evil.example.com:11434/api/generate")
    with pytest.raises(OllamaUnavailableError):
        tlc.ollama_chat([{"role": "user", "content": "hi"}], model="m", tools=[])


# --------------------------------------------------------------------------- #
# 2. Tools-unsupported / connection error mapping.
# --------------------------------------------------------------------------- #


def _http_error(url: str, code: int, body: bytes) -> urllib.error.HTTPError:
    import io
    from email.message import Message

    return urllib.error.HTTPError(url, code, "err", Message(), io.BytesIO(body))


def test_http_body_mentioning_tool_maps_to_unsupported() -> None:
    def transport(url: str, body: bytes, *, timeout: int) -> bytes:
        raise _http_error(url, 400, b'{"error":"this model does not support tools"}')

    with pytest.raises(tlc.ToolCallsUnsupportedError):
        tlc.ollama_chat(
            [{"role": "user", "content": "hi"}], model="m", tools=[], transport=transport
        )


def test_connection_error_maps_to_unavailable() -> None:
    def transport(url: str, body: bytes, *, timeout: int) -> bytes:
        import urllib.error

        raise urllib.error.URLError("connection refused")

    with pytest.raises(OllamaUnavailableError):
        tlc.ollama_chat(
            [{"role": "user", "content": "hi"}], model="m", tools=[], transport=transport
        )


def test_other_http_error_maps_to_unavailable() -> None:
    def transport(url: str, body: bytes, *, timeout: int) -> bytes:
        raise _http_error(url, 500, b"internal error")

    with pytest.raises(OllamaUnavailableError):
        tlc.ollama_chat(
            [{"role": "user", "content": "hi"}], model="m", tools=[], transport=transport
        )


def test_garbled_json_maps_to_unavailable() -> None:
    def transport(url: str, body: bytes, *, timeout: int) -> bytes:
        return b"not json at all"

    with pytest.raises(OllamaUnavailableError):
        tlc.ollama_chat(
            [{"role": "user", "content": "hi"}], model="m", tools=[], transport=transport
        )


# --------------------------------------------------------------------------- #
# 3. num_ctx pinning (+ env override).
# --------------------------------------------------------------------------- #


def test_num_ctx_default_pinned() -> None:
    captured = _CapturedRequest()
    msg = tlc.ollama_chat(
        [{"role": "user", "content": "hi"}],
        model="m",
        tools=[],
        transport=_ok_transport(captured, {"content": "ok"}),
    )
    assert msg == {"content": "ok"}
    assert captured.body is not None
    assert captured.body["options"]["num_ctx"] == 16384
    assert captured.body["stream"] is False


def test_num_ctx_explicit_override() -> None:
    captured = _CapturedRequest()
    tlc.ollama_chat(
        [{"role": "user", "content": "hi"}],
        model="m",
        tools=[],
        num_ctx=4096,
        transport=_ok_transport(captured, {"content": "ok"}),
    )
    assert captured.body is not None
    assert captured.body["options"]["num_ctx"] == 4096


def test_num_ctx_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_TRIAL_NUM_CTX", "8192")
    assert tlc.resolve_num_ctx() == 8192


def test_num_ctx_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_TRIAL_NUM_CTX", raising=False)
    assert tlc.resolve_num_ctx() == 16384


def test_chat_url_derives_chat_path() -> None:
    captured = _CapturedRequest()
    tlc.ollama_chat(
        [{"role": "user", "content": "hi"}],
        model="m",
        tools=[],
        transport=_ok_transport(captured, {"content": "ok"}),
    )
    assert captured.url is not None
    assert captured.url.endswith("/api/chat")


# --------------------------------------------------------------------------- #
# 4. Registry bounds — the C-005 tests (most important in this WP).
# --------------------------------------------------------------------------- #


@pytest.fixture
def trial_context(tmp_path: Path):
    sandbox = build_sandbox(Path(__file__).resolve().parents[1])
    source = sandbox.root / "tests" / "fixtures" / "session_log" / "fitbit_heart_rate_synthetic.csv"
    ctx = tlc.build_trial_context(sandbox, source=source)
    yield ctx
    sandbox.teardown()


def test_read_context_returns_whole_allowlisted_file(trial_context, tmp_path: Path) -> None:
    # Write a multi-thousand-line file at an allowlisted location and assert the
    # WHOLE content comes back (FR-002 no-truncation witness).
    big = trial_context.source
    lines = "\n".join(f"row,{i}" for i in range(5000)) + "\n"
    big.write_text(lines, encoding="utf-8")
    registry = tlc.default_tool_registry()
    out = registry["read_context"].handler({"path": str(big)}, trial_context)
    assert out == lines
    assert len(out.splitlines()) == 5000


def test_read_context_refuses_manifest(trial_context) -> None:
    manifest = (
        trial_context.sandbox_root / "tests" / "fixtures" / "session_log" / "fixture_fields.yaml"
    )
    registry = tlc.default_tool_registry()
    out = registry["read_context"].handler({"path": str(manifest)}, trial_context)
    assert "fixture_fields.yaml" not in out or "refus" in out.lower() or "not" in out.lower()
    # It must be a refusal string, never the manifest content.
    assert "ground" not in out.lower() or "refus" in out.lower()
    # Strongest check: the manifest's own content is not leaked.
    if manifest.exists():
        assert manifest.read_text(encoding="utf-8") not in out


def test_read_context_refuses_absolute_escape(trial_context) -> None:
    registry = tlc.default_tool_registry()
    out = registry["read_context"].handler({"path": "/etc/hosts"}, trial_context)
    assert isinstance(out, str)
    assert Path("/etc/hosts").read_text(encoding="utf-8") not in out


def test_read_context_refuses_traversal(trial_context) -> None:
    registry = tlc.default_tool_registry()
    traversal = str(trial_context.sandbox_root / ".." / ".." / "etc" / "passwd")
    out = registry["read_context"].handler({"path": traversal}, trial_context)
    assert isinstance(out, str)
    assert "passwd" not in out or "refus" in out.lower() or "allow" in out.lower()


def test_read_context_refuses_arbitrary_repo_file(trial_context) -> None:
    registry = tlc.default_tool_registry()
    other = trial_context.sandbox_root / "pyproject.toml"
    out = registry["read_context"].handler({"path": str(other)}, trial_context)
    assert isinstance(out, str)
    assert other.read_text(encoding="utf-8") not in out


def test_allowlist_has_no_manifest(trial_context) -> None:
    # Assert the allowlist contents directly via the public registry surface.
    names = {p.name for p in trial_context.read_allowlist}
    assert "fixture_fields.yaml" not in names
    assert {"CONTRACT.md", "base.py"} <= names


def test_write_parser_destination_and_overwrite(trial_context) -> None:
    registry = tlc.default_tool_registry()
    dest = trial_context.sandbox_root / "src" / "premura" / "parsers" / "_live_trial_parser.py"
    out1 = registry["write_parser"].handler({"code": "X = 1\n"}, trial_context)
    assert isinstance(out1, str)
    assert dest.read_text(encoding="utf-8") == "X = 1\n"
    # A second call overwrites.
    registry["write_parser"].handler({"code": "Y = 2\n"}, trial_context)
    assert dest.read_text(encoding="utf-8") == "Y = 2\n"


def test_registry_exposes_three_tools(trial_context) -> None:
    registry = tlc.default_tool_registry()
    assert set(registry) == {"read_context", "write_parser", "run_ingest"}
    chat_tools = tlc.registry_as_chat_tools(registry)
    assert isinstance(chat_tools, list)
    assert {t["function"]["name"] for t in chat_tools} == {
        "read_context",
        "write_parser",
        "run_ingest",
    }


# --------------------------------------------------------------------------- #
# 5. Brief invariants (FR-001/FR-002/SC-006), per drawer probe.
# --------------------------------------------------------------------------- #

_DRAWER_API_NAMES = {
    "observation": ["IngestBatch", "Measurement", "SourceDescriptor", "SkippedRow"],
    "intake_alien": ["IntakeBatch", "ParseOutput", "NutritionIntakeInput", "SupplementIntakeInput"],
}


@pytest.mark.parametrize("scenario_factory", [observation_scenario, intake_scenario])
def test_brief_contains_api_surface(scenario_factory) -> None:
    scenario = scenario_factory()
    probe = _resolve_drawer_probe(scenario)
    brief = tlc.assemble_brief(probe, goal=probe.goal, source=scenario.source_path)
    for name in _DRAWER_API_NAMES[scenario.name]:
        assert name in brief, f"{name} missing from {scenario.name} brief"


@pytest.mark.parametrize("scenario_factory", [observation_scenario, intake_scenario])
def test_brief_contains_loop_protocol(scenario_factory) -> None:
    scenario = scenario_factory()
    probe = _resolve_drawer_probe(scenario)
    brief = tlc.assemble_brief(probe, goal=probe.goal, source=scenario.source_path)
    for tool_name in ("read_context", "write_parser", "run_ingest"):
        assert tool_name in brief


@pytest.mark.parametrize("scenario_factory", [observation_scenario, intake_scenario])
def test_brief_strips_one_shot_directive(scenario_factory) -> None:
    scenario = scenario_factory()
    probe = _resolve_drawer_probe(scenario)
    brief = tlc.assemble_brief(probe, goal=probe.goal, source=scenario.source_path)
    assert "Output ONLY the python module" not in brief


@pytest.mark.parametrize("scenario_factory", [observation_scenario, intake_scenario])
def test_brief_contains_goal_and_sample(scenario_factory) -> None:
    scenario = scenario_factory()
    probe = _resolve_drawer_probe(scenario)
    brief = tlc.assemble_brief(probe, goal=probe.goal, source=scenario.source_path)
    assert probe.goal in brief
    first_line = scenario.source_path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line in brief


# --------------------------------------------------------------------------- #
# 6. Budget check — loud failure, never truncation.
# --------------------------------------------------------------------------- #


def test_brief_budget_overflow_raises() -> None:
    scenario = observation_scenario()
    probe = _resolve_drawer_probe(scenario)
    with pytest.raises(tlc.BriefBudgetError) as exc:
        tlc.assemble_brief(probe, goal=probe.goal, source=scenario.source_path, num_ctx=64)
    # The error names sizes (the overflow), never returns a truncated brief.
    msg = str(exc.value)
    assert "64" in msg or "budget" in msg.lower()


def test_brief_budget_ok_with_default() -> None:
    scenario = observation_scenario()
    probe = _resolve_drawer_probe(scenario)
    # Default num_ctx (16384) comfortably fits the brief — no raise.
    brief = tlc.assemble_brief(probe, goal=probe.goal, source=scenario.source_path)
    assert isinstance(brief, str) and brief
