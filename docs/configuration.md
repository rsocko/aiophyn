# Configuration

This document explains how to configure the `aiophyn` library and its example scripts.

## Environment Variables

The example scripts in `examples/` use a `.env` file for credentials. A template is provided at `examples/.env.example`.

### Setup

```bash
# Copy the template
cp examples/.env.example examples/.env

# Edit with your credentials
# (use any text editor)
```

### Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PHYN_USERNAME` | Yes | — | Your Phyn or Kohler account email address |
| `PHYN_PASSWORD` | Yes | — | Your Phyn or Kohler account password |
| `PHYN_BRAND` | No | `"phyn"` | Brand: `"phyn"` for Phyn devices, `"kohler"` for Kohler H2Wise+ |
| `PHYN_DEVICE_ID` | No | auto-discovered | Specific device ID to target (skips auto-discovery) |

### .env.example Contents

```dotenv
# Phyn API Test Configuration
#
# Copy this file to .env and fill in your credentials.
# The .env file is excluded from version control via .gitignore.
#
# Required:
PHYN_USERNAME=your_email@example.com
PHYN_PASSWORD=your_password_here
PHYN_BRAND=phyn

# Optional: Set a specific device ID to skip auto-discovery
# PHYN_DEVICE_ID=YOUR_DEVICE_ID_HERE
```

> **Security:** The `.env` file should never be committed to version control. Ensure it is listed in `.gitignore`.

---

## Brand Configuration

The library supports two brands that use the same Phyn hardware platform:

### Phyn (`phyn_brand="phyn"`)

- Direct authentication via AWS Cognito SRP
- Default API keys and Cognito pool settings are built into the library
- This is the default brand if not specified

### Kohler H2Wise+ (`phyn_brand="kohler"`)

- Authentication goes through Kohler's Azure AD B2C identity provider first
- The Kohler token is exchanged for Phyn credentials
- Requires the `pycryptodome` package for AES decryption of the password token
- Uses Kohler-specific API keys and Cognito settings retrieved at runtime

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
        phyn_brand="phyn",         # or "kohler"
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
| `phyn_brand` | `str` | `"phyn"` | `"phyn"` or `"kohler"` |
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
| `pycognito` | `^2022.8.0` | AWS Cognito SRP authentication helper |
| `paho-mqtt` | `>=1.6.1,<3.0.0` | MQTT client for real-time streaming |
| `pysocks` | `>=1.7.1,<2.0.0` | SOCKS proxy support for MQTT connections |
| `pycryptodome` | `>=3.20.0,<4.0.0` | AES decryption for Kohler password tokens |

### Example Script Dependencies

| Package | Purpose |
|---------|---------|
| `python-dotenv` | Load `.env` files for credentials |

### Test Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
