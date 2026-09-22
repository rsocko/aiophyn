"""Offline tests of opt-in, transport limits and private-file protections."""

import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from aiohttp import ClientSession, web
import pytest

from examples import diagnostics as diag

ROOT = Path(__file__).resolve().parents[1]


def run_pytest(*args, credentials=False):
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("PHYN_"):
            del environment[key]
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if credentials:
        environment.update(
            PHYN_USERNAME="synthetic-user", PHYN_PASSWORD="synthetic-password"
        )
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "pytest_asyncio.plugin", *args],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
    )


@pytest.mark.parametrize("credentials", [False, True])
def test_default_suite_deselects_live_without_reading_credentials(credentials):
    result = run_pytest(
        "tests/test_live_readonly.py",
        "tests/test_home.py",
        "-q",
        credentials=credentials,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 deselected" in result.stdout


def test_offline_pytest_never_loads_live_configuration():
    code = """
import pytest
from examples import diagnostics
def forbidden(*args, **kwargs):
    raise AssertionError("offline pytest loaded live configuration")
diagnostics.load_configuration = forbidden
raise SystemExit(pytest.main(["tests/test_home.py", "tests/test_live_readonly.py", "-q"]))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 deselected" in result.stdout


@pytest.mark.parametrize(
    "script",
    [
        "test_api",
        "test_alerts",
        "test_comprehensive",
        "test_home_inventory",
        "test_water_usage_events",
    ],
)
@pytest.mark.parametrize("module", [False, True])
def test_cli_entrypoint_help_does_not_need_configuration(script, module):
    args = (
        ["-m", "examples." + script]
        if module
        else [str(ROOT / "examples" / (script + ".py"))]
    )
    result = subprocess.run(
        [sys.executable, *args, "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--env-file" in result.stdout
    assert "--history" in result.stdout


@pytest.mark.parametrize(
    "options,expected",
    [
        (["--run-live"], "Live configuration invalid"),
        (
            ["--run-live", "--env-file", "does-not-exist.env"],
            "Live configuration invalid",
        ),
        (["--env-file", "does-not-exist.env"], "requires explicit --run-live"),
        (["--run-live-writes"], "Live writes are unsupported"),
        (["--history-start", "2025-01-01"], "requires explicit --run-live"),
    ],
)
def test_explicit_live_misconfiguration_is_not_green_skip(options, expected):
    result = run_pytest("tests/test_live_readonly.py", "-q", *options)
    assert result.returncode != 0
    assert expected in result.stdout + result.stderr


def test_external_dns_and_direct_ip_are_blocked():
    for host in ("api.phyn.com", "cognito-idp.us-east-1.amazonaws.com", "192.0.2.1"):
        with pytest.raises(RuntimeError, match="Offline test blocked"):
            socket.getaddrinfo(host, 443)
    with socket.socket() as sock:
        with pytest.raises(RuntimeError, match="Offline test blocked"):
            sock.connect(("192.0.2.1", 443))
        with pytest.raises(RuntimeError, match="Offline test blocked"):
            sock.connect_ex(("192.0.2.1", 443))
    assert socket.getaddrinfo("127.0.0.1", 443)


def test_request_budget_is_hard_cap_and_close_stops_future_sends(monkeypatch):
    sleeps = []
    monkeypatch.setattr(diag.time, "sleep", sleeps.append)
    monkeypatch.setattr(diag.time, "monotonic", lambda: 10)
    budget = diag.RequestBudget(limit=2, spacing=0.5)
    budget.take()
    budget.take()
    with pytest.raises(RuntimeError, match="budget"):
        budget.take()
    assert budget.count == 2
    assert sleeps == [0, 0.5]
    budget = diag.RequestBudget()
    budget.close()
    with pytest.raises(RuntimeError, match="budget"):
        budget.take()


def test_cognito_configuration_bounds_timeouts_retries_and_wire_sends(monkeypatch):
    sdk = Mock()
    monkeypatch.setattr(diag.boto3.session, "Session", Mock(return_value=sdk))
    budget = diag.RequestBudget(limit=2, spacing=0)
    with diag.bounded_cognito(budget):
        client = diag.boto3.client("cognito-idp", region_name="us-east-1")
    config = sdk.client.call_args.kwargs["config"]
    assert config.connect_timeout == config.read_timeout == 5
    assert config.retries == {"total_max_attempts": 1}
    assert config.signature_version is diag.UNSIGNED
    client.meta.events.register.assert_called_once_with("before-send", budget.take)


@pytest.mark.asyncio
async def test_transport_allows_loopback_get_but_blocks_writes_redirects_and_over_budget():
    received = []

    async def handler(request):
        received.append(request.path)
        if request.path == "/redirect":
            raise web.HTTPFound("/destination")
        return web.json_response([])

    application = web.Application()
    application.router.add_route("*", "/{tail:.*}", handler)
    runner = web.AppRunner(application)
    await runner.setup()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    site = web.SockSite(runner, sock)
    await site.start()
    budget = diag.RequestBudget(limit=2, spacing=0)
    try:
        async with ClientSession(trace_configs=[diag.trace_config(budget)]) as session:
            url = f"http://127.0.0.1:{port}"
            async with session.get(url + "/ok") as response:
                assert await response.json() == []
            with pytest.raises(RuntimeError, match="GET"):
                await session.post(url + "/write", json={})
            with pytest.raises(RuntimeError, match="redirect"):
                await session.get(url + "/redirect")
            with pytest.raises(RuntimeError, match="budget"):
                await session.get(url + "/over-budget")
    finally:
        await runner.cleanup()
    assert received == ["/ok", "/redirect"]
    assert budget.count == 2
    assert budget.counts == {"cognito": 0, "phyn_rest": 2}


@pytest.mark.asyncio
async def test_per_send_hook_counts_connection_retries_not_logical_starts():
    budget = diag.RequestBudget(limit=2, spacing=0)
    trace = diag.trace_config(budget)
    trace.freeze()
    params = SimpleNamespace(method="GET")
    await trace.on_request_start.send(None, None, params)
    await trace.on_request_headers_sent.send(None, None, params)
    await trace.on_request_headers_sent.send(None, None, params)
    with pytest.raises(RuntimeError, match="budget"):
        await trace.on_request_headers_sent.send(None, None, params)
    assert budget.counts == {"cognito": 0, "phyn_rest": 2}


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.live",
        ".env.local",
        "nested/.env.live",
        "nested/private.env",
        ".env.example",
        "nested/.env.example",
        "examples/config.py",
        ".artifacts/report.json",
        "nested/.artifacts/raw.json",
        ".venv/site.cfg",
        ".venv-live/site.cfg",
        ".venv.39/site.cfg",
        ".coverage",
        ".coverage.local",
        "coverage.xml",
        "junit-results.xml",
    ],
)
def test_private_paths_are_ignored(path):
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", path],
        cwd=ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, path


def test_placeholder_is_not_ignored_and_no_private_files_are_tracked():
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "examples/.env.example"],
        cwd=ROOT,
        capture_output=True,
    )
    assert result.returncode == 1
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    for name in filter(None, tracked):
        path = Path(name)
        assert not (
            (
                path.name == ".env"
                or path.name.startswith(".env.")
                or path.name.endswith(".env")
            )
            and name != "examples/.env.example"
        ), "A non-placeholder environment file is already tracked"
        assert ".artifacts" not in path.parts, "A private report is already tracked"
        assert (
            name != "examples/config.py"
        ), "Private Python configuration is already tracked"
