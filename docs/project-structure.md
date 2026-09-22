# Project Structure

This document describes the layout of the `aiophyn` repository, explaining the purpose of each directory and file.

## Directory Tree

```
aiophyn/
├── LICENSE                      # MIT license
├── pyproject.toml               # Project metadata, dependencies, build config
├── pytest.ini                   # Pytest configuration
├── README.md                    # Project overview & quick-start
│
├── aiophyn/                     # Core library package
│   ├── __init__.py              # Package exports: async_get_api, HomeInventory
│   ├── api.py                   # API class — auth, HTTP requests, main entry point
│   ├── const.py                 # Constants (API_BASE URL)
│   ├── device.py                # Device class — state, consumption, valve, events
│   ├── errors.py                # Error hierarchy (PhynError, RequestError, BrandError)
│   ├── home.py                  # Home class — home/device discovery
│   ├── home_inventory.py        # HomeInventory class — fixture types & inventory
│   ├── mqtt.py                  # MQTTClient — real-time WebSocket/MQTT streaming
│   │
│   └── utils/                   # Utility scripts
│       └── device_dump.py       # Interactive device state dump utility
│
├── docs/                        # Documentation (you are here)
│   ├── architecture.md          # Class structure & architecture
│   ├── project-structure.md     # This file — repository layout
│   ├── examples.md              # Guide to example scripts
│   ├── testing.md               # Test suite documentation
│   └── configuration.md         # Environment & configuration guide
│
├── examples/                    # Runnable example & validation scripts
│   ├── .env.example             # Template for credentials configuration
│   ├── diagnostics.py          # Shared bounded read-only runner & sanitized reports
│   ├── history.py              # Pure fixed-window history comparisons
│   ├── test_alerts.py          # Read-only alert diagnostics
│   ├── test_api.py              # Basic API connectivity test
│   ├── test_comprehensive.py    # Selected read-only endpoint diagnostics
│   ├── test_home_inventory.py   # Home inventory endpoint testing
│   ├── test_mqtt.py             # MQTT real-time streaming test
│   └── test_water_usage_events.py  # Water usage events & ML analysis
│
├── scripts/
│   ├── check_installed.py      # Isolated installed-package provenance & routing
│   └── verify_distribution.py  # Clean wheel/sdist/no-Git build and install gate
│
└── tests/                       # Offline by default; live checks explicitly gated
    ├── __init__.py
    ├── conftest.py              # Fixtures, mocks, and sample API response data
    ├── test_api.py              # API initialization & error hierarchy tests
    ├── test_device.py           # Device method tests (largest test file)
    ├── test_home.py             # Home discovery tests
    ├── test_home_inventory.py   # Home inventory endpoint tests
    ├── test_auth_contracts.py   # Real SRP calculations, mocked AWS I/O
    ├── test_transport_contracts.py # Loopback HTTP contracts
    ├── test_packaging.py        # Distribution-gate checks
    ├── test_usage_diagnostics.py # Synthetic predicted-usage accounting
    ├── test_history_diagnostics.py # Synthetic window comparisons
    ├── test_live_guards.py      # Offline opt-in, budget & privacy checks
    └── test_live_readonly.py    # Local opt-in only; deselected by default
```

## Key Directories

### `aiophyn/` — Core Library

The main Python package containing all library code. This is what gets installed when users `pip install` the library. It is organized by domain:

- **`api.py`** — The central `API` class and the `async_get_api()` factory function. Handles all authentication (AWS Cognito SRP) and HTTP request dispatching.
- **`device.py`** — All device-centric operations: reading sensor state, water consumption, valve control, away mode, auto-shutoff, health tests, firmware info, water usage events with ML fixture predictions, and event feedback submission.
- **`home.py`** — Account-level home and device discovery.
- **`home_inventory.py`** — Fixture type catalog and per-device fixture configuration.
- **`mqtt.py`** — Real-time event streaming via MQTT over WebSockets, including automatic reconnection with exponential backoff.
- **`utils/device_dump.py`** — A standalone utility script to quickly dump device state and away mode for debugging.

### `examples/` — Runnable Example Scripts

Explicitly invoked scripts can connect to the live Phyn API with locally
configured credentials. Imports are inert. Read-only diagnostics use process
variables or an explicitly named `--env-file`, bounded requests, and sanitized
reports. The separate legacy MQTT example uses `config.py` and logs private
data. Pure usage/history helpers are also tested offline.

See [examples.md](examples.md) for detailed documentation of each script.

### `tests/` — Automated Unit Tests

Default tests use mocks, synthetic data, and loopback HTTP servers; external
networking is blocked and no credentials are loaded. The optional
`live_readonly` check requires explicit selection and `--run-live`; it is never
enabled by ordinary pytest or CI. Historical shared samples establish response
shapes, not server completeness or revision guarantees.

See [testing.md](testing.md) for detailed documentation of each test file.

### `docs/` — Documentation

You are reading it. This directory contains developer-facing documentation for understanding, using, and contributing to the library.

## Key Files

### `pyproject.toml`

Project metadata and build configuration using Poetry:

- **Name:** `aiophyn`
- **Version:** `2026.9.1`
- **License:** MIT
- **Python:** `^3.9`
- **Key dependencies:** `pycognito`, `aiohttp`, `boto3`, `paho-mqtt`, `pysocks`, `pycryptodome`
- **Build backend:** `poetry.core.masonry.api`

### `pytest.ini`

Configures pytest:
- Test discovery path: `tests/`
- Import mode: `importlib` (avoids package path conflicts)
- Marker: `live_readonly` (deselected unless explicitly opted in)

### `LICENSE`

MIT License, copyright 2023 MizterB.
