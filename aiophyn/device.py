"""Define /devices endpoints."""
from datetime import datetime
from typing import Awaitable, Any, Callable, Optional, Union

from .const import API_BASE


class Device:
    """Define an object to handle the endpoints."""

    def __init__(self, request: Callable[..., Awaitable]) -> None:
        """Initialize."""
        self._request: Callable[..., Awaitable] = request

    async def get_state(self, device_id: str) -> dict:
        """Return state of a device.

        Returns the current device state including sensor readings,
        valve status, and configuration.

        :param device_id: Unique identifier for the device
        :type device_id: ``str``
        :return: Dict with device state. Key fields:
            - device_id (str), product_code (str), serial_number (str)
            - fw_version (str): Firmware version as numeric string (e.g. "40809001")
            - sov_status.v (str): Valve state — "Open", "Closed", "Partial", "LeakExp"
            - online_status.v (str): "online" or "offline"
            - temperature (dict): min, max, mean (floats in °F), ts
            - pressure (dict): min, median, max, mean, percentile95,
              pressure_threshold_95, percentile5 (floats in PSI), ts
            - flow (dict): min, max, mean (floats in GPM), ts
            - signal_strength (int): WiFi RSSI in dBm
            - auto_shutoff_enable (bool): Whether auto shutoff is enabled
            - auto_shutoff_eligible (int): Eligibility percentage (0-100)
            - timezone (str), partner (str), users (list[str]), created_ts (int)
        :rtype: ``dict``
        """
        return await self._request("get", f"{API_BASE}/devices/{device_id}/state")

    async def get_consumption(
        self,
        device_id: str,
        duration: str,
        precision: int = 6,
        details: bool = False,
        event_count: bool = False,
        comparison: bool = False,
    ) -> dict:
        """Return water consumption of a device.

        :param device_id: Unique identifier for the device
        :type device_id: ``str``
        :param duration: Date string formatted as 'YYYY/MM/DD', 'YYYY/MM', or 'YYYY'
        :type duration: ``str``
        :param precision: Decimal places of measurement precision
        :type precision: ``int``
        :param details: Include detailed breakdown of consumption
        :type details: ``bool``
        :param event_count: Include the event count
        :type event_count: ``bool``
        :param comparison: Include comparison data
        :type comparison: ``bool``
        :rtype: ``dict``
        """

        params = {
            "device_id": device_id,
            "duration": duration,
            "precision": precision,
        }

        if details:
            params["details"] = "Y"

        if event_count:
            params["event_count"] = "Y"

        if comparison:
            params["comparison"] = "Y"

        return await self._request(
            "get", f"{API_BASE}/devices/{device_id}/consumption/details", params=params
        )

    async def get_water_statistics(self, device_id: str, from_ts: int, to_ts: int) -> list[dict[str, Any]]:
        """Get statistics about a device sensor.

        Returns daily statistics including flow, pressure, temperature,
        plumbing type, quiet periods, and eco-water detection data.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :param from_ts: Lower bound timestamp in milliseconds (13 digits)
        :type from_ts: int
        :param to_ts: Upper bound timestamp in milliseconds (13 digits)
        :type to_ts: int
        :return: List of daily statistics entries.
            Each entry contains flow (min/max/mean), pressure (min/median/max/mean/
            percentile95/pressure_threshold_95/percentile5), temperature (min/max/mean),
            plus_rt_threshold, device_id, plumbing_type, ecowater_found_today,
            device_local_date, ecowater_exist, quiet_periods, and ts.
        :rtype: list[dict[str, Any]]
        """
        params = {
            "from_ts": from_ts,
            "to_ts": to_ts
        }

        return await self._request(
            "get", f"{API_BASE}/devices/{device_id}/water_statistics/history/", params=params
        )

    async def open_valve(self, device_id: str) -> dict:
        """Open a device shutoff valve.

        :param device_id: Unique identifier for the device
        :type device_id: ``str``
        :rtype: ``dict``
        """
        return await self._request(
            "post",
            f"{API_BASE}/devices/{device_id}/sov/Open",
        )

    async def close_valve(self, device_id: str) -> dict:
        """Close a device shutoff valve.

        :param device_id: Unique identifier for the device
        :type device_id: ``str``
        :rtype: ``dict``
        """
        return await self._request(
            "post",
            f"{API_BASE}/devices/{device_id}/sov/Close",
        )

    async def get_away_mode(self, device_id: str) -> dict:
        """Return away mode status of a device.

        :param device_id: Unique identifier for the device
        :type device_id: ``str``
        :rtype: ``dict``
        """
        return await self._request("get", f"{API_BASE}/preferences/device/{device_id}/leak_sensitivity_away_mode")


    async def enable_away_mode(self, device_id: str) -> None:
        """Enable the device's away mode.

        :param device_id: Unique identifier for the device
        :type device_id: ``str``
        :rtype: ``dict``
        """
        data = [
            {
                "name": "leak_sensitivity_away_mode",
                "value": "true",
                "device_id": device_id,
            }
        ]
        return await self._request(
            "post", f"{API_BASE}/preferences/device/{device_id}", json=data
        )

    async def disable_away_mode(self, device_id: str) -> None:
        """Disable the device's away mode.

        :param device_id: Unique identifier for the device
        :type device_id: ``str``
        :rtype: ``dict``
        """
        data = [
            {
                "name": "leak_sensitivity_away_mode",
                "value": "false",
                "device_id": device_id,
            }
        ]
        return await self._request(
            "post", f"{API_BASE}/preferences/device/{device_id}", json=data
        )
    
    async def get_autoshutoff_status(self, device_id: str) -> dict:
        """Get auto shutoff status for a device.

        Returns the current auto shutoff configuration including whether
        it is enabled and the eligibility percentage.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :return: Dict with auto_shutoff_enable (bool) and auto_shutoff_eligible (int).
        :rtype: dict
        """
        return await self._request(
            "get", f"{API_BASE}/devices/{device_id}/auto_shutoff"
        )

    async def get_device_preferences(self, device_id: str) -> list[dict]:
        """Get device preferences.

        Returns all preferences configured for the device, such as
        leak_sensitivity_away_mode and scheduler_enable.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :return: List of preference dicts, each with name (str), value (str), and device_id (str).
        :rtype: list[dict]
        """
        return await self._request(
            "get", f"{API_BASE}/preferences/device/{device_id}"
        )
    
    async def get_health_tests(self, device_id: str) -> dict:
        """Get health test history for a device.

        Returns grouped health/leak test results including pass/fail status.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :return: Dict with ``data`` key containing list of test results.
            Each test has end_time, is_warn (bool), is_leak (bool), and other fields.
        :rtype: dict
        """
        return await self._request(
            "get", f"{API_BASE}/devices/{device_id}/health_tests?list_type=grouped"
        )
    
    async def get_latest_firmware_info(self, device_id: str) -> list[dict]:
        """Get latest firmware information for a device.

        .. note::
            The API returns a list; callers typically use ``[0]`` to get
            the first (and usually only) entry.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :return: List of firmware info dicts. Each contains device_id (str),
            server_ts (int, milliseconds), fw_version (int, e.g. 40809001),
            and upgraded_seconds (int, epoch seconds of last upgrade).
        :rtype: list[dict]
        """
        return await self._request(
            "get", f"{API_BASE}/firmware/latestVersion/v2?device_id={device_id}"
        )

    async def run_leak_test(self, device_id: str, extended_test: Union[bool, str] = False) -> dict:
        """Run a leak test.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :param extended_test: Whether to run an extended test. Accepts bool or
            string ("true"/"false") for compatibility with HA service calls.
        :type extended_test: bool or str, optional
        :return: API response
        :rtype: dict
        """
        if isinstance(extended_test, str):
            extended_test = extended_test.lower() == "true"
        data = {
            "initiator": "App",
            "test_duration": "e" if extended_test else "s"
        }
        return await self._request(
            "post", f"{API_BASE}/devices/{device_id}/health_tests", json=data
        )

    async def set_autoshutoff_enabled(self, device_id: str, shutoff_on: bool, time: int | None = None) -> dict:
        """Enable or disable auto shutoff for a device.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :param shutoff_on: True to enable auto shutoff, False to disable.
        :type shutoff_on: bool
        :param time: When disabling, duration in seconds before re-enabling
            (e.g. 30, 3600, 21600, 86400). None for indefinite.
        :type time: int or None
        :return: API response
        :rtype: dict
        """
        url = f"{API_BASE}/devices/{device_id}/auto_shutoff/status/"
        if shutoff_on == True:
            url += "Enable"
        else:
            url += "Disable"
            if time != None:
                url += "/%s" % time
        return await self._request(
            "post", url
        )

    async def set_device_preferences(self, device_id: str, data: list[dict]) -> None:
        """Set device preferences

        :param device_id: Unique identifier for the device
        :type device_id: str
        :param data: List of dicts which have the keys: device_id, name, value
        :type data: List[dict]
        """
        return await self._request(
            "post", f"{API_BASE}/preferences/device/{device_id}", json=data
        )

    async def get_water_usage_events(
        self,
        device_id: str,
        from_datetime: datetime,
        to_datetime: datetime,
    ) -> list[dict]:
        """Get water usage events with fixture predictions.

        Fetches individual water usage events for the specified time range,
        including ML-based fixture predictions and confidence scores.

        :param device_id: Unique identifier for the device
        :type device_id: str
        :param from_datetime: Start of time range
        :type from_datetime: datetime
        :param to_datetime: End of time range
        :type to_datetime: datetime
        :return: List of water usage events. Each event contains:
            - id (str): UUID-format event identifier
            - device_id (str): Device identifier
            - product_code (str): e.g. "PP2"
            - open_edge_timestamp (int): Start time in milliseconds
            - close_edge_timestamp (int): End time in milliseconds
            - total_flow (float): Total water flow in gallons
            - flow_rate (float): Flow rate in GPM
            - latest_user_feedback (dict): User correction, empty ``{}`` if none
            - latest_suggested_fixtures_result (dict): Contains:
                - algorithm_name (str): e.g. "ruleflowtimefeatures"
                - suggested_fixtures (list[dict]): Each with fixture_id (int),
                  fixture_name (str), confidence_score (float),
                  prediction_algorithm (str): Classification source. Known values:
                    "clustering" (ML flow-pattern matching),
                    "heuristics" (rule-based fallback),
                    "user-feedback" (user-corrected),
                    "bayesian_v2" (ML model), "duration_based" (duration rules)
                - created_timestamp (int): Prediction timestamp in milliseconds
        :rtype: list[dict]

        .. note::
            The Phyn API requires timestamps in MILLISECONDS (13 digits).
            This method handles the conversion internally from datetime objects.
        """
        from_ts = int(from_datetime.timestamp() * 1000)
        to_ts = int(to_datetime.timestamp() * 1000)

        params = {
            "device_id": device_id,
            "from_ts": str(from_ts),
            "to_ts": str(to_ts),
        }

        return await self._request(
            "get", f"{API_BASE}/water-usage-events", params=params
        )

    async def submit_water_usage_event_feedback(
        self,
        event_id: str,
        fixture_id: int,
        sub_fixture_id: Optional[int] = None,
        tell_us: Optional[str] = None,
    ) -> dict:
        """Submit fixture correction feedback for a water usage event.

        :param event_id: Water usage event identifier
        :type event_id: str
        :param fixture_id: Correct fixture type ID (home_inventory_type_id)
        :type fixture_id: int
        :param sub_fixture_id: Optional sub-fixture identifier
        :type sub_fixture_id: Optional[int]
        :param tell_us: Optional custom fixture text
        :type tell_us: Optional[str]
        :return: API response
        :rtype: dict
        """
        data = {
            "fixture_id": fixture_id,
            "sub_fixture_id": sub_fixture_id,
            "tell_us": tell_us,
        }
        return await self._request(
            "post",
            f"{API_BASE}/water-usage-events/{event_id}/feedback/",
            token_type="id",
            json=data,
        )
