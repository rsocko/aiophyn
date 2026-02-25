# Architecture & Class Structure

This document describes the internal architecture of the `aiophyn` library, its class hierarchy, and how the components interact.

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Application                         │
│                  (e.g. Home Assistant, scripts)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    async_get_api()
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                          API                                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  ┌───────────┐ │
│  │  Home    │  │  Device  │  │HomeInventory  │  │   MQTT    │ │
│  │          │  │          │  │               │  │  Client   │ │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  └─────┬─────┘ │
│       │              │               │                 │       │
│       └──────────────┴───────────────┘                 │       │
│                      │                                 │       │
│              api._request()                    WebSocket/MQTT  │
│                      │                                 │       │
└──────────────────────┼─────────────────────────────────┼───────┘
                       │                                 │
                       ▼                                 ▼
              Phyn REST API                    Phyn MQTT Broker
           (api.phyn.com)                   (WebSocket over TLS)
```

## Core Classes

### `API` — [aiophyn/api.py](../aiophyn/api.py)

The central class that manages authentication and holds references to all subsystem handlers.

**Responsibilities:**
- AWS Cognito authentication via SRP (Secure Remote Password)
- Token management (access token, ID token, refresh token, expiration tracking)
- HTTP request dispatching with automatic token refresh
- Proxy & SSL configuration

**Key attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `home` | `Home` | Home discovery operations |
| `device` | `Device` | Device state, control, and data retrieval |
| `home_inventory` | `HomeInventory` | Fixture type catalog and per-device inventory |
| `mqtt` | `MQTTClient` | Real-time device updates via MQTT |
| `username` | `str` (property) | The authenticated user's email |

**Authentication flow:**

1. For **Phyn** brand: Direct AWS Cognito SRP authentication
2. For **Kohler** brand: B2C login → Kohler token → Phyn token exchange → Cognito authentication

The private `_request()` method handles all HTTP calls, automatically refreshing expired tokens before making requests.

---

### `Home` — [aiophyn/home.py](../aiophyn/home.py)

Handles home/account discovery.

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `get_homes(user_id)` | Retrieve all homes and associated devices for a user | `list[dict]` — each with `id`, `address`, `device_ids`, `devices` |

---

### `Device` — [aiophyn/device.py](../aiophyn/device.py)

Handles all device-level operations — the largest class in the library.

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `get_state(device_id)` | Current device state (sensors, valve, online status) | `dict` |
| `get_consumption(device_id, duration, ...)` | Water consumption for a day/month/year | `dict` |
| `get_water_statistics(device_id, from_ts, to_ts)` | Daily statistics (flow, pressure, temperature) | `list[dict]` |
| `get_water_usage_events(device_id, from_dt, to_dt)` | Individual water usage events with ML fixture predictions | `list[dict]` |
| `submit_water_usage_event_feedback(event_id, fixture_id, ...)` | Submit fixture correction feedback | `dict` |
| `open_valve(device_id)` | Open the shutoff valve | `dict` |
| `close_valve(device_id)` | Close the shutoff valve | `dict` |
| `get_away_mode(device_id)` | Get away mode status | `dict` |
| `enable_away_mode(device_id)` | Enable away mode | `None` |
| `disable_away_mode(device_id)` | Disable away mode | `None` |
| `get_autoshutoff_status(device_id)` | Get auto shutoff configuration | `dict` |
| `set_autoshutoff_enabled(device_id, shutoff_on, time)` | Enable/disable auto shutoff | `dict` |
| `get_device_preferences(device_id)` | Get all device preferences | `list[dict]` |
| `set_device_preferences(device_id, data)` | Set device preferences | `None` |
| `get_health_tests(device_id)` | Get health/leak test history | `dict` |
| `run_leak_test(device_id, extended_test)` | Run a standard or extended leak test | `dict` |
| `get_latest_firmware_info(device_id)` | Get firmware version information | `list[dict]` |

> **Note:** `get_autoshuftoff_status` exists as a backward-compatible alias (preserving the original typo) for `get_autoshutoff_status`.

---

### `HomeInventory` — [aiophyn/home_inventory.py](../aiophyn/home_inventory.py)

Handles fixture type catalog and per-device fixture inventory management.

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `get_fixture_types()` | Master catalog of all fixture types (Toilet, Sink, etc.) | `list[dict]` |
| `get_device_inventory(device_id)` | User-configured fixtures for a device (with counts) | `dict` with `list` key |
| `update_device_inventory(device_id, fixture_type_id, count)` | Update fixture count for a device | `dict` |

---

### `MQTTClient` — [aiophyn/mqtt.py](../aiophyn/mqtt.py)

Real-time event streaming via MQTT over WebSockets.

**Responsibilities:**
- WebSocket connection management with automatic reconnection
- Topic subscription (per-device update streams)
- Event handler registration for connect/disconnect/update events
- Exponential backoff for reconnection attempts

**Key methods:**

| Method | Description |
|--------|-------------|
| `connect()` | Establish MQTT connection |
| `disconnect()` | Initiate disconnection |
| `disconnect_and_wait()` | Disconnect and wait for completion |
| `subscribe(topic)` | Subscribe to an MQTT topic |
| `add_event_handler(type, target)` | Register a handler for `"connect"`, `"disconnect"`, or `"update"` events |
| `is_connected()` | Check connection status |

**Supporting classes:**
- `AIOHelper` — Bridges `paho-mqtt` synchronous socket I/O with asyncio event loops
- `Timer` — Runs a callback after a configurable delay, used for reconnection scheduling

---

### `KOHLER_API` — [aiophyn/partners/kohler.py](../aiophyn/partners/kohler.py)

Partner authentication for Kohler H2Wise+ devices that use Phyn hardware.

**Flow:**
1. B2C login to Kohler's Azure AD B2C identity provider
2. Exchange Kohler token for Phyn partner token
3. Decrypt Phyn password from encrypted token using AES-CBC
4. Return Cognito credentials and MQTT settings for standard Phyn authentication

This class is used internally by `API` when `phyn_brand="kohler"` and is not typically accessed directly.

---

## Error Hierarchy

Defined in [aiophyn/errors.py](../aiophyn/errors.py):

```
Exception
├── PhynError          # Base error for all Phyn-related errors
│   └── RequestError   # HTTP request failures
└── BrandError         # Invalid brand specified during initialization
```

---

## Constants

Defined in [aiophyn/const.py](../aiophyn/const.py):

| Constant | Value | Description |
|----------|-------|-------------|
| `API_BASE` | `https://api.phyn.com` | Base URL for all REST API calls |

Additional constants in [aiophyn/api.py](../aiophyn/api.py) include default HTTP headers, AWS Cognito pool configuration, and API keys.

---

## Package Exports

The top-level `aiophyn` package ([\_\_init\_\_.py](../aiophyn/__init__.py)) exports:

- `async_get_api` — Factory function to create an authenticated `API` instance
- `HomeInventory` — The home inventory class (for type-hinting convenience)

The root-level [\_\_init\_\_.py](../__init__.py) re-exports these and registers submodule aliases so that `from aiophyn.device import Device` works regardless of the nested package layout.

---

## Design Patterns

### Dependency Injection for HTTP Requests

The `Home`, `Device`, and `HomeInventory` classes all receive the `API._request` method as a constructor argument rather than holding a reference to the `API` object itself. This:
- Keeps subsystem classes decoupled from `API` internals
- Makes unit testing straightforward (inject an `AsyncMock` as the request function)
- Allows each class to focus solely on URL construction and response handling

### Factory Function

`async_get_api()` is the primary entry point. It creates an `API` instance and calls `async_authenticate()` before returning, ensuring the caller always gets a ready-to-use, authenticated client.

### Async-First Design

All I/O operations are `async`. Synchronous AWS Cognito authentication is wrapped with `asyncio.wrap_future()` to avoid blocking the event loop.
