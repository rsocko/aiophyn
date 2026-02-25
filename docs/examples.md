# Example Scripts

The `examples/` directory contains runnable scripts that exercise the `aiophyn` library against the live Phyn API. These are developer tools for validation, debugging, and exploring API capabilities — not automated tests.

> **Important:** All example scripts require real Phyn (or Kohler) credentials. See [configuration.md](configuration.md) for `.env` setup instructions.

## Common Patterns

All example scripts share these patterns:

1. **Credential loading** — Reads `PHYN_USERNAME`, `PHYN_PASSWORD`, `PHYN_BRAND`, and optionally `PHYN_DEVICE_ID` from a `.env` file via `python-dotenv`
2. **Output capture** — Saves all API responses to `examples/output/<script>_<timestamp>.json` for offline analysis
3. **Error handling** — Catches `PhynError` exceptions and logs them
4. **Path bootstrapping** — Adds the repository root to `sys.path` so the local `aiophyn` package is importable without installation

## Prerequisites

```bash
# Install the library and example dependencies
pip install -e .
pip install python-dotenv

# Configure credentials
cp examples/.env.example examples/.env
# Edit examples/.env with your credentials
```

---

## test_api.py

**Purpose:** Quick connectivity and basic API validation. The simplest starting point for verifying your credentials work.

**What it does:**
1. Authenticates with the Phyn API
2. Discovers all homes and devices for the user
3. Gets the device state (sensors, valve status) for the first device found
4. Gets today's water consumption with detailed hourly breakdown
5. Reads the current valve status from the device state

**Parameters (from `.env`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `PHYN_USERNAME` | Yes | Your Phyn account email |
| `PHYN_PASSWORD` | Yes | Your Phyn account password |
| `PHYN_BRAND` | No | `"phyn"` (default) or `"kohler"` |

**Output:** `examples/output/test_api_<timestamp>.json`

Contains captured responses for `get_homes`, `get_state`, `get_consumption`, and `valve_status`.

**Commented-out features:** Lines for `close_valve()` and `open_valve()` are included but commented out. Uncomment them to test valve control (use caution — this controls real hardware).

**How to run:**
```bash
cd examples
python test_api.py
```

---

## test_comprehensive.py

**Purpose:** Exercises the full API surface in a single run, producing a pass/fail report for each endpoint.

**What it does:**
1. **Authentication** — Verifies login
2. **Home Discovery** — Lists homes, addresses, and devices
3. **Device State** — Reads temperature, pressure, and valve status
4. **Water Consumption** — Today's consumption with details and event count
5. **Water Usage Events** — Last 7 days of events with fixture prediction metadata
6. **Fixture Types** — Master catalog of fixture types (Home Inventory)
7. **Device Inventory** — User-configured fixture counts per device
8. **Device Preferences** — All device configuration preferences
9. **Firmware Info** — Current firmware version and upgrade timestamp
10. **Away Mode** — Away mode status

**Parameters (from `.env`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `PHYN_USERNAME` | Yes | Your Phyn account email |
| `PHYN_PASSWORD` | Yes | Your Phyn account password |
| `PHYN_BRAND` | No | `"phyn"` (default) or `"kohler"` |
| `PHYN_DEVICE_ID` | No | Override auto-discovered device ID |

**Output:** `examples/output/test_comprehensive_<timestamp>.json`

Contains all captured API responses plus a `results` summary with pass/fail counts.

**Console output example:**
```
======================================================================
  TEST SUMMARY
======================================================================
  Total:  10
  Passed: 10
  Failed: 0

  [PASS] Authentication
  [PASS] get_homes
  [PASS] get_state
  ...
```

**How to run:**
```bash
cd examples
python test_comprehensive.py
```

---

## test_home_inventory.py

**Purpose:** Focused validation of the Home Inventory endpoints — fixture types and per-device fixture configuration.

**What it does:**
1. **Test 1: Fixture Types** — Retrieves the master catalog of all fixture types Phyn recognizes (Toilet, Sink, Shower, etc.) with their IDs, names, and icon URLs
2. **Test 2: Device Inventory** — For each discovered device, retrieves the user's configured fixtures with counts (e.g., "5 Toilets, 9 Sinks"), distinguishing configured vs. unconfigured fixtures
3. **Test 3: Cross-Reference** — Compares the master fixture catalog against each device's inventory to show which types are configured and their counts

**Parameters (from `.env`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `PHYN_USERNAME` | Yes | Your Phyn account email |
| `PHYN_PASSWORD` | Yes | Your Phyn account password |
| `PHYN_BRAND` | No | `"phyn"` (default) or `"kohler"` |
| `PHYN_DEVICE_ID` | No | Override auto-discovered device ID |

**Output:** `examples/output/test_home_inventory_<timestamp>.json`

Contains fixture types, per-device inventory, and cross-reference data.

**How to run:**
```bash
cd examples
python test_home_inventory.py
```

---

## test_mqtt.py

**Purpose:** Tests real-time MQTT streaming — subscribes to device update topics and captures live messages.

**What it does:**
1. Authenticates and discovers devices
2. Connects to the Phyn MQTT broker over WebSockets
3. Subscribes to update topics for Phyn Plus devices (`PP1`/`PP2`)
4. Listens for 10 seconds, logging received messages
5. Disconnects cleanly and saves captured messages

**Parameters (from `.env`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `PHYN_USERNAME` | Yes | Your Phyn account email |
| `PHYN_PASSWORD` | Yes | Your Phyn account password |
| `PHYN_BRAND` | No | `"phyn"` (default) or `"kohler"` |

**Output:** `examples/output/test_mqtt_<timestamp>.json`

Contains captured MQTT messages in the `messages` array, plus home/device discovery responses.

**Platform notes:**
- On Windows, the script sets `WindowsSelectorEventLoopPolicy` to enable `add_reader` support required by the MQTT client
- If the event loop doesn't support `add_reader` (e.g., some Windows Python builds), the script exits with a descriptive error

**How to run:**
```bash
cd examples
python test_mqtt.py
```

---

## test_water_usage_events.py

**Purpose:** The most advanced example — fetches water usage events and performs ML classification quality analysis on the fixture predictions.

**What it does:**
1. Authenticates and discovers devices
2. For each device and each configured time range:
   - Fetches water usage events via `get_water_usage_events()`
   - Aggregates usage by fixture type (gallons, event count, average confidence)
   - Analyzes prediction quality: low-confidence events, ambiguous top-2 classifications, user feedback presence
   - Reports classification algorithm distribution (clustering, heuristics, user-feedback, etc.)
   - Lists review candidate events sorted by confidence

**Parameters (from `.env`):**

| Variable | Required | Description |
|----------|----------|-------------|
| `PHYN_USERNAME` | Yes | Your Phyn account email |
| `PHYN_PASSWORD` | Yes | Your Phyn account password |
| `PHYN_BRAND` | No | `"phyn"` (default) or `"kohler"` |
| `PHYN_DEVICE_ID` | No | Override auto-discovered device ID |

**CLI arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--device-id` | env/auto | Override device ID |
| `--days` | `1,7,30` | Comma-separated day ranges to analyze |
| `--low-confidence-threshold` | `0.70` | Flag predictions below this confidence |
| `--ambiguity-gap-threshold` | `0.15` | Flag when top-2 confidence gap is below this |
| `--max-review-events` | `10` | Max review candidates to display per range |

**Output:** `examples/output/test_water_usage_events_<timestamp>.json`

Contains all events per device per time range, with full fixture prediction data.

**Console output example:**
```
  Usage by fixture (Last 7 days):
  Fixture                      Gallons   Events   Avg Conf
  ------------------------- ---------- -------- ----------
  Shower Only                  105.23g      14      91.2%
  Toilet                        38.50g      45      82.5%
  Sink                          12.30g      32      75.8%
  Dishwasher                     8.10g       3      45.2%

  Classification quality (Last 7 days):
    Low confidence (<70%): 12/94
    Ambiguous top-2 (gap < 0.15): 5/94
    Events with user feedback: 3/94
```

**How to run:**
```bash
cd examples
python test_water_usage_events.py
python test_water_usage_events.py --days 1,7 --low-confidence-threshold 0.5
```

---

## Output Directory

All scripts save output to `examples/output/`. This directory is created automatically on first run. Output files are timestamped JSON files containing the raw API responses, making them useful for:

- Offline analysis and debugging
- Comparing API responses over time
- Understanding API response structures before writing new code
- Sharing API data without sharing credentials
