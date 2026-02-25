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
        including their IDs, names, categories, and icon image URLs.

        :return: List of fixture type definitions.
            Each item contains home_inventory_type_id (int), name (str),
            image (str, S3 URL to icon), and home_inventory_type (str, "F").
        :rtype: list[dict]

        Example response::

            [
                {"home_inventory_type_id": 1, "name": "Hot Tub", "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/hot-tub-black.png", "home_inventory_type": "F"},
                {"home_inventory_type_id": 5, "name": "Shower Only", "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/shower-black.png", "home_inventory_type": "F"},
                {"home_inventory_type_id": 8, "name": "Toilet", "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/toilet-black.png", "home_inventory_type": "F"},
                {"home_inventory_type_id": 16, "name": "Dishwasher", "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/dishwasher-black.png", "home_inventory_type": "F"},
                {"home_inventory_type_id": 30, "name": "Washing Machine", "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/washing-machine-black.png", "home_inventory_type": "F"},
                {"home_inventory_type_id": 34, "name": "Other", "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/other-black.png", "home_inventory_type": "F"},
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
            Each entry has home_inventory_type_id (int), name (str),
            count (int), image (str, S3 URL), home_inventory_type (str, "F"),
            and optionally sub_fixtures (list[dict]) with named sub-fixture
            entries containing name (str), active (bool), and id (int).
        :rtype: dict

        Example response::

            {
                "list": [
                    {"home_inventory_type_id": 8, "name": "Toilet", "count": 5, "image": "https://s3.amazonaws.com/.../toilet-black.png", "home_inventory_type": "F"},
                    {"home_inventory_type_id": 5, "name": "Shower Only", "count": 2, "image": "https://s3.amazonaws.com/.../shower-black.png", "home_inventory_type": "F", "sub_fixtures": [{"name": "Master Bathroom", "active": true, "id": 1647984949429}]},
                    {"home_inventory_type_id": 7, "name": "Sink", "count": 9, "image": "https://s3.amazonaws.com/.../sink-black.png", "home_inventory_type": "F"},
                    {"home_inventory_type_id": 16, "name": "Dishwasher", "count": 1, "image": "https://s3.amazonaws.com/.../dishwasher-black.png", "home_inventory_type": "F"},
                    {"home_inventory_type_id": 2, "name": "Irrigation System", "count": 0, "image": "https://s3.amazonaws.com/.../irrigation-black.png", "home_inventory_type": "F"},
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
