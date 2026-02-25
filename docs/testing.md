# Test Suite

The `tests/` directory contains automated unit tests using [pytest](https://docs.pytest.org/). All tests run offline using mocked API responses — no network access or real credentials are needed.

## Running Tests

```bash
# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# Run a specific test file
pytest tests/test_device.py

# Run a specific test class
pytest tests/test_device.py::TestWaterUsageEvents

# Run a single test
pytest tests/test_device.py::TestWaterUsageEvents::test_basic_call

# Run with output visible
pytest -s
```

The `pytest.ini` at the repository root configures:
- **Test path:** `tests/`
- **Import mode:** `importlib` (avoids path conflicts with the nested `aiophyn/aiophyn/` structure)

### Dependencies

```bash
pip install pytest pytest-asyncio
```

Tests use `pytest-asyncio` for testing `async` methods. All async test methods are decorated with `@pytest.mark.asyncio`.

---

## Test Architecture

### Mocking Strategy

Tests use **dependency injection** to avoid real API calls. Each subsystem class (`Device`, `Home`, `HomeInventory`) accepts a request function in its constructor. In tests, an `AsyncMock` replaces the real HTTP request function:

```python
@pytest.fixture
def mock_request():
    return AsyncMock()

@pytest.fixture
def device(mock_request):
    return Device(mock_request)
```

This pattern lets tests configure return values per-test:

```python
async def test_get_state(self, device, mock_request):
    mock_request.return_value = SAMPLE_DEVICE_STATE
    result = await device.get_state("DEVICE123")
    assert result["sov_status"]["v"] == "Open"
```

### Sample Data

All mock API response data is defined in `conftest.py` as module-level constants. This data mirrors real Phyn API response structures, captured from actual API calls. Available sample datasets:

| Constant | Description |
|----------|-------------|
| `SAMPLE_FIXTURE_TYPES` | 16 fixture types (Toilet, Sink, Shower, etc.) |
| `SAMPLE_DEVICE_INVENTORY` | Device inventory with 12 fixture entries (9 configured, 3 unconfigured) |
| `SAMPLE_WATER_USAGE_EVENTS` | 4 water usage events with varying fixture predictions |
| `SAMPLE_DEVICE_STATE` | Full device state with sensors, valve, and configuration |
| `SAMPLE_DEVICE_STATE_2` | Second device state (different values, auto-shutoff disabled) |
| `SAMPLE_CONSUMPTION` | Water consumption with hourly breakdown (50 events, ~54 gallons) |
| `SAMPLE_CONSUMPTION_EMPTY` | Empty consumption response (idle device) |
| `SAMPLE_FIRMWARE_INFO` | Firmware version and upgrade timestamp |
| `SAMPLE_WATER_STATISTICS` | 2 days of daily water statistics |
| `SAMPLE_DEVICE_PREFERENCES` | Device preference list (away mode setting) |
| `SAMPLE_AWAY_MODE` | Away mode status response |
| `SAMPLE_HOMES` | Home with 2 devices at "123 Main St" |

---

## Test Files

### test_api.py

**What it validates:** API class initialization, brand handling, module exports, and error hierarchy.

**Test classes:**

#### `TestAPIInit` (6 tests)
Tests the `API` class constructor and its attributes. Uses `@pytest.fixture(autouse=True)` to mock `MQTTClient` so tests don't require a running event loop.

| Test | Validates |
|------|-----------|
| `test_phyn_brand` | Phyn brand sets `_brand = 0` and stores username |
| `test_kohler_brand` | Kohler brand sets `_brand = 1` |
| `test_invalid_brand_raises` | Invalid brand raises `BrandError` |
| `test_has_device_attribute` | `api.device` is a `Device` instance |
| `test_has_home_attribute` | `api.home` is a `Home` instance |
| `test_has_home_inventory_attribute` | `api.home_inventory` is a `HomeInventory` instance |
| `test_username_property` | `api.username` returns the email |

#### `TestErrors` (3 tests)
Validates the error class inheritance chain.

| Test | Validates |
|------|-----------|
| `test_request_error_is_phyn_error` | `RequestError` inherits from `PhynError` |
| `test_brand_error_is_exception` | `BrandError` inherits from `Exception` |
| `test_phyn_error_is_exception` | `PhynError` inherits from `Exception` |

#### `TestModuleExports` (2 tests)
Verifies that top-level imports work correctly.

| Test | Validates |
|------|-----------|
| `test_async_get_api_importable` | `from aiophyn import async_get_api` works |
| `test_home_inventory_importable` | `from aiophyn import HomeInventory` works |

---

### test_device.py

**What it validates:** All `Device` class methods — the most comprehensive test file with 38+ tests organized into 10 test classes.

#### `TestDeviceState` (3 tests)
| Test | Validates |
|------|-----------|
| `test_get_state` | Correct URL, response values (temperature, pressure, valve) |
| `test_get_state_has_real_api_fields` | All fields from real API present (sensors, status, config) |
| `test_get_state_second_device` | Second device has different values, extended SOV fields |

#### `TestConsumption` (4 tests)
| Test | Validates |
|------|-----------|
| `test_get_consumption_basic` | URL construction and water_consumption value |
| `test_get_consumption_has_real_api_fields` | Response structure: details, event count, averages |
| `test_get_consumption_empty_device` | Idle device returns zero consumption |
| `test_get_consumption_with_details` | Optional params (`details`, `event_count`, `comparison`) |
| `test_get_consumption_monthly` | Monthly duration format (`YYYY/MM`) |

#### `TestWaterUsageEvents` (8 tests)
| Test | Validates |
|------|-----------|
| `test_basic_call` | URL construction and millisecond timestamp params |
| `test_millisecond_timestamps` | Datetime → 13-digit millisecond conversion accuracy |
| `test_response_contains_fixture_data` | Fixture predictions, confidence scores, algorithms |
| `test_response_with_user_correction` | User-corrected fixture labels (`latest_user_feedback`) |
| `test_response_empty_user_feedback` | Uncorrected events have `{}`, not missing key |
| `test_response_user_feedback_prediction_algorithm` | `"user-feedback"` prediction algorithm handling |
| `test_response_has_real_api_structure` | All events have complete required field set |
| `test_empty_response` | Empty event list handled correctly |
| `test_params_are_strings` | Timestamp params are strings (API requirement) |

#### `TestWaterStatistics` (2 tests)
| Test | Validates |
|------|-----------|
| `test_get_water_statistics` | Correct URL and timestamp params |
| `test_water_statistics_has_real_api_structure` | Flow, pressure, temperature, metadata fields |

#### `TestWaterUsageEventFeedback` (2 tests)
| Test | Validates |
|------|-----------|
| `test_submit_feedback_basic` | Correct URL and payload with required fields |
| `test_submit_feedback_with_optional_fields` | Optional `sub_fixture_id` and `tell_us` fields |

#### `TestValveControl` (2 tests)
| Test | Validates |
|------|-----------|
| `test_open_valve` | Correct URL: `/devices/{id}/sov/Open` |
| `test_close_valve` | Correct URL: `/devices/{id}/sov/Close` |

#### `TestAwayMode` (3 tests)
| Test | Validates |
|------|-----------|
| `test_get_away_mode` | URL and response structure |
| `test_enable_away_mode` | POST with `value: "true"` |
| `test_disable_away_mode` | POST with `value: "false"` |

#### `TestFirmware` (3 tests)
| Test | Validates |
|------|-----------|
| `test_get_latest_firmware_info` | Response values (fw_version, device_id) |
| `test_firmware_info_has_real_api_fields` | All real API fields present with correct types |
| `test_firmware_info_as_list` | List response + `[0]` access pattern (HA compatibility) |

#### `TestDevicePreferences` (2 tests)
| Test | Validates |
|------|-----------|
| `test_get_device_preferences` | URL, response structure, preference values |
| `test_set_device_preferences` | POST with preference data payload |

#### `TestAutoShutoff` (3 tests)
| Test | Validates |
|------|-----------|
| `test_get_autoshutoff_status` | Correct endpoint URL |
| `test_set_autoshutoff_enabled` | Enable URL: `.../status/Enable` |
| `test_set_autoshutoff_disabled_with_time` | Disable with duration: `.../status/Disable/3600` |
| `test_set_autoshutoff_disabled_no_time` | Disable indefinitely: `.../status/Disable` |

#### `TestHealthTests` (4 tests)
| Test | Validates |
|------|-----------|
| `test_get_health_tests` | Correct URL with `list_type=grouped` |
| `test_run_leak_test_standard` | Standard test: `test_duration = "s"` |
| `test_run_leak_test_extended` | Extended test: `test_duration = "e"` |
| `test_run_leak_test_extended_string` | String `"true"` handling (HA compatibility) |
| `test_run_leak_test_standard_string` | String `"false"` handling |

---

### test_home.py

**What it validates:** The `Home` class and its `get_homes()` method.

#### `TestGetHomes` (5 tests)
| Test | Validates |
|------|-----------|
| `test_basic_call` | Correct URL and `user_id` param |
| `test_returns_home_list` | Response is a list of home dicts |
| `test_home_contains_multiple_devices` | Home has 2 devices with IDs and product codes |
| `test_home_contains_device_ids_list` | `device_ids` shortcut array is present |
| `test_home_contains_address` | Address information is present |
| `test_empty_homes` | Empty list response handled |

---

### test_home_inventory.py

**What it validates:** The `HomeInventory` class — fixture types, device inventory, and inventory updates.

#### `TestGetFixtureTypes` (6 tests)
| Test | Validates |
|------|-----------|
| `test_basic_call` | Correct URL for fixture types endpoint |
| `test_returns_list` | Response is a list with 16 entries |
| `test_fixture_type_structure` | Each entry has required fields with correct types |
| `test_known_fixture_types` | Well-known fixtures (Toilet, Sink, etc.) present |
| `test_fixture_categories` | All fixtures use category `"F"` |
| `test_empty_response` | Empty list handled |

#### `TestGetDeviceInventory` (7 tests)
| Test | Validates |
|------|-----------|
| `test_basic_call` | URL construction with device ID |
| `test_response_has_list_key` | Response contains `"list"` key |
| `test_configured_fixtures` | 9 fixtures with count > 0 identified |
| `test_unconfigured_fixtures` | 3 fixtures with count = 0 identified |
| `test_fixture_entry_structure` | Each entry has required fields |
| `test_sub_fixtures` | Sub-fixtures on Shower Only (name, active, id) |
| `test_different_device_ids` | URL changes per device ID |

#### `TestUpdateDeviceInventory` (5 tests)
| Test | Validates |
|------|-----------|
| `test_basic_call` | Correct URL and JSON payload |
| `test_uses_put_method` | Uses HTTP PUT (not POST) |
| `test_payload_format` | Payload is `{home_inventory_type_id, count}` |
| `test_zero_count` | Setting count to 0 works (removing a fixture) |
| `test_various_fixture_ids` | Multiple fixture type IDs handled correctly |

---

## conftest.py

The shared test configuration file that provides:

1. **Fixtures** (`mock_request`, `device`, `home`, `home_inventory`) — Injectable test dependencies
2. **Sample data constants** — Comprehensive API response mocks based on real Phyn API captures

The sample data is designed to cover realistic scenarios including:
- Multiple devices with varying states
- Active and idle devices
- Fixtures with and without sub-fixtures
- Water events with different prediction algorithms
- User-corrected and uncorrected events
- Configured and unconfigured fixture entries
