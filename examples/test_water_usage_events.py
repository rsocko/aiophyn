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
"""
import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta

from aiohttp import ClientSession
from dotenv import load_dotenv

from aiophyn import async_get_api
from aiophyn.errors import PhynError

_LOGGER = logging.getLogger()

load_dotenv()

USERNAME = os.getenv("PHYN_USERNAME")
PASSWORD = os.getenv("PHYN_PASSWORD")
BRAND = os.getenv("PHYN_BRAND", "phyn")
DEVICE_ID = os.getenv("PHYN_DEVICE_ID")


async def main() -> None:
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

            if DEVICE_ID:
                devices = [DEVICE_ID]

            print(f"Testing devices: {devices}")

            now = datetime.now()

            # Test multiple time ranges
            ranges = [
                ("Last 24 hours", timedelta(days=1)),
                ("Last 7 days", timedelta(days=7)),
                ("Last 30 days", timedelta(days=30)),
            ]

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

            print("\nTest complete.")

        except PhynError as err:
            _LOGGER.error("There was an error: %s", err)


asyncio.run(main())
