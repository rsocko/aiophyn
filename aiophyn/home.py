"""Define /home endpoints."""
from typing import Awaitable, Callable

from .const import API_BASE


class Home:
    """Define an object to handle the endpoints."""

    def __init__(self, request: Callable[..., Awaitable]) -> None:
        """Initialize."""
        self._request: Callable[..., Awaitable] = request

    async def get_homes(
        self,
        user_id: str,
    ) -> list:
        """Return info for all homes.

        :param user_id: Phyn username (email)
        :type user_id: ``str``
        :return: List of home dicts. Each contains id (str),
            address (dict with address1), device_ids (list[str]),
            and devices (list[dict] with device_id, product_code, name).
        :rtype: ``list``
        """
        params = {"user_id": user_id}

        return await self._request("get", f"{API_BASE}/homes", params=params)
