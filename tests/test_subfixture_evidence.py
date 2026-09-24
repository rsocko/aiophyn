"""Synthetic join feasibility cases; no account data or new SDK identity contract."""

from copy import deepcopy
import json
from unittest.mock import AsyncMock

import pytest

from aiophyn.device import Device
from aiophyn.home_inventory import HomeInventory
from examples.subfixture_evidence import (
    analyze, event_join, inventory_changes, inventory_index,
)
from examples.test_water_usage_events import PayloadError


def inventory(category=7, identity=101, name="Private synthetic fixture", active=True):
    return {"list": [{
        "home_inventory_type_id": category, "count": 1, "name": "Sink",
        "sub_fixtures": [{"id": identity, "name": name, "active": active}],
    }]}


def event(category=7, subfixture=101):
    return {
        "id": "private-event", "total_flow": 3,
        "open_edge_timestamp": 10, "close_edge_timestamp": 20,
        "latest_suggested_fixtures_result": {"suggested_fixtures": [{
            "fixture_id": category, "sub_fixture_id": subfixture,
            "fixture_name": "Sink", "confidence_score": 0.9,
        }]},
    }


def classify(item, payload=None, device="device-a"):
    return event_join(device, item, inventory_index("device-a", payload or inventory()))


@pytest.mark.parametrize("value", [101, "101", "00101", " 101 "])
def test_integer_and_digit_string_normalization(value):
    assert classify(event(subfixture=value))["classification"] == "joinable"


@pytest.mark.parametrize("value", [True, False, -1, 101.0, "", "1.0", "bad", {}, []])
def test_invalid_subfixture_ids_are_not_silently_joined(value):
    assert classify(event(subfixture=value))["classification"] == "invalid_or_ambiguous"


@pytest.mark.parametrize("value", [None, 0, "0", 999])
def test_missing_zero_and_unmapped_ids_retain_category_only(value):
    result = classify(event(subfixture=value))
    assert result["classification"] == "category_only"
    assert result["instance_key"] is None


def test_no_singleton_name_or_top_level_id_inference():
    item = event()
    del item["latest_suggested_fixtures_result"]["suggested_fixtures"][0]["sub_fixture_id"]
    item["sub_fixture_id"] = 101
    result = classify(item)
    assert result["classification"] == "category_only"
    assert result["subfixture_id_state"] == "missing"


def test_zero_inventory_id_is_observed_not_proven_physical_identity():
    result = classify(event(subfixture=0), inventory(identity=0))
    assert result["reason"] == "zero_subfixture_id_semantics_unverified"
    assert result["classification"] == "invalid_or_ambiguous"


def test_cross_device_collision_cannot_join():
    result = classify(event(), device="device-b")
    assert result["classification"] == "invalid_or_ambiguous"
    assert result["instance_key"] is None


def test_cross_category_collision_cannot_supply_instance():
    payload = inventory(category=8)
    payload["list"].append({"home_inventory_type_id": 7, "name": "Sink", "count": 1})
    result = classify(event(), payload)
    assert result["classification"] == "category_only"
    assert result["reason"] == "unmatched_subfixture_id"


def test_same_numeric_id_under_two_categories_has_distinct_scoped_keys():
    payload = inventory()
    payload["list"].extend(inventory(category=8)["list"])
    first = classify(event(), payload)
    second = classify(event(category=8), payload)
    assert first["classification"] == second["classification"] == "joinable"
    assert first["instance_key"] != second["instance_key"]


@pytest.mark.parametrize("duplicate", ["category", "instance"])
def test_duplicate_identity_is_ambiguous(duplicate):
    payload = inventory()
    if duplicate == "category":
        payload["list"] *= 2
    else:
        payload["list"][0]["sub_fixtures"] *= 2
    assert classify(event(), payload)["classification"] == "invalid_or_ambiguous"


def test_inactive_and_renamed_rows_do_not_change_identity_or_drop_volume():
    before = inventory()
    after = inventory(name="Different private name", active=False)
    initial = classify(event(), before)
    current = classify(event(), after)
    assert initial["instance_key"] == current["instance_key"]
    assert current["classification"] == "joinable"
    assert current["inactive_instance"]
    assert inventory_changes("device-a", before, after) == {
        "instance_keys_added": 0, "instance_keys_removed": 0,
        "instance_names_changed": 1, "instance_activity_changed": 1,
    }


def test_user_choice_never_borrows_model_subfixture():
    item = event()
    item["latest_user_feedback"] = {"fixture_id": 7}
    result = classify(item)
    assert result["classification"] == "category_only"
    assert result["source"] == "user_feedback"
    item["latest_user_feedback"]["sub_fixture_id"] = 101
    item["latest_suggested_fixtures_result"]["suggested_fixtures"][0]["fixture_id"] = 8
    assert classify(item)["classification"] == "joinable"


def test_orphan_user_instance_is_not_combined_with_model_parent():
    item = event()
    item["latest_user_feedback"] = {"sub_fixture_id": 101}
    assert classify(item)["reason"] == "orphan_user_subfixture_id"


def test_highest_confidence_owns_id_and_distinct_ties_are_ambiguous():
    item = event(subfixture=999)
    predictions = item["latest_suggested_fixtures_result"]["suggested_fixtures"]
    predictions[0]["confidence_score"] = 0.2
    predictions.append(dict(predictions[0], sub_fixture_id=101, confidence_score=0.9))
    assert classify(item)["classification"] == "joinable"
    predictions[0]["confidence_score"] = 0.9
    assert classify(item)["reason"] == "tied_distinct_fixture_identities"


def test_user_choice_survives_invalid_optional_prediction_metadata():
    item = event()
    item["latest_user_feedback"] = {"fixture_id": 7, "sub_fixture_id": 101}
    item["latest_suggested_fixtures_result"] = []
    assert classify(item)["classification"] == "joinable"


def test_bidirectional_counts_volume_and_redaction():
    payload = inventory()
    payload["list"][0]["sub_fixtures"].append(
        {"id": 102, "name": "Another private fixture", "active": True}
    )
    rows = [event(), dict(event(subfixture=None), id="second", total_flow=2)]
    original = deepcopy((payload, rows))
    result = analyze("device-a", payload, rows, 0, 100)
    assert result["coverage"]["joinable"] == {
        "event_count": 1, "gallons": 3, "event_fraction": 0.5, "volume_fraction": 0.6
    }
    assert result["coverage"]["category_only"]["volume_fraction"] == 0.4
    assert result["inventory"]["named_instance_keys_with_events"] == 1
    assert result["inventory"]["named_instance_keys_without_events"] == 1
    assert sum(row["gallons"] for row in result["coverage"].values()) == 5
    text = json.dumps(result)
    for value in ("Private", "private-event", "device-a", "101", "102"):
        assert value not in text
    assert (payload, rows) == original


def test_no_instances_is_not_evidence_of_zero_water_use():
    payload = inventory()
    del payload["list"][0]["sub_fixtures"]
    result = analyze("device-a", payload, [event()], 0, 100)
    assert result["inventory"]["named_instance_rows"] == 0
    assert result["coverage"]["category_only"]["gallons"] == 3
    empty = analyze("device-a", payload, [], 0, 100)
    assert empty["coverage"]["joinable"]["volume_fraction"] is None


def test_unconfigured_inventory_count_does_not_gate_event_volume():
    payload = inventory()
    payload["list"][0]["count"] = 0
    result = analyze("device-a", payload, [event()], 0, 100)
    assert result["coverage"]["joinable"]["gallons"] == 3
    assert result["provisional_events_in_unconfigured_categories"]["gallons"] == 3
    assert result["inventory"]["unconfigured_categories_with_provisional_events"] == 1


@pytest.mark.parametrize("invalid", [False, "", -1, "1.5", None])
def test_invalid_inventory_identity_cannot_map(invalid):
    payload = inventory(identity=invalid)
    result = analyze("device-a", payload, [event()], 0, 100)
    assert result["inventory"]["invalid_rows"] == {"invalid_subfixture_id": 1}
    assert result["coverage"]["joinable"]["event_count"] == 0


def test_identical_duplicates_and_boundary_ownership_are_not_double_counted():
    original = event()
    outside = dict(event(), id="outside", open_edge_timestamp=100, close_edge_timestamp=110)
    result = analyze("device-a", inventory(), [original, deepcopy(original), outside], 0, 100)
    assert result["event_count"] == 1
    assert result["total_gallons"] == 3


def test_conflicting_duplicate_events_fail_instead_of_double_counting():
    with pytest.raises(PayloadError, match="Conflicting duplicate"):
        analyze("device-a", inventory(), [event(), dict(event(), total_flow=99)], 0, 100)


@pytest.mark.asyncio
async def test_sdk_preserves_optional_subfixture_metadata_verbatim():
    usage = [event(subfixture="00101")]
    usage[0]["latest_user_feedback"] = {"fixture_id": 7, "sub_fixture_id": 0}
    request = AsyncMock(return_value=usage)
    assert await Device(request).get_water_usage_events(
        "device-a", from_ts=0, to_ts=100
    ) is usage
    payload = inventory()
    request.return_value = payload
    assert await HomeInventory(request).get_device_inventory("device-a") is payload
