"""Probe an installed distribution, never the source checkout or a live device."""

import asyncio
from importlib import metadata
from pathlib import Path
import sys
import sysconfig
from unittest.mock import AsyncMock

import aiophyn
from aiophyn import HomeInventory, async_get_api
from aiophyn.api import API
from aiophyn.const import API_BASE
from aiophyn.device import Device
from aiophyn.mqtt import MQTTClient
from Crypto.Cipher import AES
import paho.mqtt.client
import socks


async def check_features():
    request = AsyncMock(return_value=[])
    inventory = HomeInventory(request)
    result = await inventory.get_fixture_types()
    request.assert_awaited_once_with("get", f"{API_BASE}/home-inventory/types")
    assert result is request.return_value

    request.reset_mock()
    await inventory.get_device_inventory("offline-device")
    request.assert_awaited_once_with(
        "get", f"{API_BASE}/home-inventory/device/offline-device"
    )

    request.reset_mock()
    device = Device(request)
    await device.get_water_usage_events("offline-device", from_ts=1000, to_ts=2000)
    request.assert_awaited_once_with(
        "get",
        f"{API_BASE}/water-usage-events",
        params={"device_id": "offline-device", "from_ts": 1000, "to_ts": 2000},
    )

    request.reset_mock()
    await device.get_autoshuftoff_status("offline-device")
    request.assert_awaited_once_with(
        "get", f"{API_BASE}/devices/offline-device/auto_shutoff"
    )
    assert not hasattr(device, "get_autoshutoff_status")


def main():
    expected_version = sys.argv[1]
    distribution = metadata.distribution("aiophyn")
    assert distribution.version == expected_version == aiophyn.__version__
    installed_file = Path(aiophyn.__file__).resolve()
    assert (
        installed_file
        == Path(distribution.locate_file("aiophyn/__init__.py")).resolve()
    ), installed_file
    assert installed_file.is_relative_to(
        Path(sysconfig.get_path("purelib")).resolve()
    ), installed_file
    assert callable(async_get_api)
    assert API and MQTTClient and paho.mqtt.client.Client and socks.socksocket
    assert AES.block_size == 16
    asyncio.run(check_features())
    print(f"Verified aiophyn {distribution.version} from {installed_file}")


if __name__ == "__main__":
    main()
