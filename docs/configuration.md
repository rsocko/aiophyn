# Configuration

This document explains how to configure the `aiophyn` library and its example scripts.

## Environment Variables

The read-only diagnostic scripts in `examples/` read process environment
variables at runtime. They never search for or automatically load `.env`,
`.env.live`, `.env.local` or `config.py`. The MQTT example alone retains its
legacy `examples/config.py` setup; see [examples](examples.md).

### Setup

```powershell
Copy-Item examples\.env.example .env.live
# Edit .env.live locally; do not paste credentials into a shared transcript.
# Optional dependency, needed only for an explicitly selected dotenv file:
python -m pip install python-dotenv
python examples\test_water_usage_events.py --env-file .env.live
```

Without `--env-file`, only `PHYN_*` process variables are used and python-dotenv
is not needed. With it, the named file must exist. Process variables take
precedence over file values. Dotenv interpolation is disabled, so secrets are
not expanded from unrelated environment variables. Missing credentials,
placeholder credentials or a missing optional dependency produce a nonzero
exit with local configuration guidance, never a successful no-op.

### Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PHYN_USERNAME` | Yes | — | Your Phyn or Kohler account email address |
| `PHYN_PASSWORD` | Yes | — | Your Phyn or Kohler account password |
| `PHYN_BRAND` | No | `"phyn"` | Deprecated compatibility argument; ignored by the current runtime |
| `PHYN_DEVICE_ID` | For history | first discovered device | Select one discovered device; required for history characterization |

### .env.example Contents

```dotenv
# Phyn API Test Configuration
#
# Copy to a local .env.live and select it explicitly with --env-file.
#
# Required:
PHYN_USERNAME=your_email@example.com
PHYN_PASSWORD=your_password_here
PHYN_BRAND=phyn

# Select a discovered device; mandatory for history characterization.
# PHYN_DEVICE_ID=YOUR_DEVICE_ID_HERE
```

> **Security:** Credentials stay local; no GitHub account secrets are needed.
> `.env`, `*.env`, `.env.*`, `examples/config.py`, `.artifacts/`, local virtual
> environments and coverage/JUnit outputs are ignored. `examples/.env.example`
> is a tracked placeholder only. Ignore rules cannot protect an already tracked
> file: check both `git check-ignore` and `git ls-files` before sharing changes.
> Never commit raw captures, reports, passwords or tokens. Do not delete
> unrelated private files while cleaning up.

Ordinary `python -m pytest` and CI's `python -m pytest tests` stay offline even
when credentials are present. A file is read by live pytest fixtures only after
both `--run-live` and a selected `live_readonly` test. Merely approving or
installing this harness is not permission to access a household account.

---

## Brand Configuration

The current runtime authenticates via AWS Cognito SRP. `phyn_brand` is accepted
for compatibility but ignored. Historical Kohler Azure AD B2C behavior is not
implemented by this current authentication path; setting `PHYN_BRAND=kohler`
does not activate an alternate login flow. These examples do not change that
contract.

---

## Library Configuration (Programmatic)

When using the library in code, configuration is passed to `async_get_api()`:

```python
from aiophyn import async_get_api
from aiohttp import ClientSession

async with ClientSession() as session:
    api = await async_get_api(
        username="user@example.com",
        password="your_password",
        phyn_brand="phyn",         # deprecated, ignored
        session=session,           # optional: reuse an aiohttp session
        client_id="my-client",     # optional: MQTT client ID
        verify_ssl=True,           # optional: disable SSL verification
        proxy="proxy.example.com", # optional: HTTP proxy hostname
        proxy_port=8080,           # optional: HTTP proxy port
    )
```

### Parameter Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Phyn/Kohler account email |
| `password` | `str` | — | Phyn/Kohler account password |
| `phyn_brand` | `str` | `"phyn"` | Deprecated; ignored |
| `session` | `ClientSession` | `None` | Reuse an existing aiohttp session |
| `client_id` | `str` | `None` | MQTT client identifier (auto-generated if not set) |
| `verify_ssl` | `bool` | `True` | Whether to verify SSL certificates |
| `proxy` | `str` | `None` | HTTP proxy hostname or IP |
| `proxy_port` | `int` | `None` | HTTP proxy port |

### Proxy Support

For debugging or network inspection, the library supports HTTP proxies:

```python
api = await async_get_api(
    username="user@example.com",
    password="password",
    verify_ssl=False,              # Usually needed with proxy
    proxy="127.0.0.1",
    proxy_port=8080,
)
```

Both REST API calls and MQTT WebSocket connections respect the proxy settings.

---

## Dependencies

### Runtime Dependencies (from `pyproject.toml`)

| Package | Version | Purpose |
|---------|---------|---------|
| `aiohttp` | `^3.8.1` | Async HTTP client for REST API calls |
| `boto3` | `^1.20.24` | AWS SDK for Cognito authentication |
| `pycognito` | `^2024.5.1` | AWS Cognito SRP authentication helper |
| `paho-mqtt` | `>=2.0.0,<3.0.0` | MQTT client for real-time streaming |
| `pysocks` | `>=1.7.1,<2.0.0` | SOCKS proxy support for MQTT connections |
| `pycryptodome` | `>=3.20.0,<4.0.0` | AES decryption for Kohler password tokens |

### Example Script Dependencies

| Package | Purpose |
|---------|---------|
| `python-dotenv` | Optional; load only an explicitly selected `--env-file` |

### Test Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
