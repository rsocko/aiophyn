"""Synthetic fixtures only; expected volumes are hand-calculated."""

import ast
import argparse
import asyncio
import builtins
from contextlib import nullcontext
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import sys

import pytest

from examples import diagnostics as diag
from examples.test_water_usage_events import (
    PayloadError,
    _classify_event_quality,
    _parse_day_ranges,
    summarize_usage,
)


def event(flow=2, suggestions=True):
    result = {
        "id": "synthetic-event",
        "total_flow": flow,
        "open_edge_timestamp": 1000,
        "close_edge_timestamp": 2000,
    }
    if suggestions:
        result["latest_suggested_fixtures_result"] = {
            "suggested_fixtures": [
                {"fixture_id": 7, "fixture_name": "Sink", "confidence_score": 0.8},
            ]
        }
    return result


@pytest.mark.parametrize(
    "prediction",
    ["absent", None, {}, {"suggested_fixtures": None}, {"suggested_fixtures": []}],
)
def test_classified_plus_unknown_total_is_five(prediction):
    unknown = event(3, False)
    if prediction != "absent":
        unknown["latest_suggested_fixtures_result"] = prediction
    result = summarize_usage([event(), unknown])
    assert result["total_gallons"] == 5
    assert result["event_count"] == 2
    assert result["fixtures"]["Sink"]["total_gallons"] == 2
    assert result["fixtures"]["Unknown"] == {
        "total_gallons": 3,
        "event_count": 1,
        "average_confidence": None,
    }
    assert result["label"] == "Predicted fixture usage"


def test_empty_is_not_a_zero_volume_event():
    assert summarize_usage([])["status"] == "empty"
    result = summarize_usage([event(0)])
    assert result["status"] == "passed"
    assert result["total_gallons"] == 0
    assert result["event_count"] == 1


@pytest.mark.parametrize("value", [None, True, {}, [], "bad", "NaN", float("inf"), -1])
@pytest.mark.parametrize("field", ["total_flow", "confidence_score"])
def test_bad_numbers_are_not_zero_success(value, field):
    item = event()
    if field == "total_flow":
        item[field] = value
    else:
        item["latest_suggested_fixtures_result"]["suggested_fixtures"][0][field] = value
    with pytest.raises(PayloadError, match=field):
        summarize_usage([item])


@pytest.mark.parametrize(
    "low,gap", [(-1, 0.15), (1.1, 0.15), (0.7, float("nan")), (0.7, 2)]
)
def test_invalid_thresholds_rejected_even_for_empty_data(low, gap):
    with pytest.raises(PayloadError):
        summarize_usage([], low, gap)


def test_strict_threshold_boundary_and_feedback_does_not_override_prediction():
    item = event()
    item["latest_suggested_fixtures_result"]["suggested_fixtures"] = [
        {"fixture_id": 7, "fixture_name": "Sink", "confidence_score": 0.7},
        {"fixture_id": 8, "fixture_name": "Toilet", "confidence_score": 0.55},
    ]
    item["latest_user_feedback"] = {"fixture_id": 8, "tell_us": "private kitchen name"}
    quality = _classify_event_quality(item, 0.7, 0.15)
    assert quality["confidence_gap"] == 0.15
    assert not quality["is_low_confidence"]
    assert not quality["is_ambiguous"]
    assert quality["feedback_conflict"]
    result = summarize_usage([item], 0.71, 0.16)
    assert result["fixtures"]["Sink"]["total_gallons"] == 2
    assert result["low_confidence_events"] == result["ambiguous_events"] == 1
    assert result["feedback_conflicts"] == 1
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "change",
    [
        {"latest_suggested_fixtures_result": []},
        {"latest_user_feedback": "bad"},
        {"latest_suggested_fixtures_result": {"suggested_fixtures": {}}},
        {"latest_suggested_fixtures_result": {"suggested_fixtures": [None]}},
    ],
)
def test_malformed_containers_fail(change):
    with pytest.raises(PayloadError):
        summarize_usage([dict(event(), **change)])


def test_numeric_strings_and_confidence_range():
    result = summarize_usage([event("2.5")])
    assert result["total_gallons"] == 2.5
    item = event()
    item["latest_suggested_fixtures_result"]["suggested_fixtures"][0][
        "confidence_score"
    ] = 1.01
    with pytest.raises(PayloadError):
        summarize_usage([item])


def test_event_contract_rejects_empty_identifier():
    item = event()
    item["id"] = item["event_id"] = ""
    with pytest.raises(PayloadError, match="nonempty"):
        diag.contract_summary([item], "events")


def test_safe_report_does_not_include_custom_names():
    item = event()
    item["latest_suggested_fixtures_result"]["suggested_fixtures"][0][
        "fixture_name"
    ] = "Private household address"
    result = diag.safe_usage([item], 0.7, 0.15)
    assert "Private" not in json.dumps(result)
    assert result["fixtures"]["Unpublished custom predictions"]["total_gallons"] == 2


@pytest.mark.parametrize(
    "module",
    [
        "test_api",
        "test_alerts",
        "test_comprehensive",
        "test_home_inventory",
        "test_water_usage_events",
        "test_mqtt",
        "diagnostics",
        "history",
    ],
)
def test_example_imports_are_inert(monkeypatch, module):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "Import attempted runtime credential loading, argument parsing or execution"
        )

    monkeypatch.setattr(asyncio, "run", forbidden)
    monkeypatch.setattr("argparse.ArgumentParser.parse_args", forbidden)
    monkeypatch.setattr(diag, "load_configuration", forbidden)
    original_getitem = os._Environ.__getitem__

    def guarded_getitem(environment, key):
        if key.startswith("PHYN_"):
            forbidden()
        return original_getitem(environment, key)

    monkeypatch.setattr(os._Environ, "__getitem__", guarded_getitem)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in ("config", "dotenv"):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    module_object = importlib.import_module("examples." + module)
    source = Path(module_object.__file__).read_text(encoding="utf-8")
    ast.parse(source, feature_version=(3, 9))
    # Execute fresh module globals without replacing shared exception classes.
    exec(
        compile(source, module_object.__file__, "exec"),
        {
            "__name__": module_object.__name__,
            "__package__": "examples",
            "__file__": module_object.__file__,
        },
    )


def test_config_only_loads_environment_at_runtime(monkeypatch):
    monkeypatch.setenv("PHYN_USERNAME", "synthetic-user")
    monkeypatch.setenv("PHYN_PASSWORD", "synthetic-password")
    monkeypatch.setenv("PHYN_DEVICE_ID", "synthetic-device")
    result = diag.load_configuration()
    assert result.username == "synthetic-user"
    assert result.device_id == "synthetic-device"
    assert "synthetic" not in repr(result)


def test_dotenv_is_only_used_when_explicit_and_environment_wins(monkeypatch, tmp_path):
    for key in ("PHYN_USERNAME", "PHYN_PASSWORD", "PHYN_BRAND", "PHYN_DEVICE_ID"):
        monkeypatch.delenv(key, raising=False)
    values = Mock(
        return_value={
            "PHYN_USERNAME": "synthetic-file-user",
            "PHYN_PASSWORD": "synthetic-file-password",
        }
    )
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(dotenv_values=values))
    monkeypatch.setenv("PHYN_USERNAME", "synthetic-env-user")
    monkeypatch.setenv("PHYN_PASSWORD", "synthetic-env-password")
    diag.load_configuration()
    values.assert_not_called()
    file = tmp_path / ".env.live"
    file.write_text("# synthetic configuration only\n", encoding="utf-8")
    result = diag.load_configuration(str(file))
    values.assert_called_once_with(file, interpolate=False)
    assert result.username == "synthetic-env-user"
    assert result.password == "synthetic-env-password"


def test_optional_dotenv_missing_has_actionable_failure(monkeypatch, tmp_path):
    file = tmp_path / ".env.live"
    file.write_text("# synthetic configuration only\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "dotenv", None)
    with pytest.raises(diag.ConfigurationError, match="pip install python-dotenv"):
        diag.load_configuration(str(file))


def test_missing_config_returns_nonzero_without_auth(monkeypatch, capsys):
    monkeypatch.delenv("PHYN_USERNAME", raising=False)
    monkeypatch.delenv("PHYN_PASSWORD", raising=False)
    assert diag.cli("usage", []) == 2
    assert "PHYN_USERNAME" in capsys.readouterr().err


@pytest.fixture
def synthetic_api(monkeypatch):
    api = SimpleNamespace(
        home=SimpleNamespace(
            get_homes=AsyncMock(
                return_value=[
                    {
                        "id": "private-home",
                        "address": "private-address",
                        "devices": [{"device_id": "synthetic-device"}],
                    },
                ]
            )
        ),
        device=SimpleNamespace(
            get_water_usage_events=AsyncMock(return_value=[event()])
        ),
        home_inventory=SimpleNamespace(
            get_fixture_types=AsyncMock(return_value=[{"home_inventory_type_id": 7}]),
            get_device_inventory=AsyncMock(
                return_value={"list": [{"home_inventory_type_id": 7, "count": 2}]}
            ),
        ),
    )
    monkeypatch.setattr(diag, "async_get_api", AsyncMock(return_value=api))
    monkeypatch.setattr(diag, "bounded_cognito", lambda budget: nullcontext())
    return api


@pytest.mark.asyncio
async def test_diagnostic_contracts_and_sanitized_output(synthetic_api):
    report = await diag.run_diagnostics(
        diag.Configuration("private-user", "private-password")
    )
    assert report["status"] == "passed"
    assert report["counts"] == {"passed": 5, "failed": 0, "empty": 0, "skipped": 1}
    assert "private" not in json.dumps(report)
    assert "synthetic-device" not in json.dumps(report)


@pytest.mark.asyncio
async def test_auth_failure_is_failed_not_zero_failed(monkeypatch, synthetic_api):
    monkeypatch.setattr(
        diag, "async_get_api", AsyncMock(side_effect=RuntimeError("private-token"))
    )
    report = await diag.run_diagnostics(
        diag.Configuration("synthetic", "synthetic"), "comprehensive"
    )
    assert report["status"] == "failed"
    assert report["counts"]["failed"] == 1
    assert report["counts"]["skipped"] == 9
    assert "private-token" not in json.dumps(report)


@pytest.mark.asyncio
async def test_discovery_empty_is_incomplete_not_success(synthetic_api):
    synthetic_api.home.get_homes.return_value = []
    report = await diag.run_diagnostics(diag.Configuration("synthetic", "synthetic"))
    assert report["status"] == "incomplete"
    assert report["counts"]["empty"] == 1
    assert report["counts"]["skipped"] == 3


@pytest.mark.asyncio
async def test_empty_events_are_explicit(synthetic_api):
    synthetic_api.device.get_water_usage_events.return_value = []
    report = await diag.run_diagnostics(diag.Configuration("synthetic", "synthetic"))
    assert report["status"] == "passed"
    assert report["counts"]["empty"] == 1


@pytest.mark.asyncio
async def test_failed_window_is_not_empty_success(synthetic_api):
    synthetic_api.device.get_water_usage_events.side_effect = RuntimeError(
        "private-token"
    )
    report = await diag.run_diagnostics(diag.Configuration("synthetic", "synthetic"))
    assert report["status"] == "failed"
    assert report["counts"]["empty"] == 0
    assert "private-token" not in json.dumps(report)


@pytest.mark.asyncio
async def test_transport_guard_failure_is_actionable(synthetic_api):
    synthetic_api.device.get_water_usage_events.side_effect = diag.DiagnosticError(
        "Read-only request budget exhausted or closed; run aborted"
    )
    report = await diag.run_diagnostics(diag.Configuration("synthetic", "synthetic"))
    assert report["status"] == "failed"
    assert "request budget exhausted" in json.dumps(report)


@pytest.mark.asyncio
async def test_operation_timeout_aborts_and_redacts(synthetic_api, monkeypatch):
    async def slow(*args):
        await asyncio.sleep(1)

    synthetic_api.home.get_homes.side_effect = slow
    monkeypatch.setattr(diag, "OPERATION_TIMEOUT", 0.001)
    report = await diag.run_diagnostics(diag.Configuration("synthetic", "synthetic"))
    assert report["status"] == "failed"
    assert report["counts"]["failed"] == 1
    assert report["counts"]["skipped"] == 3
    assert "timed out" in json.dumps(report)


@pytest.mark.asyncio
async def test_history_configuration_fails_before_auth(synthetic_api):
    with pytest.raises(diag.ConfigurationError, match="explicit"):
        await diag.run_diagnostics(
            diag.Configuration("synthetic", "synthetic"), history=True
        )
    with pytest.raises(ValueError, match="completed"):
        await diag.run_diagnostics(
            diag.Configuration("synthetic", "synthetic", device_id="synthetic-device"),
            history=True,
            history_start="2999-01-01",
        )
    diag.async_get_api.assert_not_awaited()


def test_report_refuses_overwrite(tmp_path):
    path = tmp_path / "report.json"
    diag.write_report({"status": "passed"}, path)
    with pytest.raises(FileExistsError):
        diag.write_report({"status": "failed"}, path)
    assert json.loads(path.read_text())["status"] == "passed"


def test_day_ranges_are_bounded():
    assert _parse_day_ranges("7,1,7") == [1, 7]
    for value in ("0,1", "32", "1,2,3,4", "abc", "1,"):
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_day_ranges(value)
