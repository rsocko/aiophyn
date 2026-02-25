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

SAMPLE_FIXTURE_TYPES = [
    {"home_inventory_type_id": 1, "name": "Hot Tub", "home_inventory_type": "appliance"},
    {"home_inventory_type_id": 2, "name": "Irrigation System", "home_inventory_type": "outdoor"},
    {"home_inventory_type_id": 5, "name": "Shower Only", "home_inventory_type": "fixture"},
    {"home_inventory_type_id": 6, "name": "Shower Tub Combo", "home_inventory_type": "fixture"},
    {"home_inventory_type_id": 7, "name": "Sink", "home_inventory_type": "fixture"},
    {"home_inventory_type_id": 8, "name": "Toilet", "home_inventory_type": "fixture"},
    {"home_inventory_type_id": 16, "name": "Dishwasher", "home_inventory_type": "appliance"},
    {"home_inventory_type_id": 30, "name": "Washing Machine", "home_inventory_type": "appliance"},
    {"home_inventory_type_id": 34, "name": "Other", "home_inventory_type": "other"},
]

SAMPLE_DEVICE_INVENTORY = {
    "list": [
        {"home_inventory_type_id": 8, "name": "Toilet", "count": 3},
        {"home_inventory_type_id": 5, "name": "Shower Only", "count": 2},
        {"home_inventory_type_id": 7, "name": "Sink", "count": 5},
        {"home_inventory_type_id": 16, "name": "Dishwasher", "count": 1},
        {"home_inventory_type_id": 30, "name": "Washing Machine", "count": 1},
        {"home_inventory_type_id": 2, "name": "Irrigation System", "count": 0},
        {"home_inventory_type_id": 1, "name": "Hot Tub", "count": 0},
    ]
}

SAMPLE_WATER_USAGE_EVENTS = [
    {
        "id": "evt_001",
        "device_id": "28F53741CBBA",
        "open_edge_timestamp": 1771945200000,
        "close_edge_timestamp": 1771945260000,
        "total_flow": 1.53,
        "flow_rate": 1.53,
        "latest_suggested_fixtures_result": {
            "suggested_fixtures": [
                {
                    "fixture_id": 8,
                    "fixture_name": "Toilet",
                    "confidence_score": 0.85,
                    "prediction_algorithm": "clustering",
                },
                {
                    "fixture_id": 7,
                    "fixture_name": "Sink",
                    "confidence_score": 0.10,
                    "prediction_algorithm": "clustering",
                },
            ]
        },
    },
    {
        "id": "evt_002",
        "device_id": "28F53741CBBA",
        "open_edge_timestamp": 1771948800000,
        "close_edge_timestamp": 1771949400000,
        "total_flow": 15.2,
        "flow_rate": 2.53,
        "latest_suggested_fixtures_result": {
            "suggested_fixtures": [
                {
                    "fixture_id": 5,
                    "fixture_name": "Shower Only",
                    "confidence_score": 0.92,
                    "prediction_algorithm": "clustering",
                },
            ]
        },
    },
    {
        "id": "evt_003",
        "device_id": "28F53741CBBA",
        "open_edge_timestamp": 1771952400000,
        "close_edge_timestamp": 1771952460000,
        "total_flow": 0.8,
        "flow_rate": 0.8,
        "latest_suggested_fixtures_result": {
            "suggested_fixtures": [
                {
                    "fixture_id": 7,
                    "fixture_name": "Sink",
                    "confidence_score": 0.78,
                    "prediction_algorithm": "clustering",
                },
            ]
        },
        "latest_user_feedback": {
            "fixture_id": 7,
            "sub_fixture_id": 0,
            "tell_us": "Kitchen Sink",
        },
    },
]

SAMPLE_DEVICE_STATE = {
    "temperature": {"mean": 72.5},
    "pressure": {"mean": 55.3},
    "sov_status": {"v": 1},
    "flow": {"mean": 0.0},
}

SAMPLE_HOMES = [
    {
        "id": "home_001",
        "address": {"address1": "123 Main St"},
        "device_ids": ["28F53741CBBA"],
        "devices": [
            {
                "device_id": "28F53741CBBA",
                "product_code": "PP2",
                "name": "Phyn Plus",
            }
        ],
    }
]

SAMPLE_CONSUMPTION = {
    "water_consumption": 25.5,
    "water_usage_event_count": 12,
    "details": {
        "0": 0,
        "1": 0,
        "6": 1.2,
        "7": 3.5,
        "8": 2.1,
        "12": 1.8,
        "18": 5.4,
        "19": 3.2,
        "20": 4.1,
        "21": 2.5,
        "22": 1.7,
    },
    "average_consumption": 22.3,
    "comparison": {"percent_change": 14.3},
}

SAMPLE_FIRMWARE_INFO = {
    "fw_version": "3.2.1",
    "fw_img_name": "phyn_pp2_v3.2.1.bin",
    "product_code": "PP2",
}
