"""Tests for the Device class.

Tests the existing device methods and the new get_water_usage_events method.
Validates that:
  - Correct API URLs are constructed
  - Datetime-to-millisecond conversion works correctly
  - Parameters are passed properly
  - Response data is returned as-is
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, call

from aiophyn.device import Device
from aiophyn.const import API_BASE

from conftest import (
    SAMPLE_DEVICE_STATE,
    SAMPLE_CONSUMPTION,
    SAMPLE_WATER_USAGE_EVENTS,
    SAMPLE_FIRMWARE_INFO,
)


class TestDeviceState:
    """Tests for get_state."""

    @pytest.mark.asyncio
    async def test_get_state(self, device, mock_request):
        mock_request.return_value = SAMPLE_DEVICE_STATE
        result = await device.get_state("DEVICE123")

        mock_request.assert_called_once_with(
            "get", f"{API_BASE}/devices/DEVICE123/state"
        )
        assert result == SAMPLE_DEVICE_STATE
        assert result["temperature"]["mean"] == 72.5
        assert result["pressure"]["mean"] == 55.3
        assert result["sov_status"]["v"] == 1


class TestConsumption:
    """Tests for get_consumption."""

    @pytest.mark.asyncio
    async def test_get_consumption_basic(self, device, mock_request):
        mock_request.return_value = SAMPLE_CONSUMPTION
        result = await device.get_consumption("DEVICE123", "2026/02/24")

        mock_request.assert_called_once_with(
            "get",
            f"{API_BASE}/devices/DEVICE123/consumption/details",
            params={
                "device_id": "DEVICE123",
                "duration": "2026/02/24",
                "precision": 6,
            },
        )
        assert result["water_consumption"] == 25.5

    @pytest.mark.asyncio
    async def test_get_consumption_with_details(self, device, mock_request):
        mock_request.return_value = SAMPLE_CONSUMPTION
        result = await device.get_consumption(
            "DEVICE123", "2026/02/24", details=True, event_count=True, comparison=True
        )

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["details"] == "Y"
        assert params["event_count"] == "Y"
        assert params["comparison"] == "Y"

    @pytest.mark.asyncio
    async def test_get_consumption_monthly(self, device, mock_request):
        mock_request.return_value = SAMPLE_CONSUMPTION
        await device.get_consumption("DEVICE123", "2026/02")

        call_kwargs = mock_request.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["duration"] == "2026/02"


class TestWaterUsageEvents:
    """Tests for get_water_usage_events (new method)."""

    @pytest.mark.asyncio
    async def test_basic_call(self, device, mock_request):
        """Test that basic call constructs correct URL and params."""
        mock_request.return_value = SAMPLE_WATER_USAGE_EVENTS

        from_dt = datetime(2026, 2, 20, 0, 0, 0)
        to_dt = datetime(2026, 2, 24, 23, 59, 59)

        result = await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "get"
        assert args[1] == f"{API_BASE}/water-usage-events"

        params = kwargs.get("params", {})
        assert params["device_id"] == "DEVICE123"

        # Verify millisecond conversion
        expected_from_ts = str(int(from_dt.timestamp() * 1000))
        expected_to_ts = str(int(to_dt.timestamp() * 1000))
        assert params["from_ts"] == expected_from_ts
        assert params["to_ts"] == expected_to_ts

    @pytest.mark.asyncio
    async def test_millisecond_timestamps(self, device, mock_request):
        """Verify that timestamps are converted to 13-digit milliseconds."""
        mock_request.return_value = []

        # Known timestamp: 2026-01-01 00:00:00 UTC
        from_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        to_dt = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        params = mock_request.call_args.kwargs["params"]
        from_ts = int(params["from_ts"])
        to_ts = int(params["to_ts"])

        # Must be 13 digits (milliseconds)
        assert len(params["from_ts"]) == 13
        assert len(params["to_ts"]) == 13

        # Verify conversion back
        assert abs(from_ts / 1000 - from_dt.timestamp()) < 1
        assert abs(to_ts / 1000 - to_dt.timestamp()) < 1

    @pytest.mark.asyncio
    async def test_response_contains_fixture_data(self, device, mock_request):
        """Verify response events contain fixture prediction data."""
        mock_request.return_value = SAMPLE_WATER_USAGE_EVENTS

        from_dt = datetime(2026, 2, 20)
        to_dt = datetime(2026, 2, 24)

        result = await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        assert len(result) == 3

        # First event: Toilet prediction
        event1 = result[0]
        assert event1["event_id"] == "evt_001"
        assert event1["total_flow"] == 1.53
        fixtures = event1["latest_suggested_fixtures_result"]["suggested_fixtures"]
        assert fixtures[0]["fixture_name"] == "Toilet"
        assert fixtures[0]["confidence_score"] == 0.85

        # Second event: Shower prediction
        event2 = result[1]
        assert event2["total_flow"] == 15.2
        fixtures2 = event2["latest_suggested_fixtures_result"]["suggested_fixtures"]
        assert fixtures2[0]["fixture_name"] == "Shower Only"

    @pytest.mark.asyncio
    async def test_response_with_user_correction(self, device, mock_request):
        """Verify response handles events with user-corrected fixture labels."""
        mock_request.return_value = SAMPLE_WATER_USAGE_EVENTS

        from_dt = datetime(2026, 2, 20)
        to_dt = datetime(2026, 2, 24)

        result = await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        # Third event has user correction
        event3 = result[2]
        assert event3["event_id"] == "evt_003"
        assert event3.get("user_fixture_label") == "Kitchen Sink"
        assert event3.get("user_fixture_id") == 7

    @pytest.mark.asyncio
    async def test_empty_response(self, device, mock_request):
        """Verify empty response is handled correctly."""
        mock_request.return_value = []

        from_dt = datetime(2026, 2, 20)
        to_dt = datetime(2026, 2, 24)

        result = await device.get_water_usage_events("DEVICE123", from_dt, to_dt)
        assert result == []

    @pytest.mark.asyncio
    async def test_params_are_strings(self, device, mock_request):
        """Timestamps in params must be strings (API requirement)."""
        mock_request.return_value = []

        from_dt = datetime(2026, 2, 20)
        to_dt = datetime(2026, 2, 24)

        await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        params = mock_request.call_args.kwargs["params"]
        assert isinstance(params["from_ts"], str)
        assert isinstance(params["to_ts"], str)
        assert isinstance(params["device_id"], str)


class TestWaterStatistics:
    """Tests for get_water_statistics."""

    @pytest.mark.asyncio
    async def test_get_water_statistics(self, device, mock_request):
        mock_request.return_value = [{"ts": 1771945200000, "value": 1.5}]

        result = await device.get_water_statistics(
            "DEVICE123", 1771945200000, 1771948800000
        )

        mock_request.assert_called_once_with(
            "get",
            f"{API_BASE}/devices/DEVICE123/water_statistics/history/",
            params={"from_ts": 1771945200000, "to_ts": 1771948800000},
        )
        assert len(result) == 1


class TestValveControl:
    """Tests for valve operations."""

    @pytest.mark.asyncio
    async def test_open_valve(self, device, mock_request):
        mock_request.return_value = {}
        await device.open_valve("DEVICE123")
        mock_request.assert_called_once_with(
            "post", f"{API_BASE}/devices/DEVICE123/sov/Open"
        )

    @pytest.mark.asyncio
    async def test_close_valve(self, device, mock_request):
        mock_request.return_value = {}
        await device.close_valve("DEVICE123")
        mock_request.assert_called_once_with(
            "post", f"{API_BASE}/devices/DEVICE123/sov/Close"
        )


class TestAwayMode:
    """Tests for away mode operations."""

    @pytest.mark.asyncio
    async def test_get_away_mode(self, device, mock_request):
        mock_request.return_value = {"value": "true"}
        result = await device.get_away_mode("DEVICE123")
        mock_request.assert_called_once_with(
            "get",
            f"{API_BASE}/preferences/device/DEVICE123/leak_sensitivity_away_mode",
        )

    @pytest.mark.asyncio
    async def test_enable_away_mode(self, device, mock_request):
        mock_request.return_value = {}
        await device.enable_away_mode("DEVICE123")

        call_args = mock_request.call_args
        assert call_args[0][0] == "post"
        json_data = call_args.kwargs.get("json", call_args[1].get("json"))
        assert json_data[0]["value"] == "true"

    @pytest.mark.asyncio
    async def test_disable_away_mode(self, device, mock_request):
        mock_request.return_value = {}
        await device.disable_away_mode("DEVICE123")

        call_args = mock_request.call_args
        json_data = call_args.kwargs.get("json", call_args[1].get("json"))
        assert json_data[0]["value"] == "false"


class TestFirmware:
    """Tests for firmware operations."""

    @pytest.mark.asyncio
    async def test_get_latest_firmware_info(self, device, mock_request):
        mock_request.return_value = SAMPLE_FIRMWARE_INFO
        result = await device.get_latest_firmware_info("DEVICE123")

        assert result["fw_version"] == "3.2.1"
        assert result["product_code"] == "PP2"


class TestHealthTests:
    """Tests for health test operations."""

    @pytest.mark.asyncio
    async def test_run_leak_test_standard(self, device, mock_request):
        mock_request.return_value = {}
        await device.run_leak_test("DEVICE123")

        call_args = mock_request.call_args
        json_data = call_args.kwargs.get("json", call_args[1].get("json"))
        assert json_data["test_duration"] == "s"

    @pytest.mark.asyncio
    async def test_run_leak_test_extended(self, device, mock_request):
        mock_request.return_value = {}
        await device.run_leak_test("DEVICE123", extended_test=True)

        call_args = mock_request.call_args
        json_data = call_args.kwargs.get("json", call_args[1].get("json"))
        assert json_data["test_duration"] == "e"
