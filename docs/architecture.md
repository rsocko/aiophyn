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

Authentication uses AWS Cognito refresh-token auth when available, falling back
to SRP login. The legacy `phyn_brand` argument is accepted but ignored; there is
no separate Kohler authentication flow.

The private `_request()` method handles all HTTP calls, refreshing expired tokens
before requests. A 401 or 403 triggers at most one reauthentication and replay
with the same method, body, and token type; another 401/403 raises
`AuthenticationError`. Other HTTP failures (including 429 and 5xx), aiohttp
client errors, timeouts, and malformed JSON raise `RequestError` with the original
exception as the cause. There is no general retry of failed writes.
Cancellation propagates unchanged. Caller-provided open sessions remain open;
sessions created by `_request()` are closed on both success and failure.

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
| `get_water_usage_events(device_id, from_datetime, to_datetime, *, from_ts, to_ts)` | Individual water usage events with ML fixture predictions; each bound may use a datetime or integer millisecond epoch, or its upstream `*_ts` keyword | `list[dict]` |
| `submit_water_usage_event_feedback(event_id, fixture_id, ...)` | Submit fixture correction feedback | `dict` |
| `open_valve(device_id)` | Open the shutoff valve | `dict` |
| `close_valve(device_id)` | Close the shutoff valve | `dict` |
| `get_away_mode(device_id)` | Get away mode status | `dict` |
| `enable_away_mode(device_id)` | Enable away mode | `None` |
| `disable_away_mode(device_id)` | Disable away mode | `None` |
| `get_autoshuftoff_status(device_id)` | Get auto shutoff configuration | `dict` |
| `set_autoshutoff_enabled(device_id, shutoff_on, time)` | Enable/disable auto shutoff | `dict` |
| `get_device_preferences(device_id)` | Get all device preferences | `list[dict]` |
| `set_device_preferences(device_id, data)` | Set device preferences | `None` |
| `get_health_tests(device_id)` | Get health/leak test history | `dict` |
| `run_leak_test(device_id, extended_test)` | Run a standard or extended leak test | `dict` |
| `get_latest_firmware_info(device_id)` | Get firmware version information | `list[dict]` |

> **Note:** `get_autoshuftoff_status` preserves upstream's public method name, including its spelling.

Usage events use `GET /water-usage-events` with `device_id`, `from_ts`, and
`to_ts` query parameters and an access token. Integer milliseconds pass through
unchanged; datetime bounds use `int(value.timestamp() * 1000)` and therefore
respect aware UTC offsets (naive datetimes retain Python's local-time behavior).
Missing, duplicate, or invalid-type bounds raise `TypeError` before any request;
booleans are not accepted as timestamps. Range ordering and timestamp magnitude
are not additionally validated.

Feedback uses `POST /water-usage-events/{event_id}/feedback/` with an **ID token**
and JSON `{"fixture_id": 8, "sub_fixture_id": null, "tell_us": null}`. Optional
values replace the nulls when supplied; the fields are not omitted.

The event method makes one logical GET and returns the decoded payload without
paging, deduplication, or reconciliation. Server result caps, pagination,
retention, ordering, boundary inclusivity, open-versus-close timestamp selection,
and ongoing-event behavior are not established. Empty or absent observations
do not prove zero historical consumption or deletion.

An event ID is usable in the feedback URL, but stability across corrections,
splits/merges, or reprocessing is not proven. The nested prediction
`created_timestamp` is not an established event-wide revision for volume or
feedback. Neither `latest_*` field names nor a `user-feedback` algorithm label
prove precedence or server freshness. Replacing a prior observation on a later
fetch is a consumer's local acceptance policy, not authoritative revision
ordering.

`fixture_id` denotes a catalog category (`home_inventory_type_id`), not a
particular household fixture. Separate optional `sub_fixture_id` values can
reference named instances; labels alone are not stable household identities.
The diagnostic history comparator uses half-open start-time ownership as a
local comparison convention, not a claim about server window semantics.

---

### `HomeInventory` — [aiophyn/home_inventory.py](../aiophyn/home_inventory.py)

Handles fixture type catalog and per-device fixture inventory management.

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `get_fixture_types()` | Master catalog of all fixture types (Toilet, Sink, etc.) | `list[dict]` |
| `get_device_inventory(device_id)` | User-configured fixtures for a device (with counts) | `dict` with `list` key |
| `update_device_inventory(device_id, fixture_type_id, count)` | Update fixture count for a device | `dict` |

### Endpoint contracts and evidence

Inventory reads use `GET /home-inventory/types` and
`GET /home-inventory/device/{device_id}`, respectively. The update uses
`POST /home-inventory/device/{device_id}` with an access token and this envelope:

```json
{"list": [{"home_inventory_type_id": 8, "count": 4}]}
```

The source is the **historical 2026-02-24 experiment** in
[the endpoint research notes](https://github.com/rsocko/ideation/blob/77916cd7c0367e7112d56bdb0942f6c16d0ed039/experiments/home-automation/phyn-api-exploration/docs/api-endpoints.md),
which records HTTP 200 with `{"code": "success", "message": "success"}` for that
POST envelope, HTTP 403 for PUT, and HTTP 400 `PWS_ERROR_400_HI_3001` for bare
objects/arrays. The notes cite `scripts/home_inventory_put_test.py --probe-formats`;
probe scripts support the experiment, but raw response captures are not committed.
This is documentation-based provenance, **not a fresh live validation**.
No Phyn requests or mutations are performed by the offline contract suite.

`tests/test_transport_contracts.py` sends public-method calls through the real
`API._request` to a loopback aiohttp server. It checks serialized methods, paths,
queries, JSON, token headers, decoding, bounded reauthentication, error causes,
session ownership, and cancellation. Inventory write expectations derive from
the cited experiment; event/feedback signatures preserve the inherited upstream
contract. Responses and error scenarios are independent synthetic cases.
Fixture list/dict shape checks in the unit suite are only local model checks,
not proof of server behavior. No new validation policy for negative fixture IDs,
counts, naive datetimes, or reversed ranges is inferred from these fixtures.

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

### Partner authentication

Upstream removed the Kohler partner authentication module. Authentication now
uses the standard Phyn API; `KOHLER_API` is no longer available.

---

## Error Hierarchy

Defined in [aiophyn/errors.py](../aiophyn/errors.py):

```
Exception
├── PhynError          # Base error for all Phyn-related errors
│   ├── RequestError          # HTTP, timeout, and JSON decoding failures
│   └── AuthenticationError   # Authentication failed or retry exhausted
└── BrandError                # Legacy exported error; brand argument is ignored
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

Upstream removed the root-level package wrapper. Imports resolve through the
installed `aiophyn` package; distribution checks verify that provenance outside
the source checkout.

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
