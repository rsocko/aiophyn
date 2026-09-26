"""Offline wire contracts through public methods and the real API._request.

Inventory POST/envelope expectations come from the 2026-02-24 experiment
documented in rsocko/ideation (linked in docs/architecture.md), not a live
capture. Event bounds/feedback preserve the upstream public contract.
All responses below are independent synthetic examples, not server evidence.
"""

import asyncio
import json
import socket
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.client_exceptions import ClientResponseError

from aiophyn.api import API
from aiophyn.errors import AuthenticationError, RequestError


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def transport(monkeypatch):
    """Only endpoint origins and unrelated MQTT/Cognito I/O are substituted."""
    server = SimpleNamespace(
        requests=[],
        statuses=[200],
        payload={"synthetic": True},
        responses=None,
        raw_body=None,
        hold=False,
        expected_requests=1,
        entered=asyncio.Event(),
        release=asyncio.Event(),
    )

    async def handle(request):
        body = await request.read()
        server.requests.append(
            {
                "method": request.method,
                "path": request.path,
                "query": list(request.query.items()),
                "headers": dict(request.headers),
                "body": json.loads(body) if body else None,
            }
        )
        if len(server.requests) >= server.expected_requests:
            server.entered.set()
        if server.hold:
            await server.release.wait()
        status = server.statuses[0]
        if len(server.statuses) > 1:
            server.statuses.pop(0)
        if server.raw_body is not None:
            return web.Response(
                status=status, text=server.raw_body, content_type="application/json"
            )
        if server.responses is not None:
            key = (request.path, tuple(sorted(request.query.items())))
            return web.json_response(server.responses[key], status=status)
        return web.json_response(server.payload, status=status)

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        base = f"http://127.0.0.1:{sock.getsockname()[1]}"
        await web.SockSite(runner, sock).start()
        monkeypatch.setattr("aiophyn.device.API_BASE", base)
        monkeypatch.setattr("aiophyn.home_inventory.API_BASE", base)
        monkeypatch.setattr("aiophyn.api.MQTTClient", MagicMock())
        async with ClientSession(timeout=ClientTimeout(total=2)) as session:
            api = API("offline@example.invalid", "synthetic-password", session=session)
            api._token = "synthetic-access"
            api._id_token = "synthetic-id"
            api._refresh_token = "synthetic-refresh"
            # Exercise async_authenticate's refresh branch without AWS access.
            auth = AsyncMock(
                return_value={
                    "AuthenticationResult": {
                        "AccessToken": "refreshed-access",
                        "IdToken": "refreshed-id",
                        "ExpiresIn": 3600,
                    }
                }
            )
            monkeypatch.setattr(api, "_run_blocking", auth)
            yield SimpleNamespace(api=api, server=server, auth=auth, session=session)
    finally:
        server.release.set()
        await runner.cleanup()
        sock.close()


def assert_request(request, method, path, body=None, query=(), token="synthetic-access"):
    assert request["method"] == method
    assert request["path"] == path
    assert sorted(request["query"]) == sorted(query)
    assert request["body"] == body
    assert request["headers"]["Authorization"] == token
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["headers"]["Accept"] == "application/json"
    assert request["headers"]["x-api-key"] == "E7nfOgW6VI64fYpifiZSr6Me5w1Upe155zbu4lq8"


@pytest.mark.parametrize(
    "method,args,path,response",
    [
        (
            "get_fixture_types",
            (),
            "/home-inventory/types",
            [{"home_inventory_type_id": 8, "name": "Synthetic toilet"}],
        ),
        (
            "get_device_inventory",
            ("offline-device",),
            "/home-inventory/device/offline-device",
            {"list": [{"home_inventory_type_id": 8, "count": 4}]},
        ),
    ],
)
async def test_inventory_reads(transport, method, args, path, response):
    transport.server.payload = response
    result = await getattr(transport.api.home_inventory, method)(*args)
    assert result == response
    assert len(transport.server.requests) == 1
    assert_request(transport.server.requests[0], "GET", path)
    transport.auth.assert_not_awaited()


@pytest.mark.parametrize("concurrent", [False, True], ids=["alternating", "concurrent"])
async def test_two_device_reads_keep_wire_routes_and_results_isolated(
    transport, concurrent
):
    devices = ("offline-device-one", "offline-device-two")
    responses = {}
    routes = {}
    for device_id, volume, pressure in zip(devices, (2, 9), (41, 62)):
        routes[device_id, "inventory"] = (
            f"/home-inventory/device/{device_id}",
            (),
        )
        routes[device_id, "events"] = (
            "/water-usage-events",
            tuple(
                sorted(
                    [
                        ("device_id", device_id),
                        ("from_ts", "1704067200000"),
                        ("to_ts", "1704153600000"),
                    ]
                )
            ),
        )
        routes[device_id, "state"] = (f"/devices/{device_id}/state", ())
        responses[routes[device_id, "inventory"]] = {
            "list": [{"home_inventory_type_id": 7, "count": volume}]
        }
        responses[routes[device_id, "events"]] = [
            {"id": "shared-synthetic-event", "total_flow": volume}
        ]
        responses[routes[device_id, "state"]] = {
            "device_id": device_id,
            "pressure": pressure,
        }
    transport.server.responses = responses
    selected_reads = [
        (device_id, kind)
        for kind in ("inventory", "events", "state")
        for device_id in (*devices, *devices)
    ]

    async def read(device_id, kind):
        if kind == "inventory":
            return await transport.api.home_inventory.get_device_inventory(device_id)
        if kind == "events":
            return await transport.api.device.get_water_usage_events(
                device_id, from_ts=1704067200000, to_ts=1704153600000
            )
        return await transport.api.device.get_state(device_id)

    if concurrent:
        transport.server.hold = True
        transport.server.expected_requests = len(selected_reads)
        batch = asyncio.gather(*(read(*selection) for selection in selected_reads))
        try:
            await asyncio.wait_for(transport.server.entered.wait(), 2)
            assert not batch.done()
        finally:
            transport.server.release.set()
            results = await batch
    else:
        results = [await read(*selection) for selection in selected_reads]

    expected_routes = [routes[selection] for selection in selected_reads]
    assert results == [responses[route] for route in expected_routes]
    actual_routes = [
        (request["path"], tuple(sorted(request["query"])))
        for request in transport.server.requests
    ]
    assert sorted(actual_routes) == sorted(expected_routes)
    if not concurrent:
        assert actual_routes == expected_routes
    for request, (path, query) in zip(transport.server.requests, actual_routes):
        assert_request(request, "GET", path, query=query)
    transport.auth.assert_not_awaited()


async def test_inventory_update_historical_post_envelope(transport):
    transport.server.payload = {"code": "success", "message": "success"}
    result = await transport.api.home_inventory.update_device_inventory(
        "offline-device", 8, 4
    )
    assert result == {"code": "success", "message": "success"}
    assert len(transport.server.requests) == 1
    assert_request(
        transport.server.requests[0],
        "POST",
        "/home-inventory/device/offline-device",
        body={"list": [{"home_inventory_type_id": 8, "count": 4}]},
    )
    transport.auth.assert_not_awaited()


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ((1704067200123, 1704153600456), {}),
        ((), {"from_ts": 1704067200123, "to_ts": 1704153600456}),
        (
            (),
            {"from_datetime": 1704067200123, "to_datetime": 1704153600456},
        ),
        (
            (
                datetime(2024, 1, 1, 0, 0, 0, 123000, tzinfo=timezone.utc),
                datetime(2024, 1, 2, 0, 0, 0, 456000, tzinfo=timezone.utc),
            ),
            {},
        ),
        (
            (),
            {
                "from_datetime": datetime(
                    2024, 1, 1, 5, 30, 0, 123000,
                    tzinfo=timezone(timedelta(hours=5, minutes=30)),
                ),
                "to_datetime": datetime(
                    2024, 1, 1, 19, 0, 0, 456000,
                    tzinfo=timezone(timedelta(hours=-5)),
                ),
            },
        ),
        (
            (datetime(2024, 1, 1, 0, 0, 0, 123000, tzinfo=timezone.utc),),
            {"to_ts": 1704153600456},
        ),
    ],
)
async def test_event_bounds_on_wire(transport, args, kwargs):
    response = [{"id": "synthetic-event", "total_flow": 1.25}, {"id": "second-event"}]
    transport.server.payload = response
    result = await transport.api.device.get_water_usage_events(
        "device +&", *args, **kwargs
    )
    assert result == response
    assert len(transport.server.requests) == 1
    assert_request(
        transport.server.requests[0],
        "GET",
        "/water-usage-events",
        query=[
            ("device_id", "device +&"),
            ("from_ts", "1704067200123"),
            ("to_ts", "1704153600456"),
        ],
    )


@pytest.mark.parametrize(
    "bounds,message",
    [
        ({}, "from bound"),
        ({"from_ts": 0}, "to bound"),
        ({"to_ts": 1}, "from bound"),
        ({"from_datetime": 0, "from_ts": 0, "to_ts": 1}, "only one from"),
        ({"from_ts": 0, "to_datetime": 1, "to_ts": 1}, "only one to"),
        ({"from_ts": "0", "to_ts": 1}, "from_ts must be"),
        ({"from_ts": 0, "to_ts": 1.5}, "to_ts must be"),
        ({"from_datetime": True, "to_ts": 1}, "from bound"),
        ({"from_ts": 0, "to_ts": False}, "to_ts must be"),
        ({"from_ts": False, "to_ts": 1}, "from_ts must be"),
        ({"from_ts": 0, "to_datetime": "1"}, "to bound"),
    ],
)
async def test_invalid_bounds_do_not_send_request(transport, bounds, message):
    with pytest.raises(TypeError, match=message):
        await transport.api.device.get_water_usage_events("offline-device", **bounds)
    assert transport.server.requests == []
    transport.auth.assert_not_awaited()


@pytest.mark.parametrize("status", [200, 401, 403])
@pytest.mark.parametrize(
    "options,body",
    [
        ({}, {"fixture_id": 8, "tell_us": None}),
        (
            {"tell_us": "Category + correction"},
            {"fixture_id": 8, "tell_us": "Category + correction"},
        ),
    ],
)
async def test_feedback_id_token_and_refresh_preserve_body(transport, status, options, body):
    transport.server.statuses = [status, 200]
    transport.server.payload = {"code": "success"}
    result = await transport.api.device.submit_water_usage_event_feedback(
        "synthetic-event", 8, **options
    )
    assert result == {"code": "success"}
    tokens = ["synthetic-id"] if status == 200 else ["synthetic-id", "refreshed-id"]
    assert len(transport.server.requests) == len(tokens)
    for request, token in zip(transport.server.requests, tokens):
        assert_request(
            request, "POST", "/water-usage-events/synthetic-event/feedback/",
            body=body, token=token,
        )
    if status == 200:
        transport.auth.assert_not_awaited()
    else:
        transport.auth.assert_awaited_once_with(transport.api._refresh_token_auth)


@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize("exhausted", [False, True])
async def test_access_token_reauth_once(transport, status, exhausted):
    transport.server.statuses = [status, status if exhausted else 200]
    if exhausted:
        with pytest.raises(AuthenticationError) as caught:
            await transport.api.home_inventory.get_fixture_types()
        assert isinstance(caught.value.__cause__, ClientResponseError)
        assert caught.value.__cause__.status == status
    else:
        assert await transport.api.home_inventory.get_fixture_types() == {"synthetic": True}
    assert len(transport.server.requests) == 2
    for request, token in zip(
        transport.server.requests, ["synthetic-access", "refreshed-access"]
    ):
        assert_request(request, "GET", "/home-inventory/types", token=token)
    transport.auth.assert_awaited_once_with(transport.api._refresh_token_auth)


@pytest.mark.parametrize("status", [429, 500, 502, 503])
async def test_http_errors_do_not_retry_writes(transport, status):
    transport.server.statuses = [status]
    with pytest.raises(RequestError) as caught:
        await transport.api.device.submit_water_usage_event_feedback("synthetic-event", 8)
    assert isinstance(caught.value.__cause__, ClientResponseError)
    assert caught.value.__cause__.status == status
    assert len(transport.server.requests) == 1
    transport.auth.assert_not_awaited()


async def test_malformed_json_is_request_error(transport):
    transport.server.raw_body = '{"unfinished":'
    with pytest.raises(RequestError) as caught:
        await transport.api.home_inventory.get_fixture_types()
    assert isinstance(caught.value.__cause__, json.JSONDecodeError)
    assert len(transport.server.requests) == 1
    transport.auth.assert_not_awaited()


@pytest.mark.parametrize("internal", [False, True], ids=["external", "internal"])
@pytest.mark.parametrize("outcome", ["success", "http", "json", "timeout", "cancel"])
async def test_session_ownership_and_cancellation(transport, monkeypatch, internal, outcome):
    sessions = []

    def create_session(**kwargs):
        kwargs["timeout"] = ClientTimeout(total=0.1 if outcome == "timeout" else 2)
        session = ClientSession(**kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr("aiophyn.api.ClientSession", create_session)
    transport.api._session = None if internal else create_session()
    if outcome == "http":
        transport.server.statuses = [500]
    elif outcome == "json":
        transport.server.raw_body = "not-json"
    elif outcome in ("timeout", "cancel"):
        transport.server.hold = True

    try:
        if outcome == "cancel":
            task = asyncio.create_task(transport.api.home_inventory.get_fixture_types())
            try:
                await asyncio.wait_for(transport.server.entered.wait(), timeout=2)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            finally:
                if not task.done():
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
        elif outcome == "success":
            assert await transport.api.home_inventory.get_fixture_types() == {"synthetic": True}
        else:
            with pytest.raises(RequestError) as caught:
                await transport.api.home_inventory.get_fixture_types()
            causes = {
                "http": ClientResponseError,
                "json": json.JSONDecodeError,
                "timeout": asyncio.TimeoutError,
            }
            assert isinstance(caught.value.__cause__, causes[outcome])

        assert len(sessions) == 1
        assert sessions[0].closed is internal
        assert not transport.session.closed
        assert len(transport.server.requests) == 1
        transport.auth.assert_not_awaited()
    finally:
        transport.server.release.set()
        for session in sessions:
            await session.close()
