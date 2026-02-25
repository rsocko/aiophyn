"""Fixtures and helpers for aiophyn tests."""
import pytest
from unittest.mock import AsyncMock

from aiophyn.device import Device
from aiophyn.home import Home
from aiophyn.home_inventory import HomeInventory


@pytest.fixture
def mock_request():
    """Create a mock request function that can be configured per test."""
    return AsyncMock()


@pytest.fixture
def device(mock_request):
    """Create a Device instance with a mocked request function."""
    return Device(mock_request)


@pytest.fixture
def home(mock_request):
    """Create a Home instance with a mocked request function."""
    return Home(mock_request)


@pytest.fixture
def home_inventory(mock_request):
    """Create a HomeInventory instance with a mocked request function."""
    return HomeInventory(mock_request)


# ---- Sample API response data ----
# Based on real API responses captured from the Phyn API.
# See: ideation/experiments/home-automation/phyn-api-exploration/test-data/

SAMPLE_FIXTURE_TYPES = [
    {
        "home_inventory_type_id": 1,
        "name": "Hot Tub",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/hot-tub-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 2,
        "name": "Irrigation System",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/irrigation-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 3,
        "name": "Outdoor Spigot",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/outdoor-spigot-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 4,
        "name": "Pool",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/pool-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 5,
        "name": "Shower Only",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/shower-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 6,
        "name": "Shower Tub Combo",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/shower-tub-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 7,
        "name": "Sink",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/sink-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 8,
        "name": "Toilet",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/toilet-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 9,
        "name": "Tub",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/tub-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 10,
        "name": "Water Softener",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/water-softener-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 11,
        "name": "Reverse Osmosis Filter",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/ro-filter-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 16,
        "name": "Dishwasher",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/dishwasher-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 30,
        "name": "Washing Machine",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/washing-machine-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 34,
        "name": "Other",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/other-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 38,
        "name": "Hot Water Heater",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/other-black.png",
        "home_inventory_type": "F",
    },
    {
        "home_inventory_type_id": 42,
        "name": "Refrigerator",
        "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/other-black.png",
        "home_inventory_type": "F",
    },
]

SAMPLE_DEVICE_INVENTORY = {
    "list": [
        {
            "count": 5,
            "name": "Toilet",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/toilet-black.png",
            "home_inventory_type_id": 8,
            "home_inventory_type": "F",
        },
        {
            "count": 2,
            "name": "Shower Only",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/shower-black.png",
            "home_inventory_type_id": 5,
            "home_inventory_type": "F",
            "sub_fixtures": [
                {
                    "name": "Master Bathroom",
                    "active": True,
                    "id": 1647984949429,
                }
            ],
        },
        {
            "count": 9,
            "name": "Sink",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/sink-black.png",
            "home_inventory_type_id": 7,
            "home_inventory_type": "F",
        },
        {
            "count": 1,
            "name": "Dishwasher",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/dishwasher-black.png",
            "home_inventory_type_id": 16,
            "home_inventory_type": "F",
        },
        {
            "count": 1,
            "name": "Washing Machine",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/washing-machine-black.png",
            "home_inventory_type_id": 30,
            "home_inventory_type": "F",
        },
        {
            "count": 2,
            "name": "Shower Tub Combo",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/shower-tub-black.png",
            "home_inventory_type_id": 6,
            "home_inventory_type": "F",
        },
        {
            "count": 1,
            "name": "Tub",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/tub-black.png",
            "home_inventory_type_id": 9,
            "home_inventory_type": "F",
        },
        {
            "count": 1,
            "name": "Hot Water Heater",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/other-black.png",
            "home_inventory_type_id": 38,
            "home_inventory_type": "F",
        },
        {
            "count": 1,
            "name": "Refrigerator",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/other-black.png",
            "home_inventory_type_id": 42,
            "home_inventory_type": "F",
        },
        {
            "count": 0,
            "name": "Irrigation System",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/irrigation-black.png",
            "home_inventory_type_id": 2,
            "home_inventory_type": "F",
        },
        {
            "count": 0,
            "name": "Hot Tub",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/hot-tub-black.png",
            "home_inventory_type_id": 1,
            "home_inventory_type": "F",
        },
        {
            "count": 0,
            "name": "Other",
            "image": "https://s3.amazonaws.com/com.phyn.icons/prd/v2/other-black.png",
            "home_inventory_type_id": 34,
            "home_inventory_type": "F",
        },
    ]
}

SAMPLE_WATER_USAGE_EVENTS = [
    {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890-12345",
        "device_id": "AABBCCDDEEFF",
        "product_code": "PP2",
        "open_edge_timestamp": 1771945200000,
        "close_edge_timestamp": 1771945260000,
        "total_flow": 1.53,
        "flow_rate": 1.53,
        "latest_user_feedback": {},
        "latest_suggested_fixtures_result": {
            "algorithm_name": "ruleflowtimefeatures",
            "suggested_fixtures": [
                {
                    "fixture_id": 8,
                    "fixture_name": "Toilet",
                    "confidence_score": 0.85,
                    "prediction_algorithm": "heuristics",
                },
                {
                    "fixture_id": 7,
                    "fixture_name": "Sink",
                    "confidence_score": 0.10,
                    "prediction_algorithm": "heuristics",
                },
            ],
            "created_timestamp": 1771945320000,
        },
    },
    {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901-12345",
        "device_id": "AABBCCDDEEFF",
        "product_code": "PP2",
        "open_edge_timestamp": 1771948800000,
        "close_edge_timestamp": 1771949400000,
        "total_flow": 15.2,
        "flow_rate": 2.53,
        "latest_user_feedback": {},
        "latest_suggested_fixtures_result": {
            "algorithm_name": "ruleflowtimefeatures",
            "suggested_fixtures": [
                {
                    "fixture_id": 5,
                    "fixture_name": "Shower Only",
                    "confidence_score": 0.92,
                    "prediction_algorithm": "heuristics",
                },
            ],
            "created_timestamp": 1771949460000,
        },
    },
    {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012-12345",
        "device_id": "AABBCCDDEEFF",
        "product_code": "PP2",
        "open_edge_timestamp": 1771952400000,
        "close_edge_timestamp": 1771952460000,
        "total_flow": 0.8,
        "flow_rate": 0.8,
        "latest_user_feedback": {
            "fixture_id": 7,
            "sub_fixture_id": 0,
            "tell_us": "Kitchen Sink",
        },
        "latest_suggested_fixtures_result": {
            "algorithm_name": "ruleflowtimefeatures",
            "suggested_fixtures": [
                {
                    "fixture_id": 7,
                    "fixture_name": "Sink",
                    "confidence_score": 0.78,
                    "prediction_algorithm": "heuristics",
                },
            ],
            "created_timestamp": 1771952520000,
        },
    },
    {
        "id": "d4e5f6a7-b8c9-0123-defa-234567890123-12345",
        "device_id": "AABBCCDDEEFF",
        "product_code": "PP2",
        "open_edge_timestamp": 1771824392128,
        "close_edge_timestamp": 1771824441115,
        "total_flow": 0.496,
        "flow_rate": 0.608,
        "latest_user_feedback": {},
        "latest_suggested_fixtures_result": {
            "algorithm_name": "ruleflowtimefeatures",
            "suggested_fixtures": [
                {
                    "fixture_id": 16,
                    "fixture_name": "Dishwasher",
                    "confidence_score": 0.452,
                    "prediction_algorithm": "user-feedback",
                },
                {
                    "fixture_id": 7,
                    "fixture_name": "Sink",
                    "confidence_score": 0,
                    "prediction_algorithm": "heuristics",
                },
                {
                    "fixture_id": 8,
                    "fixture_name": "Toilet",
                    "confidence_score": 0,
                    "prediction_algorithm": "heuristics",
                },
            ],
            "created_timestamp": 1771824532710,
        },
    },
]

SAMPLE_DEVICE_STATE = {
    "sd_status": {
        "v": "G",
        "r": "watchdog",
        "ts": 1770911462000,
    },
    "device_id": "AABBCCDDEEFF",
    "product_code": "PP2",
    "temperature": {
        "min": 56.08,
        "max": 75.41,
        "mean": 65.89035547874674,
        "ts": 1771749748730,
    },
    "flow": {
        "min": 0.3906375222271139,
        "max": 3.0041370143149284,
        "mean": 1.721237873423644,
        "ts": 1771749748730,
    },
    "fw_version": "40809001",
    "signal_strength": -67,
    "online_status": {
        "v": "online",
        "sid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "ts": 1771524507950,
    },
    "hw_version": "0",
    "network_name": "IoT",
    "auto_shutoff_eligible": 100,
    "serial_number": "000000PP200001",
    "sov_status": {
        "v": "Open",
        "ts": 1771524508000,
    },
    "pressure": {
        "min": 51.998128179043746,
        "median": 58.6375967413442,
        "max": 61.94134419551935,
        "mean": 58.66604666236688,
        "percentile95": 59.437041479542465,
        "pressure_threshold_95": 59.9,
        "percentile5": 57.94231633906762,
        "ts": 1771749748730,
    },
    "timezone": "America/New_York",
    "partner": "phyn",
    "users": ["pws-00000000-0000-0000-0000-000000000001"],
    "auto_shutoff_enable": True,
    "created_ts": 1645972604139,
}

# Alternate device state for a second device (different values, auto_shutoff off)
SAMPLE_DEVICE_STATE_2 = {
    "sd_status": {
        "v": "G",
        "r": "watchdog",
        "ts": 1770885976000,
    },
    "device_id": "112233445566",
    "product_code": "PP2",
    "temperature": {
        "min": 62.93,
        "max": 65.57,
        "mean": 64.42262528578821,
        "ts": 1771750658485,
    },
    "flow": {
        "min": 0,
        "max": 0,
        "mean": 0,
        "ts": 1771750658485,
    },
    "fw_version": "40809001",
    "signal_strength": -40,
    "online_status": {
        "v": "online",
        "sid": "11111111-2222-3333-4444-555555555555",
        "ts": 1771465887748,
    },
    "hw_version": "0",
    "network_name": "IoT",
    "auto_shutoff_eligible": 100,
    "serial_number": "000000PP200002",
    "sov_status": {
        "a": "app:0000000000000:0000000000",
        "client_ts": 1771750373770,
        "v": "Open",
        "ts": 1771750373668,
    },
    "pressure": {
        "min": 70.36378433367243,
        "median": 76.41141403865717,
        "max": 82.30929878048781,
        "mean": 76.31288165129982,
        "percentile95": 78.56825301673159,
        "pressure_threshold_95": 78.6,
        "percentile5": 73.6178514750763,
        "ts": 1771750658485,
    },
    "timezone": "America/New_York",
    "partner": "phyn",
    "users": ["pws-00000000-0000-0000-0000-000000000001"],
    "auto_shutoff_enable": False,
    "created_ts": 1692219723466,
}

SAMPLE_HOMES = [
    {
        "id": "home_001",
        "address": {"address1": "123 Main St"},
        "device_ids": ["AABBCCDDEEFF", "112233445566"],
        "devices": [
            {
                "device_id": "AABBCCDDEEFF",
                "product_code": "PP2",
                "name": "Phyn Plus",
            },
            {
                "device_id": "112233445566",
                "product_code": "PP2",
                "name": "Phyn Plus 2",
            },
        ],
    }
]

SAMPLE_CONSUMPTION = {
    "water_consumption": 53.95314,
    "details": {
        "6": 0.17969,
        "7": 2.73438,
        "8": 1.42188,
        "9": 2.89062,
        "10": 2.57031,
        "11": 1.0625,
        "12": 1.35938,
        "13": 17.48438,
        "14": 6.32813,
        "15": 0.25,
        "16": 1.38281,
        "17": 1.42969,
        "18": 1.50781,
        "19": 2.21875,
        "20": 1.35938,
        "21": 1.07812,
        "23": 8.69531,
    },
    "water_usage_event_count": 50,
    "average_consumption": 189.221,
}

# Consumption with no usage (e.g. second device with no activity)
SAMPLE_CONSUMPTION_EMPTY = {
    "water_consumption": 0,
    "details": {},
    "water_usage_event_count": 0,
    "average_consumption": 181.34,
}

SAMPLE_FIRMWARE_INFO = {
    "device_id": "AABBCCDDEEFF",
    "server_ts": 1771524508293,
    "fw_version": 40809001,
    "upgraded_seconds": 1770513217,
}

SAMPLE_WATER_STATISTICS = [
    {
        "flow": {
            "max": 3.0041370143149284,
            "mean": 1.721237873423644,
            "min": 0.3906375222271139,
        },
        "pressure": {
            "min": 51.998128179043746,
            "median": 58.6375967413442,
            "max": 61.94134419551935,
            "mean": 58.66604666236688,
            "percentile95": 59.437041479542465,
            "pressure_threshold_95": 59.9,
            "percentile5": 57.94231633906762,
        },
        "plus_rt_threshold": 0.04,
        "device_id": "AABBCCDDEEFF",
        "plumbing_type": "non-prv",
        "ecowater_found_today": False,
        "device_local_date": "2026/02/21",
        "ecowater_exist": False,
        "temperature": {
            "max": 75.41,
            "mean": 65.89035547874674,
            "min": 56.08,
        },
        "quiet_periods": [2, 3, 5],
        "ts": 1771749748730,
    },
    {
        "flow": {
            "max": 4.4843918728698196,
            "mean": 2.1900192425756173,
            "min": 0.3294016393442623,
        },
        "pressure": {
            "min": 42.18183943089431,
            "median": 58.1810986775178,
            "max": 64.98936927772127,
            "mean": 58.24300353871653,
            "percentile95": 59.785097560975615,
            "pressure_threshold_95": 59.9,
            "percentile5": 57.231166316173315,
        },
        "plus_rt_threshold": 0.04,
        "device_id": "AABBCCDDEEFF",
        "plumbing_type": "non-prv",
        "ecowater_found_today": False,
        "device_local_date": "2026/02/20",
        "ecowater_exist": False,
        "temperature": {
            "max": 75.06,
            "mean": 66.28291281672779,
            "min": 53.09,
        },
        "quiet_periods": [2, 3, 5],
        "ts": 1771663423760,
    },
]

SAMPLE_DEVICE_PREFERENCES = [
    {
        "name": "leak_sensitivity_away_mode",
        "value": "false",
        "device_id": "AABBCCDDEEFF",
    },
]

SAMPLE_AWAY_MODE = {
    "name": "leak_sensitivity_away_mode",
    "value": "false",
    "device_id": "AABBCCDDEEFF",
}

