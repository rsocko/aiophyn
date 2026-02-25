"""Define /home-inventory endpoints."""
from typing import Awaitable, Callable

from .const import API_BASE


class HomeInventory:
    """Define an object to handle the home-inventory endpoints."""

    def __init__(self, request: Callable[..., Awaitable]) -> None:
        """Initialize."""
        self._request: Callable[..., Awaitable] = request

    async def get_fixture_types(self) -> list[dict]:
        """Get all available fixture types (master list).

        Returns the master catalog of fixture types that Phyn recognizes,
        including their IDs, names, and categories.

        :return: List of fixture type definitions.
            Each item contains home_inventory_type_id, name, and home_inventory_type.
        :rtype: list[dict]

        Example response::

            [
                {"home_inventory_type_id": 1, "name": "Hot Tub", "home_inventory_type": "appliance"},
                {"home_inventory_type_id": 5, "name": "Shower Only", "home_inventory_type": "fixture"},
                {"home_inventory_type_id": 8, "name": "Toilet", "home_inventory_type": "fixture"},
                {"home_inventory_type_id": 16, "name": "Dishwasher", "home_inventory_type": "appliance"},
                {"home_inventory_type_id": 30, "name": "Washing Machine", "home_inventory_type": "appliance"},
                {"home_inventory_type_id": 34, "name": "Other", "home_inventory_type": "other"},
            ]
        """
        return await self._request("get", f"{API_BASE}/home-inventory/types")

    async def get_device_inventory(self, device_id: str) -> dict:
        """Get user's configured fixtures for a specific device.

        Returns the fixture types the user has configured in the Phyn app,
        including counts (e.g., "3 toilets, 2 showers"). Only fixtures
        with count > 0 are actively configured by the user.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :return: Dict containing a ``list`` key with fixture entries.
            Each entry has home_inventory_type_id, name, and count.
        :rtype: dict

        Example response::

            {
                "list": [
                    {"home_inventory_type_id": 8, "name": "Toilet", "count": 3},
                    {"home_inventory_type_id": 5, "name": "Shower Only", "count": 2},
                    {"home_inventory_type_id": 7, "name": "Sink", "count": 5},
                    {"home_inventory_type_id": 16, "name": "Dishwasher", "count": 1},
                    {"home_inventory_type_id": 2, "name": "Irrigation System", "count": 0},
                ]
            }
        """
        return await self._request(
            "get", f"{API_BASE}/home-inventory/device/{device_id}"
        )

    async def update_device_inventory(
        self,
        device_id: str,
        fixture_type_id: int,
        count: int,
    ) -> dict:
        """Update fixture count in user's home inventory.

        Sets the number of a specific fixture type the user has configured
        for their device/home.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :param fixture_type_id: The home_inventory_type_id of the fixture to update
        :type fixture_type_id: int
        :param count: New count for this fixture type
        :type count: int
        :return: API response
        :rtype: dict

        .. note::
            This updates a single fixture type count at a time. The payload
            format is a simple object with home_inventory_type_id and count.
        """
        data = {
            "home_inventory_type_id": fixture_type_id,
            "count": count,
        }
        return await self._request(
            "put", f"{API_BASE}/home-inventory/device/{device_id}", json=data
        )
