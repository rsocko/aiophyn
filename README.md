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
- **Kohler H2Wise+** — uses the unified Phyn authentication path; the legacy partner bridge is no longer included

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

Requires Python 3.9 or newer. To install the published release:

```bash
pip install aiophyn
```

The fixture-usage feature branch is not necessarily available on PyPI. To try
that branch explicitly (use a reviewed commit SHA instead of the branch name
for a reproducible installation):

```bash
pip install "aiophyn @ git+https://github.com/rsocko/aiophyn.git@feature/fixture-usage"
```

The current remediation candidate is on `validation/water-fixture-usage`, not
`main` or `feature/fixture-usage`. It includes the corrected Home Assistant
authentication dependency and diagnostic harness. Use a reviewed immutable
commit from that validation branch for paired testing; it is not a published
release, and its package version still matches upstream's `2026.9.1`.

For development, use Poetry 2.2.1 and the checked-in dependency lock:

```bash
git clone --branch feature/fixture-usage https://github.com/rsocko/aiophyn.git
cd aiophyn
poetry sync --with dev
poetry run python -m pytest tests
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

## CI Tests and Packaging

`.github/workflows/smoke-test.yml` runs on all pull requests and pushes to
`main`, `feature/**` (including `feature/fixture-usage`), `work/**`,
`validation/**`, and `rsocko-*`. Python 3.9, 3.12, and 3.14 each run the offline unit/contract suite
against the Poetry editable install, then verify wheel and sdist installations
in clean environments outside the checkout. No Phyn credentials are required.

Checks cover installed-package provenance, version consistency, supported
exports (`async_get_api`, `HomeInventory`, `API`, `MQTTClient`), representative
fixture API calls through an injected offline transport, runtime dependencies,
`pip check`, strict Twine metadata checks, and rebuilding a source archive
without Git metadata. Release publishing runs the same checks before upload.
See [Testing](docs/testing.md) for local commands and dependency-lock details.

Live checks are deselected by default, even when credentials are present.
The optional read-only harness requires explicit selection and `--run-live`;
it does not enable inventory changes, feedback, or valve operations. Installing
the harness does not authorize account access. See
[local live checks](docs/testing.md#local-opt-in-read-only-checks) for limits
and safe configuration.

## Acknowledgements

This work follows the example of @bachya's excellent [aioflo](https://github.com/bachya/aioflo) library for Moen Flo devices.

## License

[MIT](LICENSE)
