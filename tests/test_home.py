"""Tests for the Home class."""
import pytest
from unittest.mock import AsyncMock

from aiophyn.home import Home
from aiophyn.const import API_BASE

from conftest import SAMPLE_HOMES


class TestGetHomes:
    """Tests for get_homes."""

    @pytest.mark.asyncio
    async def test_basic_call(self, home, mock_request):
        """Test that correct URL and params are used."""
        mock_request.return_value = SAMPLE_HOMES
        result = await home.get_homes("user@example.com")

        mock_request.assert_called_once_with(
            "get",
            f"{API_BASE}/homes",
            params={"user_id": "user@example.com"},
        )

    @pytest.mark.asyncio
    async def test_returns_home_list(self, home, mock_request):
        """Verify response is a list of home dicts."""
        mock_request.return_value = SAMPLE_HOMES
        result = await home.get_homes("user@example.com")

        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_home_contains_devices(self, home, mock_request):
        """Verify home entries contain device information."""
        mock_request.return_value = SAMPLE_HOMES
        result = await home.get_homes("user@example.com")

        home_info = result[0]
        assert "devices" in home_info
        assert len(home_info["devices"]) == 1
        assert home_info["devices"][0]["device_id"] == "28F53741CBBA"

    @pytest.mark.asyncio
    async def test_home_contains_address(self, home, mock_request):
        """Verify home entries contain address information."""
        mock_request.return_value = SAMPLE_HOMES
        result = await home.get_homes("user@example.com")

        home_info = result[0]
        assert "address" in home_info
        assert home_info["address"]["address1"] == "123 Main St"
