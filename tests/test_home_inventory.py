"""Tests for the HomeInventory class.

Tests the new home inventory endpoints:
  - get_fixture_types() - master list
  - get_device_inventory() - per-device fixtures
  - update_device_inventory() - update fixture counts

Sample-shape assertions below describe local fixtures, not server proof.
See test_transport_contracts.py for independent offline wire contracts.
"""
import pytest
from unittest.mock import AsyncMock

from aiophyn.home_inventory import HomeInventory
from aiophyn.const import API_BASE

try:
    from tests.conftest import SAMPLE_FIXTURE_TYPES, SAMPLE_DEVICE_INVENTORY
except ModuleNotFoundError:
    from conftest import SAMPLE_FIXTURE_TYPES, SAMPLE_DEVICE_INVENTORY


class TestGetFixtureTypes:
    """Tests for get_fixture_types."""

    @pytest.mark.asyncio
    async def test_basic_call(self, home_inventory, mock_request):
        """Test that the correct URL is called."""
        mock_request.return_value = SAMPLE_FIXTURE_TYPES
        result = await home_inventory.get_fixture_types()

        mock_request.assert_called_once_with(
            "get", f"{API_BASE}/home-inventory/types"
        )
        assert result == SAMPLE_FIXTURE_TYPES

    @pytest.mark.asyncio
    async def test_returns_list(self, home_inventory, mock_request):
        """Verify response is a list of fixture type dicts."""
        mock_request.return_value = SAMPLE_FIXTURE_TYPES
        result = await home_inventory.get_fixture_types()

        assert isinstance(result, list)
        assert len(result) == 16

    @pytest.mark.asyncio
    async def test_fixture_type_structure(self, home_inventory, mock_request):
        """Verify each fixture type has required fields matching real API."""
        mock_request.return_value = SAMPLE_FIXTURE_TYPES
        result = await home_inventory.get_fixture_types()

        for ft in result:
            assert "home_inventory_type_id" in ft
            assert "name" in ft
            assert "home_inventory_type" in ft
            assert "image" in ft
            assert isinstance(ft["home_inventory_type_id"], int)
            assert isinstance(ft["name"], str)
            assert isinstance(ft["image"], str)
            assert ft["image"].startswith("https://s3.amazonaws.com/com.phyn.icons/")

    @pytest.mark.asyncio
    async def test_known_fixture_types(self, home_inventory, mock_request):
        """Verify well-known fixture types are present."""
        mock_request.return_value = SAMPLE_FIXTURE_TYPES
        result = await home_inventory.get_fixture_types()

        names = {ft["name"] for ft in result}
        assert "Toilet" in names
        assert "Shower Only" in names
        assert "Sink" in names
        assert "Dishwasher" in names
        assert "Washing Machine" in names
        assert "Other" in names

    @pytest.mark.asyncio
    async def test_fixture_categories(self, home_inventory, mock_request):
        """Verify fixture categories use real API values."""
        mock_request.return_value = SAMPLE_FIXTURE_TYPES
        result = await home_inventory.get_fixture_types()

        # Real API uses "F" for all fixture types (not descriptive categories)
        for ft in result:
            assert ft["home_inventory_type"] == "F"

    @pytest.mark.asyncio
    async def test_empty_response(self, home_inventory, mock_request):
        """Verify empty list response is handled."""
        mock_request.return_value = []
        result = await home_inventory.get_fixture_types()
        assert result == []


class TestGetDeviceInventory:
    """Tests for get_device_inventory."""

    @pytest.mark.asyncio
    async def test_basic_call(self, home_inventory, mock_request):
        """Test correct URL construction with device_id."""
        mock_request.return_value = SAMPLE_DEVICE_INVENTORY
        result = await home_inventory.get_device_inventory("DEVICE123")

        mock_request.assert_called_once_with(
            "get", f"{API_BASE}/home-inventory/device/DEVICE123"
        )

    @pytest.mark.asyncio
    async def test_response_has_list_key(self, home_inventory, mock_request):
        """Verify response contains a 'list' key."""
        mock_request.return_value = SAMPLE_DEVICE_INVENTORY
        result = await home_inventory.get_device_inventory("DEVICE123")

        assert "list" in result
        assert isinstance(result["list"], list)

    @pytest.mark.asyncio
    async def test_configured_fixtures(self, home_inventory, mock_request):
        """Verify fixtures with count > 0 are present."""
        mock_request.return_value = SAMPLE_DEVICE_INVENTORY
        result = await home_inventory.get_device_inventory("DEVICE123")

        configured = [f for f in result["list"] if f.get("count", 0) > 0]
        assert len(configured) == 9

        names = {f["name"] for f in configured}
        assert "Toilet" in names
        assert "Shower Only" in names
        assert "Sink" in names
        assert "Dishwasher" in names
        assert "Washing Machine" in names
        assert "Shower Tub Combo" in names
        assert "Tub" in names
        assert "Hot Water Heater" in names
        assert "Refrigerator" in names

    @pytest.mark.asyncio
    async def test_unconfigured_fixtures(self, home_inventory, mock_request):
        """Verify fixtures with count = 0 are present too."""
        mock_request.return_value = SAMPLE_DEVICE_INVENTORY
        result = await home_inventory.get_device_inventory("DEVICE123")

        unconfigured = [f for f in result["list"] if f.get("count", 0) == 0]
        assert len(unconfigured) == 3

    @pytest.mark.asyncio
    async def test_fixture_entry_structure(self, home_inventory, mock_request):
        """Verify each inventory entry has required fields from real API."""
        mock_request.return_value = SAMPLE_DEVICE_INVENTORY
        result = await home_inventory.get_device_inventory("DEVICE123")

        for f in result["list"]:
            assert "home_inventory_type_id" in f
            assert "name" in f
            assert "count" in f
            assert "image" in f
            assert "home_inventory_type" in f
            assert isinstance(f["count"], int)
            assert f["home_inventory_type"] == "F"
            assert f["image"].startswith("https://")

    @pytest.mark.asyncio
    async def test_unknown_response_fields_preserved(self, home_inventory, mock_request):
        """Unknown server metadata passes through without inferred semantics."""
        payload = {
            "list": [{
                "home_inventory_type_id": 5,
                "name": "Shower Only",
                "count": 2,
                "unknown_metadata": {"opaque": [1, None]},
            }],
            "unknown_envelope": True,
        }
        mock_request.return_value = payload
        result = await home_inventory.get_device_inventory("DEVICE123")
        assert result is payload
        assert result["list"][0]["unknown_metadata"] == {"opaque": [1, None]}
        assert result["list"][0]["count"] == 2

    @pytest.mark.asyncio
    async def test_different_device_ids(self, home_inventory, mock_request):
        """Verify URL changes for different device IDs."""
        mock_request.return_value = {"list": []}

        await home_inventory.get_device_inventory("AAA111")
        mock_request.assert_called_with(
            "get", f"{API_BASE}/home-inventory/device/AAA111"
        )

        await home_inventory.get_device_inventory("BBB222")
        mock_request.assert_called_with(
            "get", f"{API_BASE}/home-inventory/device/BBB222"
        )


class TestUpdateDeviceInventory:
    """Tests for update_device_inventory."""

    @pytest.mark.asyncio
    async def test_basic_call(self, home_inventory, mock_request):
        """Test correct URL and payload construction."""
        mock_request.return_value = {}
        await home_inventory.update_device_inventory("DEVICE123", 8, 4)

        mock_request.assert_called_once_with(
            "post",
            f"{API_BASE}/home-inventory/device/DEVICE123",
            json={"list": [{"home_inventory_type_id": 8, "count": 4}]},
        )

    @pytest.mark.asyncio
    async def test_uses_post_method(self, home_inventory, mock_request):
        """Preserve the POST method from the historical endpoint experiment."""
        mock_request.return_value = {}
        await home_inventory.update_device_inventory("DEVICE123", 8, 3)

        args = mock_request.call_args[0]
        assert args[0] == "post"

    @pytest.mark.asyncio
    async def test_payload_format(self, home_inventory, mock_request):
        """Verify payload wraps type_id and count in a list."""
        mock_request.return_value = {}
        await home_inventory.update_device_inventory("DEVICE123", 5, 2)

        call_kwargs = mock_request.call_args.kwargs
        json_data = call_kwargs["json"]

        assert json_data == {"list": [{"home_inventory_type_id": 5, "count": 2}]}

    @pytest.mark.asyncio
    async def test_zero_count(self, home_inventory, mock_request):
        """Verify setting count to 0 works (removing a fixture)."""
        mock_request.return_value = {}
        await home_inventory.update_device_inventory("DEVICE123", 1, 0)

        call_kwargs = mock_request.call_args.kwargs
        assert call_kwargs["json"]["list"][0]["count"] == 0

    @pytest.mark.asyncio
    async def test_various_fixture_ids(self, home_inventory, mock_request):
        """Verify different fixture type IDs are passed correctly."""
        mock_request.return_value = {}

        test_cases = [
            (1, 1, "Hot Tub"),
            (8, 3, "Toilet"),
            (16, 1, "Dishwasher"),
            (30, 1, "Washing Machine"),
            (34, 0, "Other"),
        ]

        for type_id, count, _name in test_cases:
            await home_inventory.update_device_inventory("DEVICE123", type_id, count)
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["json"]["list"][0]["home_inventory_type_id"] == type_id
            assert call_kwargs["json"]["list"][0]["count"] == count
