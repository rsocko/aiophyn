# Project Structure

This document describes the layout of the `aiophyn` repository, explaining the purpose of each directory and file.

## Directory Tree

```
aiophyn/
├── __init__.py                  # Root package init — re-exports & submodule aliasing
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
│   ├── partners/                # Partner brand integrations
│   │   ├── __init__.py          # Exports KOHLER_API
│   │   └── kohler.py            # Kohler H2Wise+ authentication bridge
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
│   ├── test_api.py              # Basic API connectivity test
│   ├── test_comprehensive.py    # Full API surface validation
│   ├── test_home_inventory.py   # Home inventory endpoint testing
│   ├── test_mqtt.py             # MQTT real-time streaming test
│   └── test_water_usage_events.py  # Water usage events & ML analysis
│
└── tests/                       # Automated unit tests (pytest)
    ├── __init__.py
    ├── conftest.py              # Fixtures, mocks, and sample API response data
    ├── test_api.py              # API initialization & error hierarchy tests
    ├── test_device.py           # Device method tests (largest test file)
    ├── test_home.py             # Home discovery tests
    └── test_home_inventory.py   # Home inventory endpoint tests
```

## Key Directories

### `aiophyn/` — Core Library

The main Python package containing all library code. This is what gets installed when users `pip install` the library. It is organized by domain:

- **`api.py`** — The central `API` class and the `async_get_api()` factory function. Handles all authentication (AWS Cognito SRP) and HTTP request dispatching.
- **`device.py`** — All device-centric operations: reading sensor state, water consumption, valve control, away mode, auto-shutoff, health tests, firmware info, water usage events with ML fixture predictions, and event feedback submission.
- **`home.py`** — Account-level home and device discovery.
- **`home_inventory.py`** — Fixture type catalog and per-device fixture configuration.
- **`mqtt.py`** — Real-time event streaming via MQTT over WebSockets, including automatic reconnection with exponential backoff.
- **`partners/kohler.py`** — Kohler H2Wise+ authentication, translating Kohler's Azure AD B2C credentials into Phyn API access.
- **`utils/device_dump.py`** — A standalone utility script to quickly dump device state and away mode for debugging.

### `examples/` — Runnable Example Scripts

Integration test scripts that connect to the live Phyn API. These require real credentials (configured via `.env` file) and exercise the library against the production API. They are not automated tests — they are developer tools for validation and exploration.

See [examples.md](examples.md) for detailed documentation of each script.

### `tests/` — Automated Unit Tests

Pytest-based unit tests that validate library behavior using mocked API responses. These do **not** require network access or real credentials. All API responses are simulated using sample data defined in `conftest.py`, which mirrors real Phyn API response structures.

See [testing.md](testing.md) for detailed documentation of each test file.

### `docs/` — Documentation

You are reading it. This directory contains developer-facing documentation for understanding, using, and contributing to the library.

## Key Files

### `pyproject.toml`

Project metadata and build configuration using Poetry:

- **Name:** `aiophyn`
- **Version:** `2026.2.1`
- **License:** MIT
- **Python:** `^3.9`
- **Key dependencies:** `pycognito`, `aiohttp`, `boto3`, `paho-mqtt`, `pysocks`, `pycryptodome`
- **Build backend:** `poetry.core.masonry.api`

### `pytest.ini`

Configures pytest:
- Test discovery path: `tests/`
- Import mode: `importlib` (avoids package path conflicts)

### `LICENSE`

MIT License, copyright 2023 MizterB.
