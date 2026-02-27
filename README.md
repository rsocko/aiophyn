# aiophyn

An asynchronous Python library for [Phyn](https://www.phyn.com/) Smart Water devices, including Kohler's H2Wise+.

Built to support the [Phyn integration for Home Assistant](https://github.com/jordanruthe/homeassistant-phyn), this library provides a complete async interface to the Phyn cloud API.

## Features

- **Device state** — temperature, pressure, flow, valve status, online status
- **Water consumption** — daily/monthly/yearly with hourly breakdowns
- **Water usage events** — individual events with ML-based fixture predictions
- **Home inventory** — fixture type catalog and per-device fixture configuration
- **Shutoff valve control** — open/close the water shutoff valve
- **Away mode** — get, enable, and disable away mode
- **Auto-shutoff** — get status, enable/disable with optional timer
- **Health tests** — view history and run standard/extended leak tests
- **Firmware info** — current version and upgrade history
- **Device preferences** — read and set device configuration
- **Real-time streaming** — MQTT over WebSockets for live device updates
- **Kohler H2Wise+** — full support via partner authentication bridge

## Quick Start

```python
import asyncio
from aiohttp import ClientSession
from aiophyn import async_get_api

async def main():
    async with ClientSession() as session:
        api = await async_get_api(
            "your_email@example.com",
            "your_password",
            session=session,
        )

        homes = await api.home.get_homes("your_email@example.com")
        device_id = homes[0]["device_ids"][0]

        state = await api.device.get_state(device_id)
        print(f"Temperature: {state['temperature']['mean']}°F")
        print(f"Pressure: {state['pressure']['mean']} PSI")
        print(f"Valve: {state['sov_status']['v']}")

asyncio.run(main())
```

## Installation

```bash
pip install aiophyn
```

Or install from source for development:

```bash
git clone https://github.com/jordanruthe/aiophyn.git
cd aiophyn
pip install -e .
```

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | Class structure, design patterns, and component interactions |
| [Project Structure](docs/project-structure.md) | Repository layout and file descriptions |
| [Examples](docs/examples.md) | Guide to the runnable example scripts |
| [Testing](docs/testing.md) | Test suite documentation — what each test validates and how to run them |
| [Configuration](docs/configuration.md) | Environment variables, `.env` setup, and library parameters |

## CI Dependency Smoke Tests

`aiophyn` now includes a dedicated smoke-test workflow to catch missing dependency regressions before release:

- Workflow: `.github/workflows/smoke-test.yml`
- Triggers: `push` (main) and all `pull_request`s
- Validates both install paths:
    - Editable install (`pip install -e .`)
    - Wheel install (`python -m build` + `pip install dist/*.whl`)
- Smoke imports verify core/runtime dependency availability (`MQTTClient`, `KOHLER_API`, `paho-mqtt`, `pysocks`, `pycryptodome`)

## Acknowledgements

This work follows the example of @bachya's excellent [aioflo](https://github.com/bachya/aioflo) library for Moen Flo devices.

## License

[MIT](LICENSE)
