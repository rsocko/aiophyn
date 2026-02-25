"""Tests for the Device class.

Tests the existing device methods and the new get_water_usage_events method.
Validates that:
  - Correct API URLs are constructed
  - Datetime-to-millisecond conversion works correctly
  - Parameters are passed properly
  - Response data is returned as-is
  - Mock data accurately reflects real Phyn API response structures
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, call

from aiophyn.device import Device
from aiophyn.const import API_BASE

try:
    from tests.conftest import (
        SAMPLE_DEVICE_STATE,
        SAMPLE_DEVICE_STATE_2,
        SAMPLE_CONSUMPTION,
        SAMPLE_CONSUMPTION_EMPTY,
        SAMPLE_WATER_USAGE_EVENTS,
        SAMPLE_FIRMWARE_INFO,
        SAMPLE_WATER_STATISTICS,
        SAMPLE_DEVICE_PREFERENCES,
        SAMPLE_AWAY_MODE,
    )
except ModuleNotFoundError:
    from conftest import (
        SAMPLE_DEVICE_STATE,
        SAMPLE_DEVICE_STATE_2,
        SAMPLE_CONSUMPTION,
        SAMPLE_CONSUMPTION_EMPTY,
        SAMPLE_WATER_USAGE_EVENTS,
        SAMPLE_FIRMWARE_INFO,
        SAMPLE_WATER_STATISTICS,
        SAMPLE_DEVICE_PREFERENCES,
        SAMPLE_AWAY_MODE,
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
        assert result["temperature"]["mean"] == pytest.approx(65.89, abs=0.01)
        assert result["pressure"]["mean"] == pytest.approx(58.67, abs=0.01)
        assert result["sov_status"]["v"] == "Open"

    @pytest.mark.asyncio
    async def test_get_state_has_real_api_fields(self, device, mock_request):
        """Verify mock data includes all fields observed in real API responses."""
        mock_request.return_value = SAMPLE_DEVICE_STATE
        result = await device.get_state("DEVICE123")

        # Core identification fields
        assert "device_id" in result
        assert "product_code" in result
        assert result["product_code"] == "PP2"

        # Sensor fields with min/max/mean/ts structure
        for field in ("temperature", "flow"):
            assert "min" in result[field]
            assert "max" in result[field]
            assert "mean" in result[field]
            assert "ts" in result[field]

        # Pressure has additional percentile fields
        pressure = result["pressure"]
        assert "min" in pressure
        assert "median" in pressure
        assert "max" in pressure
        assert "mean" in pressure
        assert "percentile95" in pressure
        assert "pressure_threshold_95" in pressure
        assert "percentile5" in pressure

        # Status fields
        assert result["sov_status"]["v"] in ("Open", "Closed")
        assert "ts" in result["sov_status"]
        assert result["online_status"]["v"] in ("online", "offline")
        assert "sd_status" in result
        assert result["sd_status"]["v"] == "G"

        # Device info fields
        assert isinstance(result["fw_version"], str)
        assert isinstance(result["signal_strength"], int)
        assert isinstance(result["serial_number"], str)
        assert result["timezone"] == "America/New_York"
        assert isinstance(result["auto_shutoff_enable"], bool)
        assert isinstance(result["auto_shutoff_eligible"], int)
        assert isinstance(result["users"], list)

    @pytest.mark.asyncio
    async def test_get_state_second_device(self, device, mock_request):
        """Verify second device state has different values reflecting real variation."""
        mock_request.return_value = SAMPLE_DEVICE_STATE_2
        result = await device.get_state("DEVICE456")

        # Different device ID and signal strength
        assert result["device_id"] == "112233445566"
        assert result["signal_strength"] == -40

        # Zero flow (idle device)
        assert result["flow"]["mean"] == 0
        assert result["flow"]["max"] == 0

        # Auto shutoff disabled on this device
        assert result["auto_shutoff_enable"] is False

        # sov_status has extended fields observed in real API
        assert "a" in result["sov_status"]
        assert "client_ts" in result["sov_status"]


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
        assert result["water_consumption"] == pytest.approx(53.95314)

    @pytest.mark.asyncio
    async def test_get_consumption_has_real_api_fields(self, device, mock_request):
        """Verify consumption response matches real API structure."""
        mock_request.return_value = SAMPLE_CONSUMPTION
        result = await device.get_consumption("DEVICE123", "2026/02/24")

        assert "water_consumption" in result
        assert "details" in result
        assert "water_usage_event_count" in result
        assert "average_consumption" in result

        # Details keys are hour strings (not integers)
        assert isinstance(result["details"], dict)
        for key in result["details"]:
            assert isinstance(key, str)
            assert int(key) >= 0 and int(key) <= 23

        # Event count is consistent with real data scale
        assert result["water_usage_event_count"] == 50
        assert result["average_consumption"] == pytest.approx(189.221)

    @pytest.mark.asyncio
    async def test_get_consumption_empty_device(self, device, mock_request):
        """Verify empty consumption response for idle device."""
        mock_request.return_value = SAMPLE_CONSUMPTION_EMPTY
        result = await device.get_consumption("DEVICE456", "2026/02/24")

        assert result["water_consumption"] == 0
        assert result["details"] == {}
        assert result["water_usage_event_count"] == 0
        assert result["average_consumption"] == pytest.approx(181.34)

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

        assert len(result) == 4

        # First event: Toilet prediction with heuristics algorithm
        event1 = result[0]
        assert event1["id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890-12345"
        assert event1["product_code"] == "PP2"
        assert event1["total_flow"] == 1.53
        fixtures_result = event1["latest_suggested_fixtures_result"]
        assert fixtures_result["algorithm_name"] == "ruleflowtimefeatures"
        assert "created_timestamp" in fixtures_result
        fixtures = fixtures_result["suggested_fixtures"]
        assert fixtures[0]["fixture_name"] == "Toilet"
        assert fixtures[0]["confidence_score"] == 0.85
        assert fixtures[0]["prediction_algorithm"] == "heuristics"

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
        assert event3["id"] == "c3d4e5f6-a7b8-9012-cdef-123456789012-12345"
        feedback = event3.get("latest_user_feedback", {})
        assert feedback.get("tell_us") == "Kitchen Sink"
        assert feedback.get("fixture_id") == 7

    @pytest.mark.asyncio
    async def test_response_empty_user_feedback(self, device, mock_request):
        """Verify events without user feedback have empty dict (not absent)."""
        mock_request.return_value = SAMPLE_WATER_USAGE_EVENTS

        from_dt = datetime(2026, 2, 20)
        to_dt = datetime(2026, 2, 24)

        result = await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        # Events without user correction have empty dict, not missing key
        event1 = result[0]
        assert "latest_user_feedback" in event1
        assert event1["latest_user_feedback"] == {}

    @pytest.mark.asyncio
    async def test_response_user_feedback_prediction_algorithm(self, device, mock_request):
        """Verify event with 'user-feedback' prediction algorithm."""
        mock_request.return_value = SAMPLE_WATER_USAGE_EVENTS

        from_dt = datetime(2026, 2, 20)
        to_dt = datetime(2026, 2, 24)

        result = await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        # Fourth event uses user-feedback prediction algorithm
        event4 = result[3]
        fixtures = event4["latest_suggested_fixtures_result"]["suggested_fixtures"]
        assert fixtures[0]["prediction_algorithm"] == "user-feedback"
        assert fixtures[0]["fixture_name"] == "Dishwasher"
        # Has multiple suggested fixtures with varying confidence
        assert len(fixtures) == 3
        assert fixtures[1]["confidence_score"] == 0
        assert fixtures[2]["confidence_score"] == 0

    @pytest.mark.asyncio
    async def test_response_has_real_api_structure(self, device, mock_request):
        """Ensure all events match the full structure from real API responses."""
        mock_request.return_value = SAMPLE_WATER_USAGE_EVENTS

        from_dt = datetime(2026, 2, 20)
        to_dt = datetime(2026, 2, 24)

        result = await device.get_water_usage_events("DEVICE123", from_dt, to_dt)

        required_event_fields = {
            "id", "device_id", "product_code",
            "open_edge_timestamp", "close_edge_timestamp",
            "total_flow", "flow_rate",
            "latest_user_feedback", "latest_suggested_fixtures_result",
        }

        for event in result:
            assert required_event_fields.issubset(event.keys()), (
                f"Event {event.get('id')} missing fields: "
                f"{required_event_fields - event.keys()}"
            )

            # Timestamps are 13-digit millisecond values
            assert len(str(event["open_edge_timestamp"])) == 13
            assert len(str(event["close_edge_timestamp"])) == 13

            # Fixture result structure
            fixtures_result = event["latest_suggested_fixtures_result"]
            assert "algorithm_name" in fixtures_result
            assert "suggested_fixtures" in fixtures_result
            assert "created_timestamp" in fixtures_result

            for fixture in fixtures_result["suggested_fixtures"]:
                assert "fixture_id" in fixture
                assert "fixture_name" in fixture
                assert "confidence_score" in fixture
                assert "prediction_algorithm" in fixture

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
        mock_request.return_value = SAMPLE_WATER_STATISTICS

        result = await device.get_water_statistics(
            "DEVICE123", 1771945200000, 1771948800000
        )

        mock_request.assert_called_once_with(
            "get",
            f"{API_BASE}/devices/DEVICE123/water_statistics/history/",
            params={"from_ts": 1771945200000, "to_ts": 1771948800000},
        )
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_water_statistics_has_real_api_structure(self, device, mock_request):
        """Verify water statistics entries have complete real API structure."""
        mock_request.return_value = SAMPLE_WATER_STATISTICS

        result = await device.get_water_statistics(
            "DEVICE123", 1771945200000, 1771948800000
        )

        for entry in result:
            # Core sensor fields
            assert "flow" in entry
            assert "pressure" in entry
            assert "temperature" in entry

            # Flow structure
            assert set(entry["flow"].keys()) == {"min", "max", "mean"}

            # Pressure structure - matches real API including percentiles
            pressure_fields = {"min", "median", "max", "mean", "percentile95",
                             "pressure_threshold_95", "percentile5"}
            assert pressure_fields.issubset(set(entry["pressure"].keys()))

            # Device metadata fields from real API
            assert entry["device_id"] == "AABBCCDDEEFF"
            assert entry["plumbing_type"] == "non-prv"
            assert isinstance(entry["ecowater_found_today"], bool)
            assert isinstance(entry["ecowater_exist"], bool)
            assert isinstance(entry["quiet_periods"], list)
            assert "device_local_date" in entry
            assert "plus_rt_threshold" in entry
            assert "ts" in entry


class TestWaterUsageEventFeedback:
    """Tests for submit_water_usage_event_feedback."""

    @pytest.mark.asyncio
    async def test_submit_feedback_basic(self, device, mock_request):
        mock_request.return_value = {"ok": True}

        await device.submit_water_usage_event_feedback("evt_001", 8)

        mock_request.assert_called_once_with(
            "post",
            f"{API_BASE}/water-usage-events/evt_001/feedback/",
            token_type="id",
            json={
                "fixture_id": 8,
                "sub_fixture_id": None,
                "tell_us": None,
            },
        )

    @pytest.mark.asyncio
    async def test_submit_feedback_with_optional_fields(self, device, mock_request):
        mock_request.return_value = {"ok": True}

        await device.submit_water_usage_event_feedback(
            "evt_002", 7, sub_fixture_id=12, tell_us="Kitchen Sink"
        )

        mock_request.assert_called_once_with(
            "post",
            f"{API_BASE}/water-usage-events/evt_002/feedback/",
            token_type="id",
            json={
                "fixture_id": 7,
                "sub_fixture_id": 12,
                "tell_us": "Kitchen Sink",
            },
        )


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
        mock_request.return_value = SAMPLE_AWAY_MODE
        result = await device.get_away_mode("DEVICE123")
        mock_request.assert_called_once_with(
            "get",
            f"{API_BASE}/preferences/device/DEVICE123/leak_sensitivity_away_mode",
        )
        assert result["name"] == "leak_sensitivity_away_mode"
        assert result["value"] == "false"

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

        assert result["fw_version"] == 40809001
        assert result["device_id"] == "AABBCCDDEEFF"

    @pytest.mark.asyncio
    async def test_firmware_info_has_real_api_fields(self, device, mock_request):
        """Verify firmware response contains fields from real API."""
        mock_request.return_value = SAMPLE_FIRMWARE_INFO
        result = await device.get_latest_firmware_info("DEVICE123")

        assert "device_id" in result
        assert "server_ts" in result
        assert "fw_version" in result
        assert "upgraded_seconds" in result
        assert isinstance(result["fw_version"], int)
        assert isinstance(result["server_ts"], int)

    @pytest.mark.asyncio
    async def test_firmware_info_as_list(self, device, mock_request):
        """Real API returns a list; HA integration indexes with [0]."""
        mock_request.return_value = [SAMPLE_FIRMWARE_INFO]
        result = await device.get_latest_firmware_info("DEVICE123")

        # Simulate HA integration access pattern
        first = result[0]
        assert first["fw_version"] == 40809001
        assert first["device_id"] == "AABBCCDDEEFF"


class TestDevicePreferences:
    """Tests for get_device_preferences."""

    @pytest.mark.asyncio
    async def test_get_device_preferences(self, device, mock_request):
        mock_request.return_value = SAMPLE_DEVICE_PREFERENCES
        result = await device.get_device_preferences("DEVICE123")

        mock_request.assert_called_once_with(
            "get", f"{API_BASE}/preferences/device/DEVICE123"
        )
        assert isinstance(result, list)
        assert result[0]["name"] == "leak_sensitivity_away_mode"
        assert result[0]["device_id"] == "AABBCCDDEEFF"

    @pytest.mark.asyncio
    async def test_set_device_preferences(self, device, mock_request):
        mock_request.return_value = {}
        data = [{"name": "leak_sensitivity_away_mode", "value": "true",
                 "device_id": "DEVICE123"}]
        await device.set_device_preferences("DEVICE123", data)

        mock_request.assert_called_once_with(
            "post", f"{API_BASE}/preferences/device/DEVICE123", json=data
        )


class TestAutoShutoff:
    """Tests for auto shutoff operations."""

    @pytest.mark.asyncio
    async def test_get_autoshutoff_status(self, device, mock_request):
        """Test the corrected method name."""
        mock_request.return_value = {"auto_shutoff_enable": True}
        result = await device.get_autoshutoff_status("DEVICE123")

        mock_request.assert_called_once_with(
            "get", f"{API_BASE}/devices/DEVICE123/auto_shutoff"
        )

    @pytest.mark.asyncio
    async def test_get_autoshuftoff_status_alias(self, device, mock_request):
        """Test backward-compatible alias with original typo still works."""
        mock_request.return_value = {"auto_shutoff_enable": True}
        result = await device.get_autoshuftoff_status("DEVICE123")

        mock_request.assert_called_once_with(
            "get", f"{API_BASE}/devices/DEVICE123/auto_shutoff"
        )

    @pytest.mark.asyncio
    async def test_set_autoshutoff_enabled(self, device, mock_request):
        mock_request.return_value = {}
        await device.set_autoshutoff_enabled("DEVICE123", True)

        mock_request.assert_called_once_with(
            "post", f"{API_BASE}/devices/DEVICE123/auto_shutoff/status/Enable"
        )

    @pytest.mark.asyncio
    async def test_set_autoshutoff_disabled_with_time(self, device, mock_request):
        mock_request.return_value = {}
        await device.set_autoshutoff_enabled("DEVICE123", False, time=3600)

        mock_request.assert_called_once_with(
            "post", f"{API_BASE}/devices/DEVICE123/auto_shutoff/status/Disable/3600"
        )

    @pytest.mark.asyncio
    async def test_set_autoshutoff_disabled_no_time(self, device, mock_request):
        mock_request.return_value = {}
        await device.set_autoshutoff_enabled("DEVICE123", False)

        mock_request.assert_called_once_with(
            "post", f"{API_BASE}/devices/DEVICE123/auto_shutoff/status/Disable"
        )


class TestHealthTests:
    """Tests for health test operations."""

    @pytest.mark.asyncio
    async def test_get_health_tests(self, device, mock_request):
        mock_request.return_value = {}
        await device.get_health_tests("DEVICE123")

        mock_request.assert_called_once_with(
            "get", f"{API_BASE}/devices/DEVICE123/health_tests?list_type=grouped"
        )

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

    @pytest.mark.asyncio
    async def test_run_leak_test_extended_string(self, device, mock_request):
        """Test that string 'true' is handled (HA integration compatibility)."""
        mock_request.return_value = {}
        await device.run_leak_test("DEVICE123", extended_test="true")

        call_args = mock_request.call_args
        json_data = call_args.kwargs.get("json", call_args[1].get("json"))
        assert json_data["test_duration"] == "e"

    @pytest.mark.asyncio
    async def test_run_leak_test_standard_string(self, device, mock_request):
        """Test that string 'false' is handled as standard test."""
        mock_request.return_value = {}
        await device.run_leak_test("DEVICE123", extended_test="false")

        call_args = mock_request.call_args
        json_data = call_args.kwargs.get("json", call_args[1].get("json"))
        assert json_data["test_duration"] == "s"
