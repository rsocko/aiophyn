"""Pure comparisons of fixed read-only history windows; no retention inference."""

from datetime import datetime, timedelta, timezone
import math

if __package__:
    from .test_water_usage_events import PayloadError, number, summarize_usage
else:
    from test_water_usage_events import PayloadError, number, summarize_usage


DAY_MS = 86_400_000


def completed_week(start=None, now=None):
    """Return a completed seven-day UTC interval, optionally starting at a date."""
    now = now or datetime.now(timezone.utc)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if start:
        try:
            beginning = datetime.strptime(start, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            raise ValueError("--history-start must be a UTC date YYYY-MM-DD") from None
        end = beginning + timedelta(days=7)
    else:
        beginning = end - timedelta(days=7)
    if end > now or beginning >= end:
        raise ValueError("History interval must be a completed seven-day UTC interval")
    return int(beginning.timestamp() * 1000), int(end.timestamp() * 1000)


def daily_windows(start, end):
    if end - start != 7 * DAY_MS:
        raise ValueError("History comparison requires exactly seven days")
    return [(start + day * DAY_MS, start + (day + 1) * DAY_MS) for day in range(7)]


def _index(events, start, end):
    summarize_usage(events)
    indexed = {}
    duplicates = outside = crossing = 0
    for event in events:
        identity = event.get("id") or event.get("event_id")
        if not isinstance(identity, str) or not identity:
            raise PayloadError("History events require a nonempty id or event_id")
        opened = number(event.get("open_edge_timestamp"), "open_edge_timestamp")
        closed = number(event.get("close_edge_timestamp"), "close_edge_timestamp")
        if closed < opened:
            raise PayloadError("close_edge_timestamp precedes open_edge_timestamp")
        if not start <= opened < end:
            outside += 1
            continue
        # Ignore identifiers and arbitrary metadata in value comparisons.
        value = (
            opened,
            closed,
            number(event["total_flow"], "total_flow"),
            event.get("latest_suggested_fixtures_result"),
            event.get("latest_user_feedback"),
        )
        if identity in indexed:
            duplicates += 1
            if indexed[identity] != value:
                raise PayloadError("Conflicting duplicate events within one response")
        else:
            indexed[identity] = value
            crossing += closed >= end
    return indexed, duplicates, outside, crossing


def _difference(before, after):
    return {
        "added": len(after.keys() - before.keys()),
        "removed": len(before.keys() - after.keys()),
        "changed": sum(
            before[key] != after[key] for key in before.keys() & after.keys()
        ),
    }


def compare_history(weekly_before, daily, weekly_after, start, end):
    """Compare start-owned [start,end) events; retain boundary/duplicate evidence."""
    windows = daily_windows(start, end)
    if len(daily) != len(windows) or any(response is None for response in daily):
        raise PayloadError("Incomplete daily history; all seven windows must succeed")
    before, before_dups, before_outside, _ = _index(weekly_before, start, end)
    after, after_dups, after_outside, _ = _index(weekly_after, start, end)
    combined = {}
    duplicates = outside = crossing = 0
    for events, (left, right) in zip(daily, windows):
        indexed, repeated, excluded, crosses = _index(events, left, right)
        if combined.keys() & indexed.keys():
            raise PayloadError(
                "Conflicting duplicate event ownership across daily windows"
            )
        combined.update(indexed)
        duplicates += repeated
        outside += excluded
        crossing += crosses
    temporal = _difference(before, after)
    early = _difference(before, combined)
    late = _difference(after, combined)
    return {
        "status": "empty" if not (before or combined or after) else "passed",
        "interval": {
            "from_ts": start,
            "to_ts": end,
            "ownership": "[start,end) by open timestamp",
        },
        "unique_counts": {
            "weekly_before": len(before),
            "daily": len(combined),
            "weekly_after": len(after),
        },
        "total_gallons": {
            "weekly_before": math.fsum(value[2] for value in before.values()),
            "daily": math.fsum(value[2] for value in combined.values()),
            "weekly_after": math.fsum(value[2] for value in after.values()),
        },
        "daily_vs_weekly_before": early,
        "daily_vs_weekly_after": late,
        "weekly_temporal_changes": temporal,
        "possible_late_events": temporal["added"],
        "possible_corrections": temporal["changed"],
        "duplicate_counts": {
            "weekly_before": before_dups,
            "daily": duplicates,
            "weekly_after": after_dups,
        },
        "outside_window_counts": {
            "weekly_before": before_outside,
            "daily": outside,
            "weekly_after": after_outside,
        },
        "daily_boundary_crossing_events": crossing,
        "consistent": not any(early.values())
        and not any(late.values())
        and not any(temporal.values()),
        "retention": "unknown",
        "pagination": "unknown; no paging parameters were sent",
        "physical_classification_accuracy": "not measured",
    }


async def characterize_history(fetch, start, end):
    """Nine sequential reads; exceptions abort rather than becoming empty windows."""
    before = await fetch(start, end)
    daily = []
    for left, right in daily_windows(start, end):
        daily.append(await fetch(left, right))
    after = await fetch(start, end)
    return compare_history(before, daily, after, start, end)
