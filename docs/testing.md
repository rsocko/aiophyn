# Test Suite

The default `tests/` suite runs offline with mocks and loopback HTTP servers.
No credentials are needed. Local live checks are marked and **deselected by
default**, including when CI runs `python -m pytest tests` and even if process
credentials happen to exist. Default collection does not load environment files.

## Running Tests

```bash
# Run all offline tests
python -m pytest

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
- **Marker:** `live_readonly`, enabled only by explicit `--run-live` and selection

`tests/conftest.py` blocks external DNS and IPv4/IPv6 socket connections during
collection and offline tests, including accidental Phyn or AWS login attempts.
Loopback remains available to the real HTTP transport contract tests. Only the
explicitly selected live fixture temporarily permits external networking; merely
passing `--run-live` does not unguard unmarked tests. This is a regression guard,
not an operating-system sandbox: independently launched subprocesses or other
transport implementations need their own protection. Child pytest invocations
load the same guard.

### Private pytest temporary directories

The suite retains pytest 8 for Python 3.9 support. To mitigate
[CVE-2025-71176](https://github.com/advisories/GHSA-6w46-j5rx-g56g), initial test
configuration creates a fresh private directory with Python's
`TemporaryDirectory` (mode 0700 on Unix) and directs pytest's predictable
temporary paths inside it through `PYTEST_DEBUG_TEMPROOT`. This applies to
ordinary commands, child pytest invocations, and both CI workflows.
Caller-supplied `--basetemp` is rejected rather than bypassing this protection.
The directory is cleaned and the previous environment restored at shutdown,
including configuration failures; pytest's usual cross-run temporary-file
retention is intentionally disabled. Explicitly saved reports are unaffected.
This mitigates this suite's usage; it does not patch pytest globally or make
the inherited dependency inventory vulnerability-free.

## Local opt-in read-only checks

```powershell
# Offline, noninteractive, no secret-file loading:
python -m pytest
python -m pytest tests

# Only after the account owner explicitly requests a local live run:
python -m pytest -m live_readonly --run-live --env-file .env.live -s
```

See [configuration](configuration.md) for process variables and optional
python-dotenv installation. `--env-file` without `--run-live` is an error.
An explicit live selection with absent credentials, a missing file/dependency,
or placeholder values fails instead of reporting a green skip. `--run-live`
without selected live tests is also an error. There is no interactive credential
prompt or automatic credential discovery.

The one local test authenticates, discovers devices, checks fixture catalog and
inventory shapes, and checks event IDs, timestamps, numeric fields and
prediction containers. One selected device is used (the first discovered device
unless explicitly configured). There are no inventory/feedback mutations,
valve commands, leak tests, merges, deletes or Home Assistant statistics changes.
`--run-live` never enables writes. `--run-live-writes` is an unsupported stub
that **errors**; mutation approval and a restoration policy would need a
separate design. Feedback, merge and deletion operations are not claimed to be
reversible.

The harness uses the same sanitized diagnostic runner as the examples:

| Limit | Enforcement |
|-------|-------------|
| Shared request-attempt cap | 24 combined Cognito authentication and Phyn REST send attempts per run |
| Counters | Separate `cognito`, `phyn_rest`, `total`, and `cap` in the report |
| Pacing/concurrency | At least 0.25 seconds between send reservations; operations are sequential |
| REST timeout | 15 seconds per aiohttp request |
| Cognito timeout | 5 seconds connect and 5 seconds read; SDK retries disabled |
| Operation/run timeout | 25 seconds per operation; 180 seconds for the run |
| Redirects/writes | Unexpected REST redirects rejected before follow-up; non-GET REST calls rejected before sending |

Cognito's SDK `before-send` hook and aiohttp's per-send
`on_request_headers_sent` hook count disjoint transports. The latter also
covers aiohttp stale-connection retries, unlike a logical request-start hook.
Attempts reserved before a failed connection/send are **not** a measurement
of responses received. Authentication normally consumes multiple requests;
the 24 cap does not mean 24 Phyn reads. The existing runtime's bounded 401/403
reauthentication remains possible and consumes the same budget.
There is no additional automatic history or rate-limit retry. A 429 aborts the
run; it is not retried in violation of `Retry-After`. Wait for the service's
retry interval before a separately requested retry.

Cancelling an async task cannot terminate an already-running Cognito thread.
SDK timeouts bound its in-flight I/O, and closing the shared budget prevents
further sends. This is not a hard OS process-kill deadline. No transport code or
public runtime API was changed to add these example-only bounds.

Optional `--live-report .artifacts\readonly.json` writes a **new** sanitized
report, refusing overwrite. Reports distinguish `passed`, `failed`, `empty` and
`skipped`; no devices means incomplete, not success. Authentication failure is
counted as failed, and dependent work is skipped. No raw payload, household
identifier, address, token, password or exception chain is printed or saved.
Treat aggregate household activity as private too. Do not enable SDK debug logs
or upload raw pytest tracebacks/captures when investigating a real account.

## History characterization

```powershell
python -m pytest -m live_readonly --run-live --env-file .env.live --history --history-start 2025-01-01 --live-report .artifacts\history.json -s
```

`PHYN_DEVICE_ID` (or `--device-id`) is required for history; it must belong to a
discovered device. The optional start date chooses **one completed seven-day
UTC interval**. Without it, the interval ends at the latest UTC midnight.
The operator may choose a small known-active older interval. A future or
unfinished week is rejected before authentication.

Nine additional read calls compare the same weekly interval, seven consecutive
daily windows, then that identical weekly interval again. No paging parameters
are guessed. Reports inspect the known event metadata fields actually returned;
a list response does not establish whether a service-side limit or hidden
pagination exists.

Comparison is by event ID and relevant values (open/close timestamps, volume,
predictions and feedback), with counts rather than raw IDs in the report.
Events are assigned by start timestamp to half-open `[start,end)` windows.
Boundary duplicates and events crossing midnight are tracked; full volumes
belong to the start day, not prorated across days. Out-of-window items are
reported, not silently double-counted. Identical duplicates within a response
are deduplicated and counted; conflicting duplicates fail explicitly.
An ID whose corrected start timestamp assigns it to multiple daily windows
also fails instead of silently overwriting a value. Per-snapshot gallon totals
are reported alongside ID-set and changed-value counts.
All seven daily responses must succeed. A failed/partial read never becomes
an empty successful window.

The first/last weekly snapshots distinguish possible late-arriving events,
removed events and changed/corrected values from stable daily/weekly differences.
These are **observations, not causal proof**: the API does not promise snapshot
isolation while sequential requests execute. `consistent=false` is a measured
comparison result, not a failed transport test. Empty history remains explicitly
empty, and **absence is not proof of retention policy**. Retention and pagination
remain unknown; physical fixture classification accuracy is not measured.
The harness neither backfills nor deletes/imports Home Assistant statistics.

### Offline coverage of the harness

For the later bounded inventory/event join assessment and its synthetic tests,
see [sub-fixture evidence](subfixture-evidence.md). It distinguishes named
inventory availability from individual usage attribution without changing
runtime statistics.

`test_usage_diagnostics.py`, `test_history_diagnostics.py` and
`test_live_guards.py` use new, entirely synthetic fixtures (no private captures).
They cover the 2+3=5 regression, null/missing predictions, zero versus empty,
invalid numeric/confidence fields, strict threshold equality, feedback conflicts,
fixed UTC boundaries, missing/duplicate/changed history, partial failure,
request caps/pacing, redirects/write prohibition, import safety, opt-in failures
and redacted reports. Ignore tests use `git check-ignore` for representative
root/nested private paths and `git ls-files` to catch already tracked secrets
by path; this is not a content-secret scanner.

`tests/fixtures/attribution_cases.json` supplies synthetic conformance vectors
for user-first category attribution, independent of a runtime library API.
Coverage includes ID-only and orphan user choices, normalized/zero IDs,
comment/subfixture-only feedback, unsorted model scores, exact ties and reorder
sensitivity, malformed fields, explicit model-metadata warnings under a valid
human choice, label conflicts, and catalog reuse without additional reads.
Bucket totals conserve full event volume; user choices do not inherit model
confidence. Raw event objects remain unchanged and private labels stay redacted.

Multi-device regressions in `test_usage_diagnostics.py` explicitly select the
second synthetic device in both same-home and separate-home accounts, covering
comprehensive reads, fixed history windows and the selected home's alerts.
Active alert summaries remain account-wide. Tests preserve default-first
selection, reject unknown selections before device reads, and keep per-device
usage/history reports separate even when event IDs overlap or one device returns
empty data or fails. `test_transport_contracts.py` exercises the real HTTP
transport against loopback with alternating and overlapping concurrent inventory,
event and state reads through one API object, checking exact paths, queries and
distinct responses. This is offline routing/report isolation evidence, not
physical multi-device validation, a cross-device history ledger, or a claim about
server caching. No automatic all-device live loop or request-budget increase is
introduced.

The older shared samples below document historical response structures, not a
fresh live contract proof. The inventory POST envelope follows the historical
experiment evidence pinned by the remediation work; no live write was attempted
to re-establish it.

### Bounded live observations (2026-09-23 UTC)

After explicit account-owner approval, two devices were checked sequentially
with separate private local reports. Each run completed 13 checks with no
failed, empty, or skipped checks: authentication, discovery, fixture catalog,
device inventory, 1/7/30-day usage events, state, consumption, preferences,
firmware, away-mode status, and the nine-read history comparison.
Each used 22 send attempts (two Cognito plus 20 REST), below the 24-attempt cap.
The fixed completed week's weekly/daily/repeated-week snapshots were consistent
for both devices in these runs.

An initial run exposed an unsupported diagnostic assumption: predictions need
not be sorted by confidence. The initial fix preserved first-returned attribution
and flagged unordered confidence for review; both live runs then passed.
That attribution policy was subsequently superseded by explicit user choice,
then highest-confidence model selection. The initial live observations do not
by themselves validate that newer policy; its synthetic contract is described
above.
No raw account/device identifiers, labels, credentials, or event captures were
committed. No inventory/feedback writes, valve operations, or HA mutations ran.

The updated attribution policy was checked again on both devices at 01:12 UTC:
each completed the same 13 checks with no failed, empty, or skipped checks,
22 send attempts, and consistent history comparisons. The new report label,
source-count totals, event counts, and conservation of fixture-bucket volume
were verified across all six device/window summaries. These windows contained
model-attributed events but no explicit user-attributed events and no invalid
model metadata. User-override precedence is therefore synthetic test evidence,
not a live feedback-write round trip. The corresponding offline suite passed
342 tests with the opt-in live test deselected.

These observations establish only the checked account, devices, intervals, and
response shapes at that time. They do not establish all API behavior, retention,
pagination/completeness guarantees, revision ordering, or physical fixture
classification accuracy. Alert endpoints and MQTT streaming were not part of
these live runs.

### Dependencies

Install Poetry 2.2.1 separately, select your Python interpreter with
`poetry env use`, then install the locked development group:

```bash
poetry check --lock
poetry sync --with dev
poetry run python -m pytest tests
```

Prefix the test commands above with `poetry run` when using this environment.
The development group declares pytest 8.x and pytest-asyncio 1.2.x, which retain
Python 3.9 support, plus `build`, `twine`, and conditional `tomli` for packaging
checks. Tests use `pytest-asyncio` for testing `async` methods.

The original lock dated back to 2022 and omitted runtime dependencies already
declared in the manifest. It was migrated with Poetry 2.2.1, retaining unrelated
pins. Python 3.14 requires newer native-extension packages (`aiohttp`,
`frozenlist`, `multidict`, `yarl`, and `cffi`).
Their required transitive changes and the new development tools are locked too.
The unused Black development dependency was subsequently removed to eliminate
the feature-introduced vulnerable formatter version
([CVE-2026-32274](https://github.com/advisories/GHSA-3936-cmfr-pm3m)).
Only its now-unreachable dependencies were pruned; retained package versions
and artifact hashes were unchanged. Formatting is not a required CI step.
`pycognito` now requires `>=2024.5.1,<2025.0.0`, matching the version required by
Home Assistant 2026.9.3 through `hass-nabucasa`; its declared Python minimum is
3.8, so aiophyn retains 3.9. The lock is not a dependency-security audit.

## CI and Distribution Verification

`.github/workflows/smoke-test.yml` runs the offline unit/contract suite and
packaging checks on Python 3.9, 3.12, and 3.14. It triggers on all pull requests,
manual dispatch, and pushes to `main`, `feature/**`, `work/**`, `validation/**`,
and `rsocko-*`.
The tests use mocks or a loopback HTTP server, never Phyn credentials or devices.
Dependency installation requires access to the package index; test/probe
execution does not contact Phyn.
Build and install steps respect the machine's configured pip package index;
they do not disable TLS verification or force direct access to public PyPI.

Run the same packaging checks locally:

```bash
poetry run python -m pip check
poetry run python scripts/verify_distribution.py
# Optionally keep only the verified wheel and sdist in an empty directory:
poetry run python scripts/verify_distribution.py --output-dir dist
```

The helper checks `pyproject.toml` against `aiophyn.__version__` without importing
the checkout, builds both distributions, and runs `twine check --strict`.
It extracts the sdist into a temporary directory outside the checkout and
rebuilds both artifacts with no Git metadata. Separate clean virtual environments
install the original wheel and sdist with their declared runtime dependencies,
run `pip check`, and execute the copied probe using Python isolated mode (`-I`).
The probe verifies that imports come from that environment's installed
distribution, not the checkout, and compares installed metadata and module
versions. It imports supported API/dependency modules and invokes real catalog,
inventory read/update, usage-event, feedback, and legacy `get_autoshuftoff_status`
methods through an injected mock transport, asserting request routing, timestamp
parameters, the POST inventory envelope, and feedback ID-token selection.
It does not authenticate, create an MQTT connection, or access a real device.

The PyPI release workflow uses the same helper and offline tests before
uploading verified artifacts, but its publish job is restricted to stable
releases in `jordanruthe/aiophyn`. Fork releases and prereleases cannot run that
job. The gate must be present in the tagged source before a GitHub release is
published; GitHub's `release: published` event also includes prereleases.

The fork's `2026.9.2.dev1` candidate uses a uniquely versioned GitHub prerelease,
not PyPI. Publish only the verified wheel, sdist, and a `SHA256SUMS` file after
the exact commit passes the Python matrix. Use an unused tag and asset names;
never replace an existing release artifact. Enable release immutability when
available, and require consumers to pin the wheel URL plus SHA256 regardless.
Verify downloaded public assets against the locally validated bytes.
Running the build helper itself never publishes anything. Publication, a
Home Assistant installation, and live device actions remain separate decisions.

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

Shared historical response-shape samples are defined in `conftest.py` as
module-level constants, with sanitized identifiers. Contract and diagnostic
tests also construct independent synthetic cases. These examples are not raw
response captures or evidence of correction lifecycle/completeness guarantees.
Available shared sample datasets:

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

#### `TestAPIInit` (7 tests)
Tests the `API` class constructor and its attributes. Uses `@pytest.fixture(autouse=True)` to mock `MQTTClient` so tests don't require a running event loop.

| Test | Validates |
|------|-----------|
| `test_phyn_brand` | Deprecated Phyn brand argument is accepted and username is stored |
| `test_kohler_brand` | Deprecated Kohler brand argument is accepted without an alternate auth path |
| `test_invalid_brand_accepted` | Unknown brand is accepted because the argument is ignored |
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

#### `TestModuleExports` (5 cases)
Verifies that top-level imports work correctly.

| Test | Validates |
|------|-----------|
| `test_async_get_api_importable` | `from aiophyn import async_get_api` works |
| `test_home_inventory_importable` | `from aiophyn import HomeInventory` works |
| `test_mqtt_annotations_are_postponed_for_python39` | MQTT callback union annotations are deferred |
| `test_subscribe_callback_preserves_ack_handling` | Tuple/list callback values still acknowledge subscriptions |

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
| `test_get_autoshuftoff_status` | Upstream method name, endpoint URL, and response |
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
| `test_uses_post_method` | Uses the historical POST inventory contract |
| `test_payload_format` | Payload is `{"list": [{"home_inventory_type_id": ..., "count": ...}]}` |
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
