"""Hand-built history comparisons; timestamps intentionally span midnight."""

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from examples.history import (
    DAY_MS,
    characterize_history,
    compare_history,
    completed_week,
)
from examples.test_water_usage_events import PayloadError

START = 1_735_689_600_000  # 2025-01-01 00:00 UTC
END = START + 7 * DAY_MS


def item(identity, opened, closed=None, flow=2):
    return {
        "id": identity,
        "open_edge_timestamp": opened,
        "close_edge_timestamp": closed if closed is not None else opened + 1000,
        "total_flow": flow,
    }


def test_completed_week_and_old_selected_week():
    now = datetime(2025, 1, 10, 12, tzinfo=timezone.utc)
    assert completed_week("2025-01-01", now) == (START, END)
    assert completed_week(now=now) == (START + 2 * DAY_MS, END + 2 * DAY_MS)
    with pytest.raises(ValueError, match="completed"):
        completed_week("2025-01-10", now)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        completed_week("invalid", now)


def test_overlap_and_exact_boundaries_are_counted_once():
    first = item("a", START, START + DAY_MS + 100, 2)
    midnight = item("b", START + DAY_MS, flow=3)
    excluded = item("outside", END, flow=99)
    # The API may return crossing/endpoint events in both neighboring windows.
    daily = [[first, first, midnight], [first, midnight], [], [], [], [], [excluded]]
    result = compare_history(
        [first, midnight, excluded], daily, [first, midnight], START, END
    )
    assert result["unique_counts"] == {
        "weekly_before": 2,
        "daily": 2,
        "weekly_after": 2,
    }
    assert result["consistent"]
    assert result["total_gallons"] == {
        "weekly_before": 5,
        "daily": 5,
        "weekly_after": 5,
    }
    assert result["duplicate_counts"]["daily"] == 1
    assert result["outside_window_counts"] == {
        "weekly_before": 1,
        "daily": 3,
        "weekly_after": 0,
    }
    assert result["daily_boundary_crossing_events"] == 1
    assert result["retention"] == "unknown"


def test_missing_added_changed_and_temporal_evidence():
    original = item("a", START, flow=2)
    changed = item("a", START, flow=3)
    missing = item("missing-in-daily", START + DAY_MS, flow=4)
    late = item("late", START + 2 * DAY_MS, flow=5)
    daily = [[changed], [], [late], [], [], [], []]
    result = compare_history(
        [original, missing], daily, [changed, missing, late], START, END
    )
    assert result["daily_vs_weekly_before"] == {"added": 1, "removed": 1, "changed": 1}
    assert result["daily_vs_weekly_after"] == {"added": 0, "removed": 1, "changed": 0}
    assert result["weekly_temporal_changes"] == {"added": 1, "removed": 0, "changed": 1}
    assert result["possible_late_events"] == result["possible_corrections"] == 1
    assert not result["consistent"]
    assert result["total_gallons"] == {
        "weekly_before": 6,
        "daily": 8,
        "weekly_after": 12,
    }


def test_feedback_and_prediction_changes_are_value_changes():
    original = item("a", START)
    changed = deepcopy(original)
    changed["latest_user_feedback"] = {"fixture_id": 7}
    result = compare_history(
        [original], [[changed], [], [], [], [], [], []], [changed], START, END
    )
    assert result["weekly_temporal_changes"]["changed"] == 1


@pytest.mark.parametrize("daily", [[], [[]] * 6, [None] + [[]] * 6])
def test_partial_windows_cannot_be_reported_as_empty(daily):
    with pytest.raises(PayloadError, match="Incomplete"):
        compare_history([], daily, [], START, END)


@pytest.mark.parametrize(
    "bad",
    [
        {
            "total_flow": 2,
            "open_edge_timestamp": START,
            "close_edge_timestamp": START + 1,
        },
        {
            "id": "a",
            "total_flow": 2,
            "open_edge_timestamp": START,
            "close_edge_timestamp": START - 1,
        },
        {
            "id": "a",
            "total_flow": 2,
            "open_edge_timestamp": None,
            "close_edge_timestamp": START,
        },
    ],
)
def test_invalid_history_event_fails(bad):
    with pytest.raises(PayloadError):
        compare_history([bad], [[]] * 7, [], START, END)


def test_conflicting_duplicate_fails():
    with pytest.raises(PayloadError, match="Conflicting duplicate"):
        compare_history(
            [item("a", START), item("a", START, flow=3)], [[]] * 7, [], START, END
        )


def test_changed_timestamp_cannot_silently_overwrite_daily_event():
    first = item("a", START)
    moved = item("a", START + DAY_MS)
    with pytest.raises(PayloadError, match="ownership across daily"):
        compare_history(
            [first], [[first], [moved], [], [], [], [], []], [moved], START, END
        )


def test_empty_history_does_not_prove_retention():
    result = compare_history([], [[]] * 7, [], START, END)
    assert result["status"] == "empty"
    assert result["retention"] == "unknown"


@pytest.mark.asyncio
async def test_history_read_order_is_fixed_and_bounded():
    fetch = AsyncMock(return_value=[])
    result = await characterize_history(fetch, START, END)
    bounds = [call.args for call in fetch.call_args_list]
    assert bounds == [(START, END)] + [
        (START + day * DAY_MS, START + (day + 1) * DAY_MS) for day in range(7)
    ] + [(START, END)]
    assert result["status"] == "empty"


@pytest.mark.asyncio
async def test_partial_request_failure_aborts_without_retries():
    fetch = AsyncMock(side_effect=[[], [], RuntimeError("synthetic request failure")])
    with pytest.raises(RuntimeError, match="synthetic request failure"):
        await characterize_history(fetch, START, END)
    assert fetch.await_count == 3
