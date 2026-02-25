"""Test home inventory / fixture type endpoints.

This script validates the HomeInventory methods added to the aiophyn library:
  - get_fixture_types() - master list of all fixture types
  - get_device_inventory() - user's configured fixtures per device

Derived from: ideation/experiments/home-automation/phyn-api-exploration/scripts/
  - fixture_deep_dive.py
  - fixture_exploration.py

Usage:
    1. Copy .env.example to .env and fill in your credentials
    2. Run: python test_home_inventory.py
"""
import asyncio
import json
import logging
import os
import sys
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


async def main() -> None:
    """Test home inventory endpoints."""
    logging.basicConfig(level=logging.INFO)

    if not USERNAME or not PASSWORD:
        print("ERROR: Set PHYN_USERNAME and PHYN_PASSWORD in .env file")
        return

    print("=" * 70)
    print("HOME INVENTORY / FIXTURE TYPES TEST")
    print("=" * 70)

    async with ClientSession() as session:
        try:
            # Authenticate
            print(f"\nConnecting as {USERNAME}...")
            api = await async_get_api(
                USERNAME, PASSWORD, phyn_brand=BRAND, session=session
            )
            print("Authenticated successfully")

            # ---- Test 1: Get all fixture types (master list) ----
            print(f"\n{'=' * 70}")
            print("TEST 1: Get fixture types (master catalog)")
            print(f"{'=' * 70}")

            fixture_types = await api.home_inventory.get_fixture_types()
            print(f"\nFound {len(fixture_types)} fixture types:")

            for ft in fixture_types:
                type_id = ft.get("home_inventory_type_id", "N/A")
                name = ft.get("name", "Unknown")
                category = ft.get("home_inventory_type", "N/A")
                print(f"  ID {type_id:>3}: {name:<25} ({category})")

            # ---- Test 2: Get device inventory ----
            print(f"\n{'=' * 70}")
            print("TEST 2: Get device inventory (user-configured fixtures)")
            print(f"{'=' * 70}")

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

            device_inventories = {}

            for device_id in devices:
                print(f"\nDevice: {device_id}")

                inventory = await api.home_inventory.get_device_inventory(device_id)
                device_inventories[device_id] = inventory
                fixture_list = inventory.get("list", [])

                configured = [f for f in fixture_list if f.get("count", 0) > 0]
                unconfigured = [f for f in fixture_list if f.get("count", 0) == 0]

                print(f"  Total fixture entries: {len(fixture_list)}")
                print(f"  Configured (count > 0): {len(configured)}")

                if configured:
                    print("\n  Configured fixtures:")
                    for f in sorted(configured, key=lambda x: x.get("name", "")):
                        print(
                            f"    - {f.get('name')}: {f.get('count')} "
                            f"(type_id={f.get('home_inventory_type_id')})"
                        )

                if unconfigured:
                    print(f"\n  Unconfigured ({len(unconfigured)} types with count=0):")
                    for f in sorted(unconfigured, key=lambda x: x.get("name", "")):
                        print(
                            f"    - {f.get('name')} "
                            f"(type_id={f.get('home_inventory_type_id')})"
                        )

            # ---- Test 3: Cross-reference fixture types with inventory ----
            print(f"\n{'=' * 70}")
            print("TEST 3: Cross-reference fixture types with device inventory")
            print(f"{'=' * 70}")

            if devices and fixture_types:
                for device_id in devices:
                    inventory = device_inventories.get(device_id, {})
                    fixture_list = inventory.get("list", [])

                    # Build lookup
                    inventory_by_id = {
                        f["home_inventory_type_id"]: f for f in fixture_list
                    }

                    print(f"\nDevice: {device_id}")
                    print(
                        f"  {'Type ID':>7} {'Name':<25} {'Category':<15} {'Count':>6}"
                    )
                    print(f"  {'-' * 7} {'-' * 25} {'-' * 15} {'-' * 6}")

                    for ft in fixture_types:
                        type_id = ft.get("home_inventory_type_id")
                        name = ft.get("name", "Unknown")
                        category = ft.get("home_inventory_type", "N/A")
                        inv = inventory_by_id.get(type_id)
                        count = inv.get("count", 0) if inv else "-"
                        marker = " *" if inv and inv.get("count", 0) > 0 else ""
                        print(
                            f"  {type_id:>7} {name:<25} {category:<15} {str(count):>6}{marker}"
                        )

            print("\nTest complete.")

        except PhynError as err:
            _LOGGER.error("There was an error: %s", err)


asyncio.run(main())
