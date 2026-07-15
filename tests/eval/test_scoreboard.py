"""Unit tests for the kept run record + capability-floor scoreboard (WP02).

Default-collected: no model server, no warehouse — pure storage behavior. Covers
append/read/order integrity, malformed-line tolerance, the real-data no-persist
PHI guard (FR-012/NFR-002), synthetic persistence, and the floor query (FR-011).
"""

from __future__ import annotations

from pathlib import Path

from premura.harness.scoreboard import (
    LiveTrialRunRecord,
    ScoreboardEntry,
    append_scoreboard,
    current_floor,
    persist_run,
    read_scoreboard,
)


def _entry(
    ts: str,
    operator_model: str = "qwen2.5-coder:7b",
    *,
    first_attempt_pass: bool = False,
    final_pass: bool = True,
    driver_model: str = "driver:1",
    attempts_used: int = 2,
) -> ScoreboardEntry:
    return ScoreboardEntry(
        ts=ts,
        operator_model=operator_model,
        driver_model=driver_model,
        attempts_used=attempts_used,
        first_attempt_pass=first_attempt_pass,
        final_pass=final_pass,
    )


def _verdict(passed: bool) -> dict:
    return {
        "passed": passed,
        "rules": {
            "loaded": {"passed": passed},
            "runtime_valid": {"passed": passed},
            "honest_about_gaps": {"passed": passed},
        },
    }


def test_append_then_read_preserves_count_and_order(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    written = [_entry(f"2026-06-03T00:0{i}:00Z") for i in range(5)]
    for entry in written:
        append_scoreboard(entry, path=board)

    read = read_scoreboard(path=board)
    assert len(read) == 5
    assert [e.ts for e in read] == [e.ts for e in written]
    assert read[0] == written[0]
    assert read[-1] == written[-1]


def test_append_is_append_only_never_rewrites(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    append_scoreboard(_entry("2026-06-03T00:00:00Z"), path=board)
    first_line = board.read_text(encoding="utf-8")
    append_scoreboard(_entry("2026-06-03T00:01:00Z"), path=board)
    # The original first line must be unchanged (a prefix of the new content).
    assert board.read_text(encoding="utf-8").startswith(first_line)


def test_read_skips_malformed_line_without_dropping_rest(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    good_a = _entry("2026-06-03T00:00:00Z")
    good_b = _entry("2026-06-03T00:02:00Z")
    board.write_text(
        good_a.to_json_line()
        + "\n"
        + "{ this is not valid json ]\n"
        + good_b.to_json_line()
        + "\n",
        encoding="utf-8",
    )

    read = read_scoreboard(path=board)
    assert [e.ts for e in read] == [good_a.ts, good_b.ts]


def test_read_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_scoreboard(path=tmp_path / "nope.jsonl") == []


def test_persist_run_real_data_writes_nothing(tmp_path: Path) -> None:
    """Hard PHI boundary: a real-data run persists zero files (FR-012/NFR-002)."""
    runs_dir = tmp_path / "live_trials"
    kept_log = tmp_path / "session_log.duckdb"
    kept_log.write_bytes(b"DUCKDB-FAKE")  # outside runs_dir; must not be copied

    record = LiveTrialRunRecord(
        operator_model="qwen2.5-coder:7b",
        driver_model="driver:1",
        attempts_used=1,
        first_attempt_verdict=_verdict(True),
        final_verdict=_verdict(True),
    )

    result = persist_run(
        record,
        kept_session_log=kept_log,
        verdict=_verdict(True),
        is_synthetic=False,
        runs_dir=runs_dir,
    )

    assert result is None
    # Zero files anywhere under runs_dir — no dir created, nothing copied.
    assert not runs_dir.exists()
    assert list(tmp_path.rglob("*")) == [kept_log]


def test_persist_run_synthetic_writes_run_dir(tmp_path: Path) -> None:
    runs_dir = tmp_path / "live_trials"
    kept_log = tmp_path / "session_log.duckdb"
    kept_log.write_bytes(b"DUCKDB-FAKE")

    verdict = _verdict(True)
    record = LiveTrialRunRecord(
        operator_model="qwen2.5-coder:7b",
        driver_model="driver:1",
        attempts_used=2,
        first_attempt_verdict=_verdict(False),
        final_verdict=verdict,
    )

    run_dir = persist_run(
        record,
        kept_session_log=kept_log,
        verdict=verdict,
        is_synthetic=True,
        runs_dir=runs_dir,
    )

    assert run_dir is not None
    assert run_dir.parent == runs_dir
    # Filesystem-safe slug: ':' replaced.
    assert ":" not in run_dir.name
    assert run_dir.name.endswith("-qwen2.5-coder-7b")

    session_copy = run_dir / "session_log.duckdb"
    verdict_file = run_dir / "verdict.json"
    assert session_copy.read_bytes() == b"DUCKDB-FAKE"
    import json

    assert json.loads(verdict_file.read_text(encoding="utf-8")) == verdict


def test_current_floor_first_vs_final_and_reaches(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    # tier A: never first-pass, but reaches final pass via retry.
    append_scoreboard(
        _entry("2026-06-03T00:00:00Z", "model-a", first_attempt_pass=False, final_pass=True),
        path=board,
    )
    append_scoreboard(
        _entry("2026-06-03T00:01:00Z", "model-a", first_attempt_pass=True, final_pass=True),
        path=board,
    )
    # tier B: never passes final at all.
    append_scoreboard(
        _entry("2026-06-03T00:02:00Z", "model-b", first_attempt_pass=False, final_pass=False),
        path=board,
    )

    floor = current_floor(read_scoreboard(path=board))

    # Tier-less entries group under (model, "one_shot") (legacy default).
    assert floor[("model-a", "one_shot")]["runs"] == 2
    assert floor[("model-a", "one_shot")]["first_attempt_pass_runs"] == 1
    assert floor[("model-a", "one_shot")]["final_pass_runs"] == 2
    assert floor[("model-a", "one_shot")]["reaches_final_pass"] is True
    assert floor[("model-a", "one_shot")]["last_ts"] == "2026-06-03T00:01:00Z"

    assert floor[("model-b", "one_shot")]["runs"] == 1
    assert floor[("model-b", "one_shot")]["reaches_final_pass"] is False
    assert floor[("model-b", "one_shot")]["final_pass_runs"] == 0


def test_scoreboard_entry_json_roundtrip() -> None:
    entry = _entry("2026-06-03T00:00:00Z", first_attempt_pass=True, final_pass=False)
    import json

    obj = json.loads(entry.to_json_line())
    assert ScoreboardEntry.from_json(obj) == entry


# --- WP01: tier axis (FR-007, SC-002, C-002, contract §5) ---------------------


def test_entry_default_tier_is_one_shot() -> None:
    """Constructing an entry without `tier` defaults to "one_shot" (keeps the
    untouched one-shot writer correct)."""
    entry = _entry("2026-06-03T00:00:00Z")
    assert entry.tier == "one_shot"


def test_record_default_tier_is_one_shot() -> None:
    """`LiveTrialRunRecord` default `tier` is "one_shot" (both tiers are live trials)."""
    record = LiveTrialRunRecord(
        operator_model="qwen2.5-coder:7b",
        driver_model="driver:1",
        attempts_used=1,
        first_attempt_verdict=_verdict(True),
        final_verdict=_verdict(True),
    )
    assert record.run_kind == "live_trial"
    assert record.tier == "one_shot"


def test_to_json_line_includes_tier() -> None:
    """An explicit tier is serialized under the "tier" key (parse, don't string-match)."""
    import json

    entry = ScoreboardEntry(
        ts="2026-06-03T00:00:00Z",
        operator_model="qwen2.5-coder:7b",
        driver_model="driver:1",
        attempts_used=2,
        first_attempt_pass=False,
        final_pass=True,
        tier="tool_loop",
    )
    obj = json.loads(entry.to_json_line())
    assert obj["tier"] == "tool_loop"


def test_from_json_legacy_line_defaults_to_one_shot() -> None:
    """A parsed object with no `tier` key reconstructs as tier="one_shot" (contract §5)."""
    legacy = {
        "ts": "2026-06-03T00:00:00Z",
        "operator_model": "qwen2.5-coder:7b",
        "driver_model": "driver:1",
        "attempts_used": 1,
        "first_attempt_pass": False,
        "final_pass": True,
    }
    entry = ScoreboardEntry.from_json(legacy)
    assert entry.tier == "one_shot"


def test_from_json_roundtrips_tier_when_present() -> None:
    import json

    entry = ScoreboardEntry(
        ts="2026-06-03T00:00:00Z",
        operator_model="qwen2.5-coder:7b",
        driver_model="driver:1",
        attempts_used=2,
        first_attempt_pass=True,
        final_pass=True,
        tier="tool_loop",
    )
    assert ScoreboardEntry.from_json(json.loads(entry.to_json_line())) == entry


def test_read_scoreboard_mixes_legacy_and_tool_loop_lines(tmp_path: Path) -> None:
    """A JSONL with one tier-less legacy line and one tool_loop line returns both
    entries with the right tiers (write via path kwarg; never touch data/)."""
    board = tmp_path / "scoreboard.jsonl"
    legacy_line = (
        '{"attempts_used": 1, "driver_model": "driver:1", "final_pass": true, '
        '"first_attempt_pass": false, "operator_model": "model-a", '
        '"ts": "2026-06-03T00:00:00Z"}'
    )
    tool_loop_entry = ScoreboardEntry(
        ts="2026-06-03T00:01:00Z",
        operator_model="model-a",
        driver_model="driver:1",
        attempts_used=3,
        first_attempt_pass=False,
        final_pass=True,
        tier="tool_loop",
    )
    board.write_text(legacy_line + "\n" + tool_loop_entry.to_json_line() + "\n", encoding="utf-8")

    read = read_scoreboard(path=board)
    assert [e.tier for e in read] == ["one_shot", "tool_loop"]


def test_current_floor_groups_by_model_and_tier(tmp_path: Path) -> None:
    """The same model under both tiers yields two distinct floor rows; a legacy
    (tier-less) entry lands under (model, "one_shot") (SC-002)."""
    board = tmp_path / "scoreboard.jsonl"
    legacy_line = (
        '{"attempts_used": 1, "driver_model": "driver:1", "final_pass": true, '
        '"first_attempt_pass": false, "operator_model": "model-a", '
        '"ts": "2026-06-03T00:00:00Z"}'
    )
    board.write_text(legacy_line + "\n", encoding="utf-8")
    append_scoreboard(
        ScoreboardEntry(
            ts="2026-06-03T00:01:00Z",
            operator_model="model-a",
            driver_model="driver:1",
            attempts_used=3,
            first_attempt_pass=False,
            final_pass=True,
            tier="tool_loop",
        ),
        path=board,
    )

    floor = current_floor(read_scoreboard(path=board))

    assert ("model-a", "one_shot") in floor
    assert ("model-a", "tool_loop") in floor
    assert floor[("model-a", "one_shot")]["runs"] == 1
    assert floor[("model-a", "tool_loop")]["runs"] == 1


def test_format_floor_renders_both_tier_labels() -> None:
    """The rendered table contains both tier labels on separate lines (SC-002)."""
    from premura.harness.scoreboard import _format_floor

    floor = current_floor(
        [
            ScoreboardEntry(
                ts="2026-06-03T00:00:00Z",
                operator_model="model-a",
                driver_model="driver:1",
                attempts_used=1,
                first_attempt_pass=False,
                final_pass=True,
                tier="one_shot",
            ),
            ScoreboardEntry(
                ts="2026-06-03T00:01:00Z",
                operator_model="model-a",
                driver_model="driver:1",
                attempts_used=3,
                first_attempt_pass=False,
                final_pass=True,
                tier="tool_loop",
            ),
        ]
    )
    rendered = _format_floor(floor)
    one_shot_lines = [ln for ln in rendered.splitlines() if "one_shot" in ln]
    tool_loop_lines = [ln for ln in rendered.splitlines() if "tool_loop" in ln]
    assert len(one_shot_lines) == 1
    assert len(tool_loop_lines) == 1


def test_one_shot_writer_call_shape_serializes_one_shot() -> None:
    """Mirror how the untouched one-shot writer builds the record/entry today
    (no `tier` argument) and assert the serialized line carries
    "tier": "one_shot" (C-002, NFR-004)."""
    import json

    # Call shape: keyword construction with no tier argument, as the one-shot
    # writer does. We do not import the private writer; we mirror its call.
    record = LiveTrialRunRecord(
        operator_model="qwen2.5-coder:7b",
        driver_model="driver:1",
        attempts_used=2,
        first_attempt_verdict=_verdict(False),
        final_verdict=_verdict(True),
    )
    entry = ScoreboardEntry(
        ts="2026-06-03T00:00:00Z",
        operator_model=record.operator_model,
        driver_model=record.driver_model,
        attempts_used=record.attempts_used,
        first_attempt_pass=record.first_attempt_verdict["passed"],
        final_pass=record.final_verdict["passed"],
    )
    assert record.tier == "one_shot"
    assert json.loads(entry.to_json_line())["tier"] == "one_shot"
