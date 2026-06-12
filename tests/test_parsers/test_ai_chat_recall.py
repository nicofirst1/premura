"""AI-chat recall intake parser — synthetic fixtures only (no real chat content)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from premura.parsers.ai_chat_recall import FORMAT_MARKER, SOURCE_KIND, AiChatRecallParser
from premura.parsers.base import normalize_parse_output
from premura.store import profile_intake as pi

# One synthetic export exercising every contract feature: day/month/year
# precision, ongoing flag, free-text dose, missing dose, missing since
# (anchors at exported_on), and a chat_date. All wording is invented.
FULL_EXPORT: dict[str, Any] = {
    "format": FORMAT_MARKER,
    "assistant": "claude.ai",
    "exported_on": "2026-06-12",
    "entries": [
        {
            "product_label": "Magnesium Glycinate 400",
            "ingredient_label": "magnesium glycinate",
            "form_label": "capsule",
            "dose": {"amount_num": 400, "unit": "mg"},
            "since": {"date": "2026-03", "precision": "month", "ongoing": True},
            "quote": "I started taking magnesium glycinate around March, still take it nightly.",
            "chat_date": "2026-05-10",
        },
        {
            "ingredient_label": "creatine monohydrate",
            "dose": {"amount_text": "one scoop"},
            "since": {"date": "2026-05-02", "precision": "day"},
            "quote": "Day one of creatine, one scoop in the morning.",
        },
        {
            "product_label": "Vitamin D3",
            "since": {"date": "2024", "precision": "year"},
            "quote": "I've taken vitamin D for a couple of years now.",
        },
        {
            "ingredient_label": "omega-3",
            "quote": "I also take omega-3, not sure since when.",
        },
    ],
}


def _write(tmp_path: Path, doc: dict[str, Any]) -> Path:
    path = tmp_path / "recall.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _parse(path: Path):
    observation, intake = normalize_parse_output(AiChatRecallParser().parse(path))
    assert observation is None, "intake-only parser must emit no observation batch"
    assert intake is not None
    return intake


def _entry(**overrides: Any) -> dict[str, Any]:
    """One valid entry, mutated per test."""
    base: dict[str, Any] = {
        "ingredient_label": "zinc",
        "quote": "I take zinc.",
        "since": {"date": "2026-01-15", "precision": "day"},
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def _doc(*entries: dict[str, Any], **top_overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "format": FORMAT_MARKER,
        "assistant": "claude.ai",
        "exported_on": "2026-06-12",
        "entries": list(entries),
    }
    doc.update(top_overrides)
    return doc


# ----- happy path ----------------------------------------------------------- #


def test_full_export_parses_all_entries(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    batch.validate()
    assert len(batch.supplement_events) == 4
    assert batch.nutrition_events == []
    assert batch.skipped_rows == []
    assert batch.unmapped_metrics == []
    assert all(e.source_kind == SOURCE_KIND for e in batch.supplement_events)
    assert all(e.local_tz is None for e in batch.supplement_events)


def test_assistant_becomes_provenance_source(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    (source_id,) = batch.source_descriptors
    assert source_id == "ai_chat_recall:claude_ai"
    assert batch.source_descriptors[source_id].app_name == "claude.ai"
    assert all(e.source_id == source_id for e in batch.supplement_events)


def test_item_dose_and_quote_land_on_event(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    magnesium = batch.supplement_events[0]
    (item,) = magnesium.items
    assert item.product_label == "Magnesium Glycinate 400"
    assert item.ingredient_label == "magnesium glycinate"
    assert item.form_label == "capsule"
    (dose,) = item.doses
    assert dose.amount_num == 400.0
    assert dose.unit == "mg"
    assert dose.amount_text is None
    assert magnesium.raw_payload is not None
    assert magnesium.raw_payload["quote"].startswith("I started taking magnesium")
    assert magnesium.raw_payload["chat_date"] == "2026-05-10"
    assert magnesium.raw_payload["assistant"] == "claude.ai"


def test_free_text_dose_is_first_class(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    creatine = batch.supplement_events[1]
    (dose,) = creatine.items[0].doses
    assert dose.amount_num is None
    assert dose.amount_text == "one scoop"


def test_missing_dose_stays_representable(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    vitamin_d = batch.supplement_events[2]
    assert vitamin_d.items[0].doses == []


# ----- fuzzy time ----------------------------------------------------------- #


def test_precision_anchors_at_earliest_instant(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    month, day, year, unknown = batch.supplement_events
    assert month.ts_utc == datetime(2026, 3, 1)
    assert day.ts_utc == datetime(2026, 5, 2)
    assert year.ts_utc == datetime(2024, 1, 1)
    assert unknown.ts_utc == datetime(2026, 6, 12)  # anchored at exported_on


def test_precision_and_ongoing_persist_in_raw_payload(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    month, day, year, unknown = batch.supplement_events
    assert month.raw_payload is not None and month.raw_payload["date_precision"] == "month"
    assert month.raw_payload["ongoing"] is True
    assert day.raw_payload is not None and day.raw_payload["date_precision"] == "day"
    assert "ongoing" not in day.raw_payload  # absent stays absent, not fabricated
    assert year.raw_payload is not None and year.raw_payload["date_precision"] == "year"
    assert unknown.raw_payload is not None and unknown.raw_payload["date_precision"] == "unknown"
    assert unknown.raw_payload["exported_on"] == "2026-06-12"


def test_date_precision_contradiction_is_skipped(tmp_path: Path) -> None:
    doc = _doc(_entry(since={"date": "2026-03-15", "precision": "month"}))
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    (skipped,) = batch.skipped_rows
    assert "does not match declared precision" in skipped.reason


def test_unpadded_date_shape_is_skipped_not_leniently_parsed(tmp_path: Path) -> None:
    # strptime alone would accept "2026-6-1"; the strict shape gate must not,
    # or "2026-6" and "2026-06" re-exports would hash to two inventory rows.
    doc = _doc(_entry(since={"date": "2026-6-1", "precision": "day"}))
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    (skipped,) = batch.skipped_rows
    assert "does not match declared precision" in skipped.reason


def test_impossible_calendar_date_is_skipped(tmp_path: Path) -> None:
    doc = _doc(_entry(since={"date": "2026-02-31", "precision": "day"}))
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    (skipped,) = batch.skipped_rows
    assert "not a real calendar date" in skipped.reason


def test_precision_without_date_is_skipped_with_honest_reason(tmp_path: Path) -> None:
    doc = _doc(_entry(since={"precision": "day"}))
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    (skipped,) = batch.skipped_rows
    assert "carries no date" in skipped.reason


def test_unknown_precision_value_is_skipped(tmp_path: Path) -> None:
    doc = _doc(_entry(since={"date": "2026-03", "precision": "approximately"}))
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    (skipped,) = batch.skipped_rows
    assert "since.precision" in skipped.reason


# ----- provenance gate ------------------------------------------------------ #


def test_entry_without_quote_is_skipped_not_loaded(tmp_path: Path) -> None:
    doc = _doc(_entry(quote=None))
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    (skipped,) = batch.skipped_rows
    assert "unverifiable" in skipped.reason
    assert "zinc" in skipped.raw_field


def test_entry_without_any_label_is_skipped(tmp_path: Path) -> None:
    doc = _doc({"quote": "I take something."})
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    (skipped,) = batch.skipped_rows
    assert "neither product_label nor ingredient_label" in skipped.reason


def test_malformed_dose_is_skipped_with_reason(tmp_path: Path) -> None:
    doc = _doc(
        _entry(dose={"unit": "mg"}),
        _entry(ingredient_label="iron", quote="I take iron.", dose={"amount_num": "two"}),
    )
    batch = _parse(_write(tmp_path, doc))
    assert batch.supplement_events == []
    reasons = " | ".join(s.reason for s in batch.skipped_rows)
    assert "neither amount_num nor amount_text" in reasons
    assert "must be a number" in reasons


# ----- declared gaps, never silent drops ------------------------------------ #


def test_unknown_keys_are_declared_unmapped(tmp_path: Path) -> None:
    doc = _doc(
        _entry(frequency="daily", since={"date": "2026-01-15", "precision": "day", "tz": "CET"}),
        mood="optimistic",
    )
    batch = _parse(_write(tmp_path, doc))
    assert len(batch.supplement_events) == 1  # unknown keys never reject the entry
    assert f"vendor:{SOURCE_KIND}:mood" in batch.unmapped_metrics
    assert f"vendor:{SOURCE_KIND}:entry.frequency" in batch.unmapped_metrics
    assert f"vendor:{SOURCE_KIND}:entry.since.tz" in batch.unmapped_metrics


# ----- whole-file rejections ------------------------------------------------ #


def test_wrong_format_marker_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, {"format": "something.else", "entries": []})
    with pytest.raises(ValueError, match="format marker"):
        AiChatRecallParser().parse(path)


def test_fenced_reply_is_tolerated(tmp_path: Path) -> None:
    # Assistants wrap the reply in a fence despite "nothing else"; the user
    # saves it verbatim. One whole-document fence is format-level recovery.
    path = tmp_path / "recall.json"
    path.write_text("```json\n" + json.dumps(_doc(_entry())) + "\n```\n", encoding="utf-8")
    batch = _parse(path)
    assert len(batch.supplement_events) == 1


def test_non_list_entries_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'entries' must be a list"):
        AiChatRecallParser().parse(_write(tmp_path, _doc(entries={"oops": True})))


def test_non_object_entry_and_since_and_ongoing_are_skipped(tmp_path: Path) -> None:
    doc = _doc(
        _entry(since="2026-03"),
        _entry(ingredient_label="iron", quote="I take iron.", since=None),
        _entry(since={"date": "2026-03", "precision": "month", "ongoing": "yes"}),
    )
    doc["entries"].insert(0, "not an object")
    batch = _parse(_write(tmp_path, doc))
    assert len(batch.supplement_events) == 1  # only the iron entry survives
    reasons = " | ".join(s.reason for s in batch.skipped_rows)
    assert "entry is not a JSON object" in reasons
    assert "'since' is not a JSON object" in reasons
    assert "'since.ongoing' must be a boolean" in reasons


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "recall.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        AiChatRecallParser().parse(path)


def test_missing_assistant_or_exported_on_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="assistant"):
        AiChatRecallParser().parse(_write(tmp_path, _doc(assistant="")))
    with pytest.raises(ValueError, match="exported_on"):
        AiChatRecallParser().parse(_write(tmp_path, _doc(exported_on="June 2026")))


def test_empty_entries_is_an_honest_nothing_found(tmp_path: Path) -> None:
    batch = _parse(_write(tmp_path, _doc()))
    assert len(batch) == 0
    batch.validate()


# ----- inbox discovery sniffer ---------------------------------------------- #


def test_discovery_sniffer_routes_documents_not_prompts(tmp_path: Path) -> None:
    from premura.cli import _json_is_chat_recall

    bare = _write(tmp_path, _doc(_entry()))
    assert _json_is_chat_recall(bare)

    fenced = tmp_path / "fenced.json"
    fenced.write_text("```json\n" + json.dumps(_doc(_entry())) + "\n```\n", encoding="utf-8")
    assert _json_is_chat_recall(fenced)

    # A saved paste-prompt mentions the marker but is prose, not a document;
    # routing it to the parser would fail the whole `ingest --source all` run.
    prompt = tmp_path / "prompt.json"
    prompt.write_text(
        f'Search our entire conversation history... reply in this format: "{FORMAT_MARKER}" ...',
        encoding="utf-8",
    )
    assert not _json_is_chat_recall(prompt)

    unrelated = tmp_path / "unrelated.json"
    unrelated.write_text('{"some": "other json"}', encoding="utf-8")
    assert not _json_is_chat_recall(unrelated)


# ----- idempotency ---------------------------------------------------------- #


def test_dedupe_key_stable_across_reexports(tmp_path: Path) -> None:
    a = _parse(_write(tmp_path, FULL_EXPORT))
    later = dict(FULL_EXPORT, exported_on="2026-07-01")
    b = _parse(_write(tmp_path, later))
    # Re-stating the same recalled facts later must produce the same keys for
    # since-dated entries; only the since-less entry re-anchors (and its key is
    # since-independent, so it still dedupes).
    keys_a = [e.dedupe_key for e in a.supplement_events]
    keys_b = [e.dedupe_key for e in b.supplement_events]
    assert keys_a == keys_b
    assert len({e.dedupe_key for e in a.supplement_events}) == 4


def test_duplicate_entry_in_one_export_is_skipped_not_fatal(tmp_path: Path) -> None:
    # A duplicated item is this source class's own failure mode (assistant
    # recall); the second occurrence must skip with a reason, not blow up the
    # whole batch on within-batch dedupe uniqueness.
    doc = _doc(_entry(), _entry(dose={"amount_num": 15, "unit": "mg"}))
    batch = _parse(_write(tmp_path, doc))
    batch.validate()
    assert len(batch.supplement_events) == 1
    (skipped,) = batch.skipped_rows
    assert "duplicate of an earlier entry" in skipped.reason
    assert "first occurrence wins" in skipped.reason


def test_declares_no_observation_metrics() -> None:
    assert AiChatRecallParser().declares_metrics() == []


# ----- round-trip into the warehouse ---------------------------------------- #


def test_round_trip_persists_under_ai_chat_recall(tmp_path: Path, empty_warehouse) -> None:
    batch = _parse(_write(tmp_path, FULL_EXPORT))
    stats = pi.persist_intake_batch(empty_warehouse, batch)
    assert stats.supplement_events_inserted == 4

    rows = empty_warehouse.execute(
        """
        SELECT s.source_kind, e.ts_utc, i.product_label, i.ingredient_label,
               json_extract_string(e.raw_payload, '$.date_precision'),
               json_extract_string(e.raw_payload, '$.quote')
        FROM hp.supplement_intake_event e
        JOIN hp.dim_source s USING (source_id)
        JOIN hp.supplement_item i ON i.supplement_event_id = e.supplement_event_id
        ORDER BY e.ts_utc
        """
    ).fetchall()
    assert len(rows) == 4
    assert all(r[0] == SOURCE_KIND for r in rows)
    # The honesty markers must be queryable from the persisted row, not just
    # present on the in-memory batch: that is where a signal would read them.
    assert {r[4] for r in rows} == {"day", "month", "year", "unknown"}
    assert all(r[5] for r in rows)

    # Re-ingesting the same export is a no-op (dedupe_key idempotency).
    stats2 = pi.persist_intake_batch(empty_warehouse, _parse(_write(tmp_path, FULL_EXPORT)))
    assert stats2.supplement_events_inserted == 0
    assert stats2.supplement_events_skipped_dup == 4
