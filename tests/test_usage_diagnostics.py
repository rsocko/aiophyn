"""Synthetic fixtures only; expected volumes are hand-calculated."""

import ast
import argparse
import asyncio
import builtins
from contextlib import nullcontext
from datetime import timedelta
import importlib
from itertools import permutations
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call
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
    assert result["label"] == "Attributed fixture usage"
    assert result["attribution_counts"] == {
        "user_feedback": 0, "prediction": 1, "unknown": 1
    }


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


def test_user_feedback_overrides_prediction_without_inheriting_model_confidence():
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
    assert quality["attributed_fixture"] == "Toilet"
    assert quality["attribution_source"] == "user_feedback"
    assert quality["attributed_confidence"] is None
    assert not quality["needs_review"]
    result = summarize_usage([item], 0.71, 0.16)
    assert result["fixtures"]["Toilet"]["total_gallons"] == 2
    assert result["fixtures"]["Toilet"]["average_confidence"] is None
    assert "Sink" not in result["fixtures"]
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


@pytest.mark.parametrize("scores", [(0.2, 0.8), (0.8, 0.1, 0.9)])
def test_unordered_predictions_use_highest_confidence_and_preserve_input(scores):
    item = event(3)
    suggestions = [
        {
            "fixture_id": index + 7,
            "fixture_name": "Sink" if index == 0 else "Toilet",
            "confidence_score": score,
        }
        for index, score in enumerate(scores)
    ]
    item["latest_suggested_fixtures_result"]["suggested_fixtures"] = suggestions
    original = json.dumps(item)
    quality = _classify_event_quality(item, 0.7, 0.15)
    assert quality["top_fixture"] == "Toilet"
    assert quality["top_confidence"] == max(scores)
    assert quality["attribution_source"] == "prediction"
    expected_gap = sorted(scores, reverse=True)[0] - sorted(scores, reverse=True)[1]
    assert quality["confidence_gap"] == pytest.approx(expected_gap)
    assert quality["unordered_confidence"]
    assert quality["needs_review"]
    assert "unordered_confidence" in quality["review_reasons"]
    summary = diag.safe_usage([item], 0.7, 0.15)
    assert summary["total_gallons"] == 3
    assert summary["fixtures"]["Toilet"]["total_gallons"] == 3
    assert "Sink" not in summary["fixtures"]
    assert summary["unordered_prediction_events"] == 1
    assert summary["review_events"] == 1
    assert diag.contract_summary([item], "events")["status"] == "passed"
    assert json.dumps(item) == original


def test_equal_or_descending_confidence_is_not_flagged_unordered():
    item = event()
    suggestions = item["latest_suggested_fixtures_result"]["suggested_fixtures"]
    suggestions.extend([
        {"fixture_name": "Toilet", "confidence_score": 0.8},
        {"fixture_name": "Other", "confidence_score": 0.2},
    ])
    assert summarize_usage([item])["unordered_prediction_events"] == 0
    assert summarize_usage([event(suggestions=False)])["unordered_prediction_events"] == 0


ATTRIBUTION_CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "attribution_cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", ATTRIBUTION_CASES, ids=lambda case: case["name"])
def test_shared_attribution_contract(case):
    item = case["event"]
    before = json.dumps(item, sort_keys=True)
    catalog = {int(key): value for key, value in case.get("catalog", {}).items()}
    if "expected_error" in case:
        with pytest.raises(PayloadError, match=case["expected_error"]):
            _classify_event_quality(item, 0.7, 0.15, catalog)
    else:
        result = _classify_event_quality(item, 0.7, 0.15, catalog)
        for key, expected in case["expected"].items():
            assert result[key] == expected, key
        summary = diag.safe_usage([item], 0.7, 0.15, catalog)
        assert summary["total_gallons"] == 2
        assert sum(entry["total_gallons"] for entry in summary["fixtures"].values()) == 2
        assert summary["attribution_counts"][result["attribution_source"]] == 1
        assert summary["invalid_prediction_events"] == int(result["invalid_prediction_metadata"])
        assert "Private" not in json.dumps(summary)
    assert json.dumps(item, sort_keys=True) == before


@pytest.mark.parametrize("scores", permutations([0.9, 0.4, 0.8]))
def test_highest_score_and_ranked_gap_are_order_independent(scores):
    item = event()
    item["latest_suggested_fixtures_result"]["suggested_fixtures"] = [
        {"fixture_id": int(score * 10), "confidence_score": score}
        for score in scores
    ]
    result = _classify_event_quality(item, 0.7, 0.15)
    assert result["attributed_fixture_id"] == 9
    assert result["attributed_confidence"] == 0.9
    assert result["confidence_gap"] == 0.1


def test_tie_requires_review_even_when_ambiguity_threshold_is_zero():
    item = event()
    item["latest_suggested_fixtures_result"]["suggested_fixtures"].append(
        {"fixture_id": 8, "fixture_name": "Toilet", "confidence_score": 0.8}
    )
    result = _classify_event_quality(item, 0, 0)
    assert result["attributed_fixture"] == "Sink"
    assert result["review_reasons"] == ["tied_highest_confidence"]


@pytest.mark.parametrize("feedback", [None, {}])
def test_empty_feedback_does_not_request_review(feedback):
    result = _classify_event_quality(
        dict(event(), latest_user_feedback=feedback), 0.7, 0.15
    )
    assert result["attribution_source"] == "prediction"
    assert result["review_reasons"] == []
    assert not result["has_user_feedback"]


@pytest.mark.parametrize("identity", [True, -1, 1.5, {}, [], "bad", "-1", " ", "1.5"])
def test_invalid_explicit_feedback_id_never_silently_falls_back(identity):
    item = dict(event(), latest_user_feedback={"fixture_id": identity})
    with pytest.raises(PayloadError, match="fixture_id"):
        summarize_usage([item])


@pytest.mark.parametrize("value", [None, True, {}, [], "bad", "NaN", "Infinity", -1, 1.01])
def test_human_selection_survives_invalid_optional_model_confidence(value):
    item = dict(event(), latest_user_feedback={"fixture_id": 8})
    item["latest_suggested_fixtures_result"]["suggested_fixtures"][0]["confidence_score"] = value
    result = diag.safe_usage([item], 0.7, 0.15)
    assert result["fixtures"]["Fixture type 8"]["total_gallons"] == 2
    assert result["attribution_counts"]["user_feedback"] == 1
    assert result["invalid_prediction_events"] == result["review_events"] == 1
    assert diag.contract_summary([item], "events")["status"] == "passed"
    item["total_flow"] = value
    if value != 1.01:
        with pytest.raises(PayloadError, match="total_flow"):
            summarize_usage([item])


def test_model_average_excludes_user_corrections_and_preserves_total():
    user = dict(event(3), latest_user_feedback={"fixture_id": "7", "sub_fixture_id": 12})
    result = summarize_usage([user, event(2), event(5, False)])
    assert result["total_gallons"] == 10
    assert result["fixtures"]["Sink"] == {
        "total_gallons": 5, "event_count": 2, "average_confidence": 0.8
    }
    assert result["fixtures"]["Unknown"]["total_gallons"] == 5
    assert result["attribution_counts"] == {"user_feedback": 1, "prediction": 1, "unknown": 1}


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
    assert result["fixtures"]["Unpublished custom labels"]["total_gallons"] == 2


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
@pytest.mark.parametrize("mode, label", [("usage", "Fixture type 8"), ("live", "Toilet")])
async def test_feedback_catalog_enrichment_uses_only_existing_reads(synthetic_api, mode, label):
    synthetic_api.home_inventory.get_fixture_types.return_value = [
        {"home_inventory_type_id": 8, "name": "Toilet"}
    ]
    synthetic_api.device.get_water_usage_events.return_value = [
        dict(event(3, False), latest_user_feedback={"fixture_id": 8})
    ]
    report = await diag.run_diagnostics(diag.Configuration("synthetic", "synthetic"), mode)
    assert report["status"] == "passed"
    usage = next(check["usage"] for check in report["checks"] if "usage" in check)
    assert usage["fixtures"][label]["total_gallons"] == 3
    assert usage["attribution_counts"]["user_feedback"] == 1
    assert synthetic_api.home_inventory.get_fixture_types.await_count == (mode == "live")
    synthetic_api.device.get_water_usage_events.assert_awaited_once()


DEVICE_IDS = ("offline-device-one", "offline-device-two")
HISTORY_START_MS = 1704067200000  # 2024-01-01 UTC
DAY_MS = 86_400_000
HISTORY_WINDOWS = [
    (HISTORY_START_MS, HISTORY_START_MS + 7 * DAY_MS),
    *[
        (HISTORY_START_MS + day * DAY_MS, HISTORY_START_MS + (day + 1) * DAY_MS)
        for day in range(7)
    ],
    (HISTORY_START_MS, HISTORY_START_MS + 7 * DAY_MS),
]


@pytest.fixture(params=["same-home", "separate-homes"])
def multi_device_api(synthetic_api, request):
    api = synthetic_api
    groups = (
        [DEVICE_IDS] if request.param == "same-home" else [(d,) for d in DEVICE_IDS]
    )
    api.home.get_homes.return_value = [
        {
            "id": f"offline-home-{index}",
            "devices": [{"device_id": device_id} for device_id in group],
            "device_ids": list(group),
        }
        for index, group in enumerate(groups)
    ]
    api.events_by_device = {
        device_id: [
            dict(
                event(flow),
                open_edge_timestamp=HISTORY_START_MS + 1000,
                close_edge_timestamp=HISTORY_START_MS + 2000,
            )
        ]
        for device_id, flow in zip(DEVICE_IDS, (2, 9))
    }
    api.history_by_device = dict(api.events_by_device)

    async def fetch(device_id, *args, **kwargs):
        rows = (
            api.history_by_device[device_id]
            if kwargs
            else api.events_by_device[device_id]
        )
        if isinstance(rows, Exception):
            raise rows
        if kwargs:
            return [
                row
                for row in rows
                if kwargs["from_ts"] <= row["open_edge_timestamp"] < kwargs["to_ts"]
            ]
        return rows

    api.device.get_water_usage_events.side_effect = fetch
    for method in (
        "get_state",
        "get_consumption",
        "get_device_preferences",
        "get_latest_firmware_info",
        "get_away_mode",
    ):
        setattr(api.device, method, AsyncMock(return_value={"synthetic": True}))
    api.alert = SimpleNamespace(
        get_latest=AsyncMock(return_value={"alerts": []}),
        get_active_summary=AsyncMock(return_value={"unresolved": 0}),
    )
    return api


def assert_comprehensive_reads(api, device_id, days, history=False):
    api.home_inventory.get_fixture_types.assert_awaited_once_with()
    api.home_inventory.get_device_inventory.assert_awaited_once_with(device_id)
    for method in (
        "get_state",
        "get_device_preferences",
        "get_latest_firmware_info",
        "get_away_mode",
    ):
        getattr(api.device, method).assert_awaited_once_with(device_id)
    reads = api.device.get_water_usage_events.await_args_list
    for read, day in zip(reads, days):
        assert read.kwargs == {}
        selected, left, right = read.args
        assert selected == device_id
        assert right - left == timedelta(days=day)
        assert right == reads[0].args[2]
    api.device.get_consumption.assert_awaited_once_with(
        device_id, reads[0].args[2].strftime("%Y/%m/%d"), details=True
    )
    assert reads[len(days) :] == (
        [call(device_id, from_ts=left, to_ts=right) for left, right in HISTORY_WINDOWS]
        if history
        else []
    )
    assert len(reads) == len(days) + (9 if history else 0)
    api.alert.get_latest.assert_not_awaited()
    api.alert.get_active_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_second_device_comprehensive_and_history(multi_device_api):
    report = await diag.run_diagnostics(
        diag.Configuration("synthetic", "synthetic", device_id=DEVICE_IDS[1]),
        "comprehensive",
        days=(1, 7, 30),
        history=True,
        history_start="2024-01-01",
    )
    assert report["status"] == "passed"
    assert all(check["status"] == "passed" for check in report["checks"])
    assert_comprehensive_reads(
        multi_device_api, DEVICE_IDS[1], (1, 7, 30), history=True
    )
    checks = {check["name"]: check for check in report["checks"]}
    for day in (1, 7, 30):
        assert checks[f"events_{day}d"]["usage"]["total_gallons"] == 9
    assert checks["history"]["total_gallons"] == {
        "weekly_before": 9,
        "daily": 9,
        "weekly_after": 9,
    }
    assert checks["history"]["consistent"] is True


@pytest.mark.asyncio
async def test_default_selection_remains_first_device(multi_device_api):
    report = await diag.run_diagnostics(
        diag.Configuration("synthetic", "synthetic"), "comprehensive"
    )
    assert report["status"] == "passed"
    assert_comprehensive_reads(multi_device_api, DEVICE_IDS[0], (7,))
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["events_7d"]["usage"]["total_gallons"] == 2
    assert checks["history"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_second_device_alerts_select_home_not_account_summary(multi_device_api):
    from aiophyn.alert import Alert

    homes = multi_device_api.home.get_homes.return_value
    report = await diag.run_diagnostics(
        diag.Configuration("synthetic", "synthetic", device_id=DEVICE_IDS[1]),
        "alerts",
    )
    assert report["status"] == "passed"
    multi_device_api.alert.get_latest.assert_awaited_once_with(
        "synthetic", homes[-1]["id"], alert_type=Alert.ALERT_TYPES
    )
    multi_device_api.alert.get_active_summary.assert_awaited_once_with(
        "synthetic", "unresolved"
    )
    for api_group in (multi_device_api.device, multi_device_api.home_inventory):
        for method in vars(api_group).values():
            method.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["comprehensive", "alerts"])
async def test_unknown_device_fails_before_reads(multi_device_api, mode):
    report = await diag.run_diagnostics(
        diag.Configuration("synthetic", "synthetic", device_id="offline-unknown"),
        mode,
        history=True,
        history_start="2024-01-01",
    )
    assert report["status"] == "failed"
    failures = [check for check in report["checks"] if check["status"] == "failed"]
    assert failures == [
        {
            "name": "device_selection",
            "status": "failed",
            "reason": "Selected device was not discovered for this account",
        }
    ]
    multi_device_api.home.get_homes.assert_awaited_once_with("synthetic")
    for api_group in (
        multi_device_api.device,
        multi_device_api.home_inventory,
        multi_device_api.alert,
    ):
        for method in vars(api_group).values():
            method.assert_not_awaited()
    assert (
        next(c for c in report["checks"] if c["name"] == "history")["status"]
        == "skipped"
    )


@pytest.mark.asyncio
async def test_per_device_usage_history_reports_isolate_shared_event_ids(
    multi_device_api, tmp_path
):
    reports = []
    snapshots = []
    for index, device_id in enumerate((*DEVICE_IDS, DEVICE_IDS[0])):
        multi_device_api.device.get_water_usage_events.reset_mock()
        report = await diag.run_diagnostics(
            diag.Configuration("synthetic", "synthetic", device_id=device_id),
            "usage",
            history=True,
            history_start="2024-01-01",
        )
        assert report["status"] == "passed"
        checks = {check["name"]: check for check in report["checks"]}
        expected = 2 if device_id == DEVICE_IDS[0] else 9
        assert checks["events_7d"]["usage"]["total_gallons"] == expected
        assert checks["events_7d"]["usage"]["event_count"] == 1
        assert checks["history"]["total_gallons"] == dict.fromkeys(
            ("weekly_before", "daily", "weekly_after"), expected
        )
        assert checks["history"]["unique_counts"] == dict.fromkeys(
            ("weekly_before", "daily", "weekly_after"), 1
        )
        assert checks["history"]["consistent"] is True
        reads = multi_device_api.device.get_water_usage_events.await_args_list
        assert len(reads) == 10
        assert reads[0].args[0] == device_id
        assert reads[1:] == [
            call(device_id, from_ts=left, to_ts=right)
            for left, right in HISTORY_WINDOWS
        ]
        path = tmp_path / f"report-{index}.json"
        diag.write_report(report, path)
        snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        reports.append(report)
    assert reports == snapshots
    assert reports[0] == reports[2]
    assert reports[0] != reports[1]
    assert reports[0] is not reports[2]
    for raw_id in (*DEVICE_IDS, "synthetic-event"):
        assert raw_id not in json.dumps(reports)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["usage", "history"])
@pytest.mark.parametrize("outcome", ["empty", "failure"])
async def test_empty_or_failed_device_does_not_contaminate_next_run(
    multi_device_api, stage, outcome
):
    responses = (
        multi_device_api.events_by_device
        if stage == "usage"
        else multi_device_api.history_by_device
    )
    responses[DEVICE_IDS[0]] = (
        [] if outcome == "empty" else RuntimeError("synthetic-private-failure")
    )
    reports = []
    for device_id in DEVICE_IDS:
        multi_device_api.device.get_water_usage_events.reset_mock()
        report = await diag.run_diagnostics(
            diag.Configuration("synthetic", "synthetic", device_id=device_id),
            "usage",
            history=True,
            history_start="2024-01-01",
        )
        reads = multi_device_api.device.get_water_usage_events.await_args_list
        assert reads
        assert all(read.args[0] == device_id for read in reads)
        if device_id == DEVICE_IDS[0] and outcome == "failure":
            assert len(reads) == (1 if stage == "usage" else 2)
        else:
            assert len(reads) == 10
            assert reads[1:] == [
                call(device_id, from_ts=left, to_ts=right)
                for left, right in HISTORY_WINDOWS
            ]
        reports.append(report)
    affected, successful = [
        {check["name"]: check for check in report["checks"]} for report in reports
    ]
    name = "events_7d" if stage == "usage" else "history"
    assert affected[name]["status"] == ("empty" if outcome == "empty" else "failed")
    assert reports[0]["status"] == ("passed" if outcome == "empty" else "failed")
    if outcome == "empty":
        if stage == "usage":
            assert affected[name]["usage"]["total_gallons"] == 0
        else:
            assert affected[name]["total_gallons"] == dict.fromkeys(
                ("weekly_before", "daily", "weekly_after"), 0
            )
    else:
        assert "usage" not in affected[name]
        assert "total_gallons" not in affected[name]
        if stage == "usage":
            assert affected["history"]["status"] == "skipped"
    assert reports[1]["status"] == "passed"
    assert successful["events_7d"]["usage"]["total_gallons"] == 9
    assert successful["history"]["total_gallons"] == dict.fromkeys(
        ("weekly_before", "daily", "weekly_after"), 9
    )
    assert successful["history"]["consistent"] is True
    assert "synthetic-private-failure" not in json.dumps(reports)


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
