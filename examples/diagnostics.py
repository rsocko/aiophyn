"""Shared, opt-in read-only example runner. Never reads credentials at import."""

import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch

from aiohttp import ClientSession, ClientTimeout, TraceConfig
import boto3
from botocore import UNSIGNED
from botocore.config import Config as BotoConfig

if __package__:
    from .history import characterize_history, completed_week
    from .test_water_usage_events import (
        PayloadError,
        _parse_day_ranges,
        number,
        summarize_usage,
    )
else:
    from history import characterize_history, completed_week
    from test_water_usage_events import (
        PayloadError,
        _parse_day_ranges,
        number,
        summarize_usage,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aiophyn import async_get_api

REQUEST_CAP = 24
REQUEST_SPACING = 0.25
OPERATION_TIMEOUT = 25
RUN_TIMEOUT = 180
SAFE_FIXTURES = {
    "Hot Tub",
    "Irrigation System",
    "Outdoor Spigot",
    "Pool",
    "Shower Only",
    "Shower Tub Combo",
    "Sink",
    "Toilet",
    "Tub",
    "Water Softener",
    "Reverse Osmosis Filter",
    "Dishwasher",
    "Washing Machine",
    "Other",
    "Hot Water Heater",
    "Refrigerator",
    "Unknown",
}


class ConfigurationError(ValueError):
    """Local configuration needs attention before any network access."""


class DiagnosticError(RuntimeError):
    """A local transport guard stopped the run; the message is safe to report."""


@dataclass(repr=False)
class Configuration:
    username: str
    password: str
    brand: str = "phyn"
    device_id: str = ""


def load_configuration(env_file=None, device_id=None):
    """Read only an explicitly selected dotenv file; environment wins."""
    values = {}
    if env_file:
        path = Path(env_file)
        if not path.is_file():
            raise ConfigurationError("--env-file must name an existing local file")
        try:
            from dotenv import dotenv_values
        except ImportError:
            raise ConfigurationError(
                "--env-file requires optional python-dotenv; install with "
                "'python -m pip install python-dotenv', or use process environment variables"
            ) from None
        # No interpolation of arbitrary process secrets into values from a file.
        values.update(dotenv_values(path, interpolate=False))
    values.update(
        {
            key: os.environ[key]
            for key in (
                "PHYN_USERNAME",
                "PHYN_PASSWORD",
                "PHYN_BRAND",
                "PHYN_DEVICE_ID",
            )
            if key in os.environ
        }
    )
    username = values.get("PHYN_USERNAME")
    password = values.get("PHYN_PASSWORD")
    if (
        not username
        or not username.strip()
        or not password
        or not password.strip()
        or username == "your_email@example.com"
        or password == "your_password_here"
    ):
        raise ConfigurationError(
            "Set real PHYN_USERNAME and PHYN_PASSWORD locally before opting in"
        )
    return Configuration(
        username.strip(),
        password,
        values.get("PHYN_BRAND") or "phyn",
        device_id or values.get("PHYN_DEVICE_ID") or "",
    )


class RequestBudget:
    """Shared wire-request cap for aiohttp and Cognito, including auth retries."""

    def __init__(self, limit=REQUEST_CAP, spacing=REQUEST_SPACING):
        self.limit = limit
        self.spacing = spacing
        self.count = 0
        self.counts = {"cognito": 0, "phyn_rest": 0}
        self.next_request = 0.0
        self.lock = threading.Lock()
        self.closed = False

    def take(self, channel="cognito", **kwargs):
        with self.lock:
            if self.closed or self.count >= self.limit:
                raise DiagnosticError(
                    "Read-only request budget exhausted or closed; run aborted"
                )
            time.sleep(max(0, self.next_request - time.monotonic()))
            self.count += 1
            self.counts[channel] += 1
            self.next_request = time.monotonic() + self.spacing

    def close(self):
        with self.lock:
            self.closed = True


@contextmanager
def quiet_logs():
    """Library exception messages/HTTP debug logs can contain secrets."""
    previous = logging.root.manager.disable
    logging.disable(sys.maxsize)
    try:
        yield
    finally:
        logging.disable(previous)


@contextmanager
def bounded_cognito(budget):
    """Bound SDK sends too; async cancellation cannot stop a blocking SRP thread."""
    sdk = boto3.session.Session(
        aws_access_key_id="unused", aws_secret_access_key="unused"
    )

    def client(service_name, **kwargs):
        if service_name != "cognito-idp":
            raise DiagnosticError("Only Cognito authentication is permitted")
        result = sdk.client(
            service_name,
            **kwargs,
            config=BotoConfig(
                signature_version=UNSIGNED,
                connect_timeout=5,
                read_timeout=5,
                retries={"total_max_attempts": 1},
            ),
        )
        result.meta.events.register("before-send", budget.take)
        return result

    with patch("aiophyn.api.boto3.client", client):
        yield


def trace_config(budget):
    trace = TraceConfig()

    async def request_start(session, context, params):
        if params.method.upper() != "GET":
            raise DiagnosticError("Diagnostic REST requests must be read-only GETs")

    async def headers_sent(session, context, params):
        # Per-send, not per logical request: aiohttp can retry a stale connection.
        await asyncio.to_thread(budget.take, channel="phyn_rest")

    async def redirect(session, context, params):
        raise DiagnosticError(
            "Unexpected HTTP redirect; no redirected request was sent"
        )

    trace.on_request_start.append(request_start)
    trace.on_request_headers_sent.append(headers_sent)
    trace.on_request_redirect.append(redirect)
    return trace


def records(value, name):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise PayloadError(f"{name} must be a list of objects")
    return value


def contract_summary(value, kind):
    """Allowlisted structural output only; no raw response values or keys."""
    if kind in ("homes", "catalog", "events"):
        entries = records(value, kind)
    elif kind == "inventory":
        if not isinstance(value, dict) or "list" not in value:
            raise PayloadError("inventory must contain a list")
        entries = records(value["list"], "inventory list")
    else:
        if not isinstance(value, (dict, list)):
            raise PayloadError("endpoint must return an object or list")
        return {"status": "empty" if not value else "passed", "entry_count": len(value)}
    if kind == "homes":
        for home in entries:
            for device in records(home.get("devices"), "home devices"):
                if (
                    not isinstance(device.get("device_id"), str)
                    or not device["device_id"]
                ):
                    raise PayloadError("discovered device requires device_id")
    elif kind in ("catalog", "inventory"):
        for fixture in entries:
            identity = fixture.get("home_inventory_type_id")
            if isinstance(identity, bool) or not isinstance(identity, int):
                raise PayloadError("fixture requires integer home_inventory_type_id")
            if kind == "inventory":
                count = number(fixture.get("count"), "inventory count")
                if not count.is_integer():
                    raise PayloadError("inventory count must be an integer")
    elif kind == "events":
        summarize_usage(entries)
        for event in entries:
            identity = event.get("id") or event.get("event_id")
            if not isinstance(identity, str) or not identity:
                raise PayloadError("event requires a nonempty id or event_id")
            opened = number(event.get("open_edge_timestamp"), "open_edge_timestamp")
            closed = number(event.get("close_edge_timestamp"), "close_edge_timestamp")
            if closed < opened:
                raise PayloadError("event end precedes event start")
    result = {
        "status": "empty" if not entries else "passed",
        "entry_count": len(entries),
    }
    if kind == "inventory":
        result["configured_count"] = sum(
            number(item["count"], "inventory count") > 0 for item in entries
        )
    if kind == "events":
        result["known_metadata_present"] = {
            key: sum(key in item for item in entries)
            for key in (
                "latest_user_feedback",
                "latest_suggested_fixtures_result",
                "created_timestamp",
                "updated_timestamp",
            )
        }
        result["pagination"] = (
            "unknown; list response inspected without paging parameters"
        )
    return result


def safe_usage(events, low, gap, fixture_names=None):
    summary = summarize_usage(events, low, gap, fixture_names)
    algorithms = summary.pop("algorithm_counts")
    safe_algorithms = {}
    for name, count in algorithms.items():
        label = (
            name
            if name
            in {
                "clustering",
                "heuristics",
                "user-feedback",
                "bayesian_v2",
                "duration_based",
                "unknown",
            }
            else "unrecognized"
        )
        safe_algorithms[label] = safe_algorithms.get(label, 0) + count
    summary["algorithm_counts"] = safe_algorithms
    # Custom fixture labels are not safe to publish; combine them without names.
    fixtures = summary.pop("fixtures")
    safe = {}

    def public_label(name):
        prefix = "Fixture type "
        suffix = name[len(prefix):] if name.startswith(prefix) else ""
        return name in SAFE_FIXTURES or (suffix.isascii() and suffix.isdecimal())

    for name, entry in fixtures.items():
        if public_label(name):
            safe[name] = entry
    custom = [entry for name, entry in fixtures.items() if not public_label(name)]
    if custom:
        safe["Unpublished custom labels"] = {
            "total_gallons": sum(entry["total_gallons"] for entry in custom),
            "event_count": sum(entry["event_count"] for entry in custom),
            "average_confidence": None,
        }
    summary["fixtures"] = safe
    return summary


async def run_diagnostics(
    config,
    mode="live",
    days=(7,),
    low=0.70,
    gap=0.15,
    history=False,
    history_start=None,
):
    """Return sanitized results; failure never masquerades as zero use."""
    if mode not in {"live", "usage", "inventory", "comprehensive", "api", "alerts"}:
        raise ConfigurationError("Unsupported diagnostic mode")
    number(low, "low confidence threshold", 1)
    number(gap, "ambiguity gap threshold", 1)
    if (
        not days
        or len(days) > 3
        or any(
            isinstance(day, bool) or not isinstance(day, int) or day < 1 or day > 31
            for day in days
        )
    ):
        raise ConfigurationError("Use up to three day ranges of 1-31 days")
    if history and not config.device_id:
        raise ConfigurationError(
            "History requires an explicit PHYN_DEVICE_ID or --device-id"
        )
    interval = completed_week(history_start) if history else None
    report = {"status": "passed", "checks": []}
    checks = report["checks"]
    budget = RequestBudget()
    stage = "authentication"
    remaining = ["discovery"]
    if mode in {"live", "inventory", "comprehensive"}:
        remaining.extend(["fixture_catalog", "device_inventory"])
    if mode in {"live", "usage", "comprehensive"}:
        remaining.extend(f"events_{day}d" for day in days)
    if mode in {"api", "comprehensive"}:
        remaining.extend(["state", "consumption"])
    if mode == "comprehensive":
        remaining.extend(["preferences", "firmware", "away_mode"])
    if mode == "alerts":
        remaining.extend(["latest_alerts", "active_alerts"])
    if history:
        remaining.append("history")

    async def check(name, operation, kind):
        nonlocal stage
        stage = name
        value = await asyncio.wait_for(operation(), OPERATION_TIMEOUT)
        summary = contract_summary(value, kind)
        checks.append({"name": name, **summary})
        remaining.remove(name)
        return value

    async def perform():
        nonlocal stage, remaining
        async with ClientSession(
            timeout=ClientTimeout(total=15),
            trace_configs=[trace_config(budget)],
        ) as session:
            api = await asyncio.wait_for(
                async_get_api(
                    config.username,
                    config.password,
                    phyn_brand=config.brand,
                    session=session,
                ),
                OPERATION_TIMEOUT,
            )
            checks.append({"name": "authentication", "status": "passed"})
            homes = await check(
                "discovery", lambda: api.home.get_homes(config.username), "homes"
            )
            devices = list(
                dict.fromkeys(d["device_id"] for h in homes for d in h["devices"])
            )
            device_id = config.device_id or (devices[0] if devices else None)
            if device_id is None:
                checks.extend(
                    {
                        "name": name,
                        "status": "skipped",
                        "reason": "No discovered devices",
                    }
                    for name in remaining
                )
                report["status"] = "incomplete"
                return
            if device_id not in devices:
                stage = "device_selection"
                raise ConfigurationError(
                    "Selected device was not discovered for this account"
                )
            now = datetime.now(timezone.utc)
            fixture_names = {}
            if mode in {"live", "inventory", "comprehensive"}:
                catalog = await check(
                    "fixture_catalog", api.home_inventory.get_fixture_types, "catalog"
                )
                for fixture in catalog:
                    name = fixture.get("name")
                    identity = fixture["home_inventory_type_id"]
                    if isinstance(name, str) and name.strip():
                        name = name.strip()
                        if identity in fixture_names and fixture_names[identity] != name:
                            raise PayloadError(
                                "Catalog contains conflicting fixture names"
                            )
                        fixture_names[identity] = name
                await check(
                    "device_inventory",
                    lambda: api.home_inventory.get_device_inventory(device_id),
                    "inventory",
                )
            if mode in {"live", "usage", "comprehensive"}:
                for day in days:
                    events = await check(
                        f"events_{day}d",
                        lambda: api.device.get_water_usage_events(
                            device_id, now - timedelta(days=day), now
                        ),
                        "events",
                    )
                    checks[-1]["usage"] = safe_usage(events, low, gap, fixture_names)
            if mode in {"api", "comprehensive"}:
                await check("state", lambda: api.device.get_state(device_id), "object")
                await check(
                    "consumption",
                    lambda: api.device.get_consumption(
                        device_id, now.strftime("%Y/%m/%d"), details=True
                    ),
                    "object",
                )
            if mode == "comprehensive":
                for name, method in (
                    ("preferences", api.device.get_device_preferences),
                    ("firmware", api.device.get_latest_firmware_info),
                    ("away_mode", api.device.get_away_mode),
                ):
                    await check(name, lambda method=method: method(device_id), "object")
            if mode == "alerts":
                from aiophyn.alert import Alert

                stage = "latest_alerts"
                home_id = next(
                    h.get("id")
                    for h in homes
                    if any(d["device_id"] == device_id for d in h["devices"])
                )
                if not isinstance(home_id, str) or not home_id:
                    raise PayloadError("Alert discovery requires a home id")
                await check(
                    "latest_alerts",
                    lambda: api.alert.get_latest(
                        config.username, home_id, alert_type=Alert.ALERT_TYPES
                    ),
                    "object",
                )
                await check(
                    "active_alerts",
                    lambda: api.alert.get_active_summary(config.username, "unresolved"),
                    "object",
                )
            if history:
                stage = "history"

                async def fetch(left, right):
                    events = await asyncio.wait_for(
                        api.device.get_water_usage_events(
                            device_id, from_ts=left, to_ts=right
                        ),
                        OPERATION_TIMEOUT,
                    )
                    contract_summary(events, "events")
                    return events

                result = await characterize_history(fetch, *interval)
                checks.append({"name": "history", **result})
                remaining.remove("history")
            else:
                checks.append(
                    {"name": "history", "status": "skipped", "reason": "Not requested"}
                )
            remaining = []

    with quiet_logs():
        try:
            with bounded_cognito(budget):
                await asyncio.wait_for(perform(), RUN_TIMEOUT)
        except Exception as error:
            # This is the diagnostic boundary: never echo API exception strings,
            # traceback locals, response values or chained token-bearing causes.
            report["status"] = "failed"
            reason = "Read failed; check credentials, connectivity and API compatibility; no raw error retained"
            if isinstance(error, (PayloadError, ConfigurationError, DiagnosticError)):
                reason = str(error)
            elif isinstance(error, asyncio.TimeoutError):
                reason = (
                    "Read timed out; run aborted without treating partial data as empty"
                )
            checks.append({"name": stage, "status": "failed", "reason": reason})
            for name in remaining:
                if name != stage:
                    checks.append(
                        {"name": name, "status": "skipped", "reason": "Earlier failure"}
                    )
        finally:
            budget.close()
            report["request_attempts"] = {
                **budget.counts,
                "total": budget.count,
                "cap": budget.limit,
            }
    report["counts"] = {
        status: sum(check["status"] == status for check in checks)
        for status in ("passed", "failed", "empty", "skipped")
    }
    return report


def write_report(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Do not overwrite existing user reports or private files.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


def cli(mode, argv=None):
    parser = argparse.ArgumentParser(description="Opt-in read-only Phyn diagnostics")
    parser.add_argument(
        "--env-file", help="Explicit dotenv file; never auto-discovered"
    )
    parser.add_argument(
        "--device-id",
        help="Selected device (prefer PHYN_DEVICE_ID to avoid shell history)",
    )
    parser.add_argument(
        "--days", type=_parse_day_ranges, default=[1, 7, 30] if mode == "usage" else [7]
    )
    parser.add_argument("--low-confidence-threshold", type=float, default=0.70)
    parser.add_argument("--ambiguity-gap-threshold", type=float, default=0.15)
    parser.add_argument(
        "--max-review-events",
        type=int,
        default=10,
        help="Legacy option; reports now publish aggregate review counts, not raw event identifiers",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Compare a completed UTC week against daily reads",
    )
    parser.add_argument(
        "--history-start", help="Optional completed week start, YYYY-MM-DD UTC"
    )
    parser.add_argument(
        "--report", help="New local sanitized JSON file, preferably under .artifacts"
    )
    args = parser.parse_args(argv)
    try:
        if args.history_start and not args.history:
            raise ConfigurationError("--history-start requires --history")
        config = load_configuration(args.env_file, args.device_id)
        report = asyncio.run(
            run_diagnostics(
                config,
                mode,
                args.days,
                args.low_confidence_threshold,
                args.ambiguity_gap_threshold,
                args.history,
                args.history_start,
            )
        )
        print(json.dumps(report, indent=2, allow_nan=False))
        if args.report:
            write_report(report, args.report)
        return 0 if report["status"] == "passed" else 1
    except (ConfigurationError, PayloadError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except OSError:
        print(
            "ERROR: Unable to read configuration or write the new report; check file access",
            file=sys.stderr,
        )
        return 2
