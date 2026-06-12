"""Store boundary for operator-declared condition episodes (migration 007).

Locks the capture semantics: append-only declarations, supersede-to-correct
with history, retract-to-withdraw with a reason, the non-overlapping current
set per label, ongoing (no end_day) episodes as record-keeping only, and the
closed-episodes analysis read path. Synthetic warehouses only.
"""

from __future__ import annotations

from datetime import date

import pytest

from premura.store import condition_episodes as ce

# ----- recording ------------------------------------------------------------ #


def test_record_and_read_back(empty_warehouse) -> None:
    episode_id = ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
        note="declared during checkup prep",
    )
    record = ce.get_condition_episode(empty_warehouse, episode_id)
    assert record is not None
    assert record.condition_label == "cold"
    assert record.start_day == date(2026, 3, 3)
    assert record.end_day == date(2026, 3, 10)
    assert record.source_kind == ce.DEFAULT_CONDITION_SOURCE_KIND
    assert record.is_current and not record.is_ongoing
    assert record.note == "declared during checkup prep"


def test_label_is_operator_vocabulary_but_never_empty(empty_warehouse) -> None:
    with pytest.raises(ce.ConditionEpisodeError, match="non-empty"):
        ce.record_condition_episode(
            empty_warehouse, condition_label="   ", start_day=date(2026, 1, 1)
        )
    # Any non-empty string is acceptable — no enum, no registry.
    assert ce.record_condition_episode(
        empty_warehouse,
        condition_label="that weird week after the move",
        start_day=date(2026, 1, 1),
        end_day=date(2026, 1, 7),
    )


def test_backwards_range_is_refused(empty_warehouse) -> None:
    with pytest.raises(ce.ConditionEpisodeError, match="not be before"):
        ce.record_condition_episode(
            empty_warehouse,
            condition_label="cold",
            start_day=date(2026, 3, 10),
            end_day=date(2026, 3, 3),
        )


def test_ongoing_episode_is_recordable(empty_warehouse) -> None:
    episode_id = ce.record_condition_episode(
        empty_warehouse, condition_label="new_medication", start_day=date(2026, 5, 1)
    )
    record = ce.get_condition_episode(empty_warehouse, episode_id)
    assert record is not None and record.is_ongoing
    assert record.to_dict()["ongoing"] is True


# ----- the non-overlapping current set -------------------------------------- #


def test_overlapping_current_same_label_is_refused(empty_warehouse) -> None:
    ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
    )
    with pytest.raises(ce.ConditionEpisodeError, match="overlaps current episode"):
        ce.record_condition_episode(
            empty_warehouse,
            condition_label="cold",
            start_day=date(2026, 3, 8),
            end_day=date(2026, 3, 15),
        )


def test_ongoing_episode_blocks_later_overlap(empty_warehouse) -> None:
    ce.record_condition_episode(empty_warehouse, condition_label="med", start_day=date(2026, 5, 1))
    with pytest.raises(ce.ConditionEpisodeError, match="ongoing"):
        ce.record_condition_episode(
            empty_warehouse,
            condition_label="med",
            start_day=date(2026, 6, 1),
            end_day=date(2026, 6, 5),
        )


def test_same_days_different_label_do_not_conflict(empty_warehouse) -> None:
    ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
    )
    assert ce.record_condition_episode(
        empty_warehouse,
        condition_label="travel",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
    )


def test_adjacent_non_overlapping_episodes_are_fine(empty_warehouse) -> None:
    ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
    )
    assert ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 11),
        end_day=date(2026, 3, 15),
    )


# ----- supersede (correct) and retract (withdraw) ---------------------------- #


def test_supersede_keeps_history_and_replaces_current(empty_warehouse) -> None:
    original = ce.record_condition_episode(
        empty_warehouse, condition_label="med", start_day=date(2026, 5, 1)
    )
    corrected = ce.record_condition_episode(
        empty_warehouse,
        condition_label="med",
        start_day=date(2026, 5, 1),
        end_day=date(2026, 6, 1),
        supersedes_episode_id=original,
    )
    old = ce.get_condition_episode(empty_warehouse, original)
    new = ce.get_condition_episode(empty_warehouse, corrected)
    assert old is not None and old.superseded_at is not None and not old.is_current
    assert new is not None and new.is_current
    assert new.supersedes_episode_id == original

    current = ce.list_condition_episodes(empty_warehouse, condition_label="med")
    assert [r.episode_id for r in current] == [corrected]
    history = ce.list_condition_episodes(
        empty_warehouse, condition_label="med", include_history=True
    )
    assert {r.episode_id for r in history} == {original, corrected}


def test_supersede_missing_or_stale_target_is_refused(empty_warehouse) -> None:
    with pytest.raises(ce.ConditionEpisodeError, match="does not exist"):
        ce.record_condition_episode(
            empty_warehouse,
            condition_label="med",
            start_day=date(2026, 5, 1),
            supersedes_episode_id=999,
        )
    original = ce.record_condition_episode(
        empty_warehouse, condition_label="med", start_day=date(2026, 5, 1)
    )
    corrected = ce.record_condition_episode(
        empty_warehouse,
        condition_label="med",
        start_day=date(2026, 5, 1),
        end_day=date(2026, 6, 1),
        supersedes_episode_id=original,
    )
    assert corrected
    with pytest.raises(ce.ConditionEpisodeError, match="already superseded"):
        ce.record_condition_episode(
            empty_warehouse,
            condition_label="med",
            start_day=date(2026, 5, 2),
            supersedes_episode_id=original,
        )


def test_failed_write_rolls_back_the_supersession(empty_warehouse) -> None:
    # The supersession UPDATE and the overlap refusal share one transaction: a
    # refused insert must not leave the superseded row closed.
    ce.record_condition_episode(  # the blocker the refused insert overlaps
        empty_warehouse,
        condition_label="med",
        start_day=date(2026, 7, 1),
        end_day=date(2026, 7, 10),
    )
    target = ce.record_condition_episode(
        empty_warehouse,
        condition_label="med",
        start_day=date(2026, 5, 1),
        end_day=date(2026, 5, 10),
    )
    with pytest.raises(ce.ConditionEpisodeError, match="overlaps"):
        ce.record_condition_episode(
            empty_warehouse,
            condition_label="med",
            start_day=date(2026, 7, 5),  # overlaps the blocker
            end_day=date(2026, 7, 20),
            supersedes_episode_id=target,
        )
    unchanged = ce.get_condition_episode(empty_warehouse, target)
    assert unchanged is not None and unchanged.is_current


def test_retract_withdraws_with_reason_and_keeps_row(empty_warehouse) -> None:
    episode_id = ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
    )
    record = ce.retract_condition_episode(
        empty_warehouse, episode_id, reason="was actually allergies, not a cold"
    )
    assert record.retracted_at is not None
    assert record.retraction_reason == "was actually allergies, not a cold"
    assert ce.list_condition_episodes(empty_warehouse, condition_label="cold") == []
    history = ce.list_condition_episodes(
        empty_warehouse, condition_label="cold", include_history=True
    )
    assert [r.episode_id for r in history] == [episode_id]


def test_retract_requires_reason_and_current_target(empty_warehouse) -> None:
    with pytest.raises(ce.ConditionEpisodeError, match="reason"):
        ce.retract_condition_episode(empty_warehouse, 1, reason="  ")
    with pytest.raises(ce.ConditionEpisodeError, match="does not exist"):
        ce.retract_condition_episode(empty_warehouse, 999, reason="oops")
    episode_id = ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 4),
    )
    ce.retract_condition_episode(empty_warehouse, episode_id, reason="wrong dates")
    with pytest.raises(ce.ConditionEpisodeError, match="already retracted"):
        ce.retract_condition_episode(empty_warehouse, episode_id, reason="again")


def test_retracted_episode_frees_its_days(empty_warehouse) -> None:
    episode_id = ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
    )
    ce.retract_condition_episode(empty_warehouse, episode_id, reason="wrong dates")
    assert ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 4),
        end_day=date(2026, 3, 9),
    )


# ----- the analysis read path ------------------------------------------------ #


def test_closed_episodes_for_label_is_the_analyzable_set(empty_warehouse) -> None:
    second = ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 4, 20),
        end_day=date(2026, 4, 25),
    )
    first = ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 3, 3),
        end_day=date(2026, 3, 10),
    )
    ce.record_condition_episode(  # ongoing: excluded from analysis
        empty_warehouse, condition_label="cold", start_day=date(2026, 6, 1)
    )
    retracted = ce.record_condition_episode(
        empty_warehouse,
        condition_label="cold",
        start_day=date(2026, 1, 1),
        end_day=date(2026, 1, 5),
    )
    ce.retract_condition_episode(empty_warehouse, retracted, reason="wrong")
    ce.record_condition_episode(  # different label: excluded
        empty_warehouse,
        condition_label="travel",
        start_day=date(2026, 2, 1),
        end_day=date(2026, 2, 5),
    )

    closed = ce.closed_episodes_for_label(empty_warehouse, "cold")
    # Ascending start order, closed + current only.
    assert [r.episode_id for r in closed] == [first, second]
    assert all(r.end_day is not None for r in closed)
