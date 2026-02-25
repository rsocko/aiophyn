"""Comprehensive test of all aiophyn API endpoints.

This script exercises the full aiophyn API surface in a single run:
  - Home/device discovery
  - Device state
  - Water consumption
  - Water usage events with fixture predictions
  - Home inventory (fixture types & device inventory)
  - Device preferences
  - Firmware info

Derived from: ideation/experiments/home-automation/phyn-api-exploration/scripts/
  - quick_test.py
  - endpoint_discovery.py
  - device_usage_test.py

Usage:
    1. Copy .env.example to .env and fill in your credentials
    2. Run: python test_comprehensive.py
"""
import asyncio
import json
import logging
import os
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


def print_section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


async def test_endpoint(name: str, coro):
    """Run a test and report pass/fail."""
    try:
        result = await coro
        print(f"  PASS: {name}")
        return result
    except Exception as e:
        print(f"  FAIL: {name} - {e}")
        return None


async def main() -> None:
    """Run comprehensive API tests."""
    logging.basicConfig(level=logging.INFO)

    if not USERNAME or not PASSWORD:
        print("ERROR: Set PHYN_USERNAME and PHYN_PASSWORD in .env file")
        return

    print("=" * 70)
    print("COMPREHENSIVE AIOPHYN API TEST")
    print("=" * 70)

    results = {"passed": 0, "failed": 0, "tests": []}

    async with ClientSession() as session:
        try:
            # ---- Authentication ----
            print_section("AUTHENTICATION")
            api = await async_get_api(
                USERNAME, PASSWORD, phyn_brand=BRAND, session=session
            )
            print(f"  PASS: Authentication")
            results["passed"] += 1
            results["tests"].append({"name": "Authentication", "status": "PASS"})

            # ---- Home Discovery ----
            print_section("HOME DISCOVERY")
            homes = await test_endpoint(
                "get_homes", api.home.get_homes(USERNAME)
            )

            if homes:
                results["passed"] += 1
                results["tests"].append({"name": "get_homes", "status": "PASS"})
                print(f"    Found {len(homes)} home(s)")
                for home in homes:
                    addr = home.get("address", {}).get("address1", "Unknown")
                    print(f"    Home: {addr}")
                    for device in home.get("devices", []):
                        did = device.get("device_id", "N/A")
                        pc = device.get("product_code", "N/A")
                        print(f"      Device: {did} ({pc})")
            else:
                results["failed"] += 1
                results["tests"].append({"name": "get_homes", "status": "FAIL"})

            # Collect device IDs
            devices = []
            if homes:
                for home in homes:
                    for device in home.get("devices", []):
                        did = device.get("device_id")
                        if did:
                            devices.append(did)

            if DEVICE_ID:
                devices = [DEVICE_ID]

            if not devices:
                print("\n  No devices found. Exiting.")
                return

            device_id = devices[0]
            print(f"\n  Using device: {device_id}")

            # ---- Device State ----
            print_section("DEVICE STATE")
            state = await test_endpoint(
                "get_state", api.device.get_state(device_id)
            )
            if state:
                results["passed"] += 1
                results["tests"].append({"name": "get_state", "status": "PASS"})
                temp = state.get("temperature", {}).get("mean", "N/A")
                pressure = state.get("pressure", {}).get("mean", "N/A")
                valve = state.get("sov_status", {}).get("v", "N/A")
                print(f"    Temperature: {temp}")
                print(f"    Pressure: {pressure}")
                print(f"    Valve: {valve}")
            else:
                results["failed"] += 1
                results["tests"].append({"name": "get_state", "status": "FAIL"})

            # ---- Consumption ----
            print_section("WATER CONSUMPTION")
            today = datetime.now().strftime("%Y/%m/%d")
            consumption = await test_endpoint(
                "get_consumption",
                api.device.get_consumption(
                    device_id, today, precision=6, details=True, event_count=True
                ),
            )
            if consumption:
                results["passed"] += 1
                results["tests"].append({"name": "get_consumption", "status": "PASS"})
                gallons = consumption.get("water_consumption", 0)
                events = consumption.get("water_usage_event_count", "N/A")
                print(f"    Today's consumption: {gallons:.2f} gallons")
                print(f"    Event count: {events}")
            else:
                results["failed"] += 1
                results["tests"].append({"name": "get_consumption", "status": "FAIL"})

            # ---- Water Usage Events ----
            print_section("WATER USAGE EVENTS")
            now = datetime.now()
            events_data = await test_endpoint(
                "get_water_usage_events",
                api.device.get_water_usage_events(
                    device_id, now - timedelta(days=7), now
                ),
            )
            if events_data is not None:
                results["passed"] += 1
                results["tests"].append(
                    {"name": "get_water_usage_events", "status": "PASS"}
                )
                print(f"    Events (last 7 days): {len(events_data)}")
                if events_data:
                    # Check for fixture data presence
                    sample = events_data[0]
                    has_fixtures = "latest_suggested_fixtures_result" in sample
                    has_event_id = "event_id" in sample
                    has_flow = "total_flow" in sample
                    print(f"    Has fixture predictions: {has_fixtures}")
                    print(f"    Has event_id: {has_event_id}")
                    print(f"    Has total_flow: {has_flow}")
            else:
                results["failed"] += 1
                results["tests"].append(
                    {"name": "get_water_usage_events", "status": "FAIL"}
                )

            # ---- Fixture Types ----
            print_section("FIXTURE TYPES (HOME INVENTORY)")
            fixture_types = await test_endpoint(
                "get_fixture_types", api.home_inventory.get_fixture_types()
            )
            if fixture_types:
                results["passed"] += 1
                results["tests"].append(
                    {"name": "get_fixture_types", "status": "PASS"}
                )
                print(f"    Fixture types: {len(fixture_types)}")
                for ft in fixture_types[:5]:
                    print(
                        f"      ID {ft.get('home_inventory_type_id')}: "
                        f"{ft.get('name')} ({ft.get('home_inventory_type')})"
                    )
                if len(fixture_types) > 5:
                    print(f"      ... and {len(fixture_types) - 5} more")
            else:
                results["failed"] += 1
                results["tests"].append(
                    {"name": "get_fixture_types", "status": "FAIL"}
                )

            # ---- Device Inventory ----
            print_section("DEVICE INVENTORY")
            inventory = await test_endpoint(
                "get_device_inventory",
                api.home_inventory.get_device_inventory(device_id),
            )
            if inventory:
                results["passed"] += 1
                results["tests"].append(
                    {"name": "get_device_inventory", "status": "PASS"}
                )
                fixture_list = inventory.get("list", [])
                configured = [f for f in fixture_list if f.get("count", 0) > 0]
                print(f"    Total fixture entries: {len(fixture_list)}")
                print(f"    Configured (count > 0): {len(configured)}")
                for f in configured:
                    print(f"      {f.get('name')}: {f.get('count')}")
            else:
                results["failed"] += 1
                results["tests"].append(
                    {"name": "get_device_inventory", "status": "FAIL"}
                )

            # ---- Device Preferences ----
            print_section("DEVICE PREFERENCES")
            prefs = await test_endpoint(
                "get_device_preferences",
                api.device.get_device_preferences(device_id),
            )
            if prefs:
                results["passed"] += 1
                results["tests"].append(
                    {"name": "get_device_preferences", "status": "PASS"}
                )
                if isinstance(prefs, list):
                    print(f"    Preferences count: {len(prefs)}")
                    for p in prefs[:5]:
                        print(
                            f"      {p.get('name', 'N/A')}: {p.get('value', 'N/A')}"
                        )
            else:
                results["failed"] += 1
                results["tests"].append(
                    {"name": "get_device_preferences", "status": "FAIL"}
                )

            # ---- Firmware Info ----
            print_section("FIRMWARE INFO")
            fw = await test_endpoint(
                "get_latest_firmware_info",
                api.device.get_latest_firmware_info(device_id),
            )
            if fw:
                results["passed"] += 1
                results["tests"].append(
                    {"name": "get_latest_firmware_info", "status": "PASS"}
                )
                print(f"    Firmware version: {fw.get('fw_version', 'N/A')}")
                print(f"    Product code: {fw.get('product_code', 'N/A')}")
            else:
                results["failed"] += 1
                results["tests"].append(
                    {"name": "get_latest_firmware_info", "status": "FAIL"}
                )

            # ---- Away Mode ----
            print_section("AWAY MODE")
            away = await test_endpoint(
                "get_away_mode", api.device.get_away_mode(device_id)
            )
            if away is not None:
                results["passed"] += 1
                results["tests"].append({"name": "get_away_mode", "status": "PASS"})
                print(f"    Away mode data: {json.dumps(away)[:200]}")
            else:
                results["failed"] += 1
                results["tests"].append({"name": "get_away_mode", "status": "FAIL"})

            # ---- Summary ----
            print_section("TEST SUMMARY")
            total = results["passed"] + results["failed"]
            print(f"  Total:  {total}")
            print(f"  Passed: {results['passed']}")
            print(f"  Failed: {results['failed']}")
            print()
            for t in results["tests"]:
                marker = "PASS" if t["status"] == "PASS" else "FAIL"
                print(f"  [{marker}] {t['name']}")

        except PhynError as err:
            _LOGGER.error("There was an error: %s", err)


asyncio.run(main())
