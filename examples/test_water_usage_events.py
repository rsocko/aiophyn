"""Test water usage events with fixture predictions.

This script validates the get_water_usage_events() method added to the aiophyn
Device class. It fetches recent water usage events and displays the fixture
predictions returned by the Phyn ML pipeline.

Derived from: ideation/experiments/home-automation/phyn-api-exploration/scripts/
  - water_usage_events_test.py
  - fixture_analyzer.py

Usage:
    1. Copy .env.example to .env and fill in your credentials
    2. Run: python test_water_usage_events.py
       Optional: python test_water_usage_events.py --days 1,7,30 --low-confidence-threshold 0.7
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from aiohttp import ClientSession
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aiophyn import async_get_api
from aiophyn.errors import PhynError

_LOGGER = logging.getLogger()

load_dotenv()

USERNAME = os.getenv("PHYN_USERNAME")
PASSWORD = os.getenv("PHYN_PASSWORD")
BRAND = os.getenv("PHYN_BRAND", "phyn")
DEVICE_ID = os.getenv("PHYN_DEVICE_ID")

DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.70
DEFAULT_AMBIGUITY_GAP_THRESHOLD = 0.15
DEFAULT_MAX_REVIEW_EVENTS = 10
DEFAULT_DAY_RANGES = [1, 7, 30]


def _fmt_ts_millis(ts_millis) -> str:
    """Format millisecond timestamp into ISO datetime."""
    try:
        if ts_millis is None:
            return "N/A"
        return datetime.fromtimestamp(int(ts_millis) / 1000).isoformat()
    except (TypeError, ValueError, OSError):
        return "N/A"


def _extract_event_id(event: dict) -> str:
    """Return event identifier from known API fields."""
    return str(event.get("id") or event.get("event_id") or "unknown")


def _classify_event_quality(
    event: dict,
    low_confidence_threshold: float,
    ambiguity_gap_threshold: float,
) -> dict:
    """Classify ML quality signals for one water usage event."""
    result = {
        "event_id": _extract_event_id(event),
        "timestamp": event.get("open_edge_timestamp"),
        "total_flow": event.get("total_flow", 0.0),
        "top_fixture": "Unknown",
        "top_confidence": 0.0,
        "algorithm": "unknown",
        "confidence_gap": None,
        "is_low_confidence": False,
        "is_ambiguous": False,
        "has_user_feedback": False,
        "needs_review": False,
        "review_reasons": [],
    }

    fixtures_result = event.get("latest_suggested_fixtures_result", {}) or {}
    suggested = fixtures_result.get("suggested_fixtures", []) or []
    user_feedback = event.get("latest_user_feedback", {}) or {}

    result["has_user_feedback"] = bool(user_feedback)

    if not suggested:
        result["needs_review"] = True
        result["review_reasons"].append("no_suggestions")
        return result

    top = suggested[0]
    top_confidence = float(top.get("confidence_score") or 0)
    result["top_fixture"] = top.get("fixture_name", "Unknown")
    result["top_confidence"] = top_confidence
    result["algorithm"] = top.get("prediction_algorithm", "unknown")
    result["is_low_confidence"] = top_confidence < low_confidence_threshold

    if len(suggested) > 1:
        second_confidence = float(suggested[1].get("confidence_score") or 0)
        gap = top_confidence - second_confidence
        result["confidence_gap"] = gap
        result["is_ambiguous"] = gap < ambiguity_gap_threshold

    if result["is_low_confidence"]:
        result["review_reasons"].append("low_confidence")
    if result["is_ambiguous"]:
        result["review_reasons"].append("ambiguous_top2")
    if result["has_user_feedback"]:
        result["review_reasons"].append("has_user_feedback")

    result["needs_review"] = bool(result["review_reasons"])
    return result


def _parse_day_ranges(value: str) -> list[int]:
    """Parse comma-separated day ranges into sorted unique positive ints."""
    try:
        parts = [int(v.strip()) for v in value.split(",") if v.strip()]
    except ValueError as err:
        raise argparse.ArgumentTypeError("--days must be comma-separated integers") from err

    valid = sorted({p for p in parts if p > 0})
    if not valid:
        raise argparse.ArgumentTypeError("--days must include at least one positive integer")
    return valid


def parse_args() -> argparse.Namespace:
    """Parse CLI options for developer validation controls."""
    parser = argparse.ArgumentParser(description="Validate water usage event ML classifications")
    parser.add_argument(
        "--device-id",
        default=None,
        help="Optional single device id override (defaults to PHYN_DEVICE_ID env, then all discovered devices)",
    )
    parser.add_argument(
        "--days",
        type=_parse_day_ranges,
        default=DEFAULT_DAY_RANGES,
        help="Comma-separated day ranges to analyze (default: 1,7,30)",
    )
    parser.add_argument(
        "--low-confidence-threshold",
        type=float,
        default=DEFAULT_LOW_CONFIDENCE_THRESHOLD,
        help="Threshold below which top predictions are flagged (default: 0.70)",
    )
    parser.add_argument(
        "--ambiguity-gap-threshold",
        type=float,
        default=DEFAULT_AMBIGUITY_GAP_THRESHOLD,
        help="Top-2 confidence gap threshold for ambiguity flagging (default: 0.15)",
    )
    parser.add_argument(
        "--max-review-events",
        type=int,
        default=DEFAULT_MAX_REVIEW_EVENTS,
        help="Max review candidate events to print per range (default: 10)",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Test water usage events retrieval and fixture predictions."""
    logging.basicConfig(level=logging.INFO)

    if not USERNAME or not PASSWORD:
        print("ERROR: Set PHYN_USERNAME and PHYN_PASSWORD in .env file")
        return

    print("=" * 70)
    print("WATER USAGE EVENTS - FIXTURE PREDICTIONS TEST")
    print("=" * 70)

    async with ClientSession() as session:
        try:
            # Authenticate
            print(f"\nConnecting as {USERNAME}...")
            api = await async_get_api(
                USERNAME, PASSWORD, phyn_brand=BRAND, session=session
            )
            print("Authenticated successfully")

            # Discover devices
            homes = await api.home.get_homes(USERNAME)
            devices = []
            for home in homes:
                for device in home.get("devices", []):
                    did = device.get("device_id")
                    if did:
                        devices.append(did)

            selected_device = args.device_id or DEVICE_ID
            if selected_device:
                devices = [selected_device]

            print(f"Testing devices: {devices}")

            now = datetime.now()

            # Test multiple time ranges
            ranges = [(f"Last {day_count} day{'s' if day_count != 1 else ''}", timedelta(days=day_count)) for day_count in args.days]

            for device_id in devices:
                print(f"\n{'=' * 70}")
                print(f"DEVICE: {device_id}")
                print(f"{'=' * 70}")

                for range_name, delta in ranges:
                    from_dt = now - delta
                    to_dt = now

                    print(f"\n--- {range_name} ---")
                    print(f"  From: {from_dt.isoformat()}")
                    print(f"  To:   {to_dt.isoformat()}")

                    events = await api.device.get_water_usage_events(
                        device_id, from_dt, to_dt
                    )

                    print(f"  Events found: {len(events)}")

                    if not events:
                        continue

                    # Show sample event structure
                    if range_name == "Last 24 hours" and events:
                        print(f"\n  Sample event structure:")
                        print(f"  {json.dumps(events[0], indent=4)[:500]}")

                    # Analyze fixtures
                    fixture_usage = defaultdict(
                        lambda: {"total_gallons": 0.0, "event_count": 0, "confidences": []}
                    )
                    algorithm_counts = defaultdict(int)
                    quality_results = []

                    for event in events:
                        total_flow = event.get("total_flow", 0)
                        fixtures_result = event.get(
                            "latest_suggested_fixtures_result", {}
                        )
                        suggested = fixtures_result.get("suggested_fixtures", [])

                        if suggested:
                            top = suggested[0]
                            fixture_name = top.get("fixture_name", "Unknown")
                            confidence = top.get("confidence_score", 0)

                            fixture_usage[fixture_name]["total_gallons"] += total_flow
                            fixture_usage[fixture_name]["event_count"] += 1
                            fixture_usage[fixture_name]["confidences"].append(confidence)

                            algorithm = top.get("prediction_algorithm", "unknown")
                            algorithm_counts[algorithm] += 1

                        quality_results.append(
                            _classify_event_quality(
                                event,
                                args.low_confidence_threshold,
                                args.ambiguity_gap_threshold,
                            )
                        )

                    total_gallons = sum(
                        f["total_gallons"] for f in fixture_usage.values()
                    )

                    print(f"\n  Usage by fixture ({range_name}):")
                    print(
                        f"  {'Fixture':<25} {'Gallons':>10} {'Events':>8} {'Avg Conf':>10}"
                    )
                    print(f"  {'-' * 25} {'-' * 10} {'-' * 8} {'-' * 10}")

                    sorted_fixtures = sorted(
                        fixture_usage.items(),
                        key=lambda x: x[1]["total_gallons"],
                        reverse=True,
                    )

                    for fixture_name, data in sorted_fixtures:
                        avg_conf = (
                            sum(data["confidences"]) / len(data["confidences"])
                            if data["confidences"]
                            else 0
                        )
                        print(
                            f"  {fixture_name:<25} {data['total_gallons']:>9.2f}g "
                            f"{data['event_count']:>7} {avg_conf:>9.1%}"
                        )

                    print(f"\n  Total: {total_gallons:.2f} gallons")

                    # Classification quality summary
                    low_conf_events = [q for q in quality_results if q["is_low_confidence"]]
                    ambiguous_events = [q for q in quality_results if q["is_ambiguous"]]
                    feedback_events = [q for q in quality_results if q["has_user_feedback"]]
                    review_events = [q for q in quality_results if q["needs_review"]]

                    print(f"\n  Classification quality ({range_name}):")
                    print(
                        f"    Low confidence (<{args.low_confidence_threshold:.0%}): "
                        f"{len(low_conf_events)}/{len(events)}"
                    )
                    print(
                        f"    Ambiguous top-2 (gap < {args.ambiguity_gap_threshold:.2f}): "
                        f"{len(ambiguous_events)}/{len(events)}"
                    )
                    print(
                        f"    Events with user feedback: "
                        f"{len(feedback_events)}/{len(events)}"
                    )

                    if algorithm_counts:
                        print("    Top-prediction algorithms:")
                        for alg, cnt in sorted(
                            algorithm_counts.items(), key=lambda x: x[1], reverse=True
                        ):
                            pct = cnt / len(events) if events else 0
                            print(f"      - {alg}: {cnt} ({pct:.1%})")

                    if review_events:
                        print(
                            f"    Review candidates (up to {args.max_review_events} events):"
                        )
                        review_sorted = sorted(
                            review_events,
                            key=lambda x: (
                                x["top_confidence"],
                                x["timestamp"] or 0,
                            ),
                        )
                        for candidate in review_sorted[:args.max_review_events]:
                            reasons = ",".join(candidate["review_reasons"])
                            gap = candidate["confidence_gap"]
                            gap_txt = f", gap={gap:.2f}" if gap is not None else ""
                            print(
                                "      - "
                                f"{candidate['event_id']} @ {_fmt_ts_millis(candidate['timestamp'])}: "
                                f"{candidate['top_fixture']} conf={candidate['top_confidence']:.1%}"
                                f"{gap_txt}, reasons={reasons}, flow={candidate['total_flow']}g"
                            )

            print("\nTest complete.")

        except PhynError as err:
            _LOGGER.error("There was an error: %s", err)


asyncio.run(main(parse_args()))
