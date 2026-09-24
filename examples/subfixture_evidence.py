"""Conservative inventory/event join evidence, not a statistics implementation."""

from collections import Counter, defaultdict
import math

from .test_water_usage_events import (
    PayloadError, _classify_event_quality, fixture_id, number,
)


def inventory_index(device_id, inventory):
    """Keep identity device/category scoped; labels never establish identity."""
    if not isinstance(device_id, str) or not device_id:
        raise PayloadError("Inventory requires a device scope")
    if not isinstance(inventory, dict) or not isinstance(inventory.get("list"), list):
        raise PayloadError("Inventory requires a list")
    categories, instances = defaultdict(list), defaultdict(list)
    errors = Counter()
    named = configured = zero_ids = 0
    for row in inventory["list"]:
        if not isinstance(row, dict):
            raise PayloadError("Inventory category must be an object")
        try:
            category = fixture_id(row.get("home_inventory_type_id"))
            if category is None:
                raise PayloadError("Inventory category requires an ID")
        except PayloadError:
            errors["invalid_category_id"] += 1
            continue
        count = number(row.get("count"), "inventory count")
        if not count.is_integer():
            raise PayloadError("Inventory count must be an integer")
        configured += count > 0
        categories[(device_id, category)].append(row)
        children = row.get("sub_fixtures")
        if children is None:
            children = []
        if not isinstance(children, list):
            raise PayloadError("sub_fixtures must be a list or null")
        for child in children:
            if not isinstance(child, dict):
                raise PayloadError("Each sub-fixture must be an object")
            named += isinstance(child.get("name"), str) and bool(child["name"].strip())
            try:
                identity = fixture_id(child.get("id"))
                if identity is None:
                    raise PayloadError("Inventory sub-fixture requires an ID")
            except PayloadError:
                errors["invalid_subfixture_id"] += 1
                continue
            zero_ids += identity == 0
            instances[(device_id, category, identity)].append(child)
    return {
        "categories": categories,
        "instances": instances,
        "counts": {
            "category_rows": len(inventory["list"]),
            "unique_category_keys": len(categories),
            "configured_category_rows": configured,
            "instance_rows_with_valid_id": sum(map(len, instances.values())),
            "named_instance_rows": named,
            "unique_instance_keys": len(instances),
            "duplicate_category_keys": sum(len(rows) > 1 for rows in categories.values()),
            "duplicate_instance_keys": sum(len(rows) > 1 for rows in instances.values()),
            "zero_instance_id_rows": zero_ids,
            "invalid_rows": dict(errors),
        },
    }


def event_join(device_id, event, index):
    """Return a potential exact-ID join; no singleton/name-only inference."""
    flow = number(event.get("total_flow"), "total_flow")
    result = {
        "classification": "invalid_or_ambiguous",
        "reason": "invalid_attribution_metadata",
        "source": "invalid",
        "gallons": flow,
        "category_key": None,
        "instance_key": None,
        "inactive_instance": False,
        "subfixture_id_state": "not_selected",
    }
    try:
        quality = _classify_event_quality(event, 0.7, 0.15)
    except PayloadError:
        return result
    result["source"] = quality["attribution_source"]
    category = quality["attributed_fixture_id"]
    if category is None:
        result["reason"] = "no_effective_category_id"
        return result
    category_key = (device_id, category)
    rows = index["categories"].get(category_key, [])
    if len(rows) != 1:
        result["reason"] = "unknown_category" if not rows else "duplicate_category_id"
        return result
    result["category_key"] = category_key
    if quality["attribution_source"] == "user_feedback":
        selected = event["latest_user_feedback"]
    else:
        suggestions = event["latest_suggested_fixtures_result"]["suggested_fixtures"]
        highest = [
            row for row in suggestions
            if number(row.get("confidence_score"), "confidence_score", 1)
            == quality["top_confidence"]
        ]
        try:
            identities = {
                (fixture_id(row.get("fixture_id")), fixture_id(row.get("sub_fixture_id")))
                for row in highest
            }
        except PayloadError:
            result["reason"] = "invalid_subfixture_id"
            result["subfixture_id_state"] = "invalid"
            return result
        if len(identities) != 1:
            result["reason"] = "tied_distinct_fixture_identities"
            return result
        selected = highest[0]
        feedback = event.get("latest_user_feedback") or {}
        if feedback.get("fixture_id") is None and feedback.get("sub_fixture_id") is not None:
            result["reason"] = "orphan_user_subfixture_id"
            return result
    value = selected.get("sub_fixture_id")
    result["subfixture_id_state"] = (
        "missing" if "sub_fixture_id" not in selected else "null"
    )
    result.update(classification="category_only", reason="no_selected_subfixture_id")
    if value is None:
        return result
    try:
        identity = fixture_id(value)
    except PayloadError:
        result.update(
            classification="invalid_or_ambiguous",
            reason="invalid_subfixture_id", subfixture_id_state="invalid",
        )
        return result
    result["subfixture_id_state"] = "zero" if identity == 0 else "nonzero"
    key = (device_id, category, identity)
    matches = index["instances"].get(key, [])
    if not matches:
        result["reason"] = (
            "zero_subfixture_id_unmapped" if identity == 0 else "unmatched_subfixture_id"
        )
    elif identity == 0:
        # A matching zero is not proof that zero denotes an individual fixture.
        result.update(
            classification="invalid_or_ambiguous",
            reason="zero_subfixture_id_semantics_unverified",
        )
    elif len(matches) > 1:
        result.update(
            classification="invalid_or_ambiguous", reason="duplicate_subfixture_id"
        )
    else:
        result.update(
            classification="joinable", reason="unique_scoped_id",
            instance_key=key, inactive_instance=matches[0].get("active") is False,
        )
    return result


def index_events(events, start, end):
    """Deduplicate only identical records under local half-open ownership."""
    if not isinstance(events, list):
        raise PayloadError("Events must be a list")
    result = {}
    for event in events:
        if not isinstance(event, dict):
            raise PayloadError("Each event must be an object")
        identity = event.get("id") or event.get("event_id")
        if not isinstance(identity, str) or not identity:
            raise PayloadError("Event requires an ID")
        opened = number(event.get("open_edge_timestamp"), "event start")
        closed = number(event.get("close_edge_timestamp"), "event end")
        if closed < opened:
            raise PayloadError("Event closes before opening")
        if not start <= opened < end:
            continue
        if identity in result and result[identity] != event:
            raise PayloadError("Conflicting duplicate event")
        result[identity] = event
    return result


def analyze(device_id, inventory, events, start, end):
    """Only aggregate counts/volumes leave this function; identifiers stay private."""
    indexed = inventory_index(device_id, inventory)
    selected = index_events(events, start, end)
    joins = [event_join(device_id, event, indexed) for event in selected.values()]
    total = math.fsum(item["gallons"] for item in joins)
    count = len(joins)

    def fraction(rows):
        gallons = math.fsum(item["gallons"] for item in rows)
        return {
            "event_count": len(rows), "gallons": gallons,
            "event_fraction": len(rows) / count if count else None,
            "volume_fraction": gallons / total if total else None,
        }

    categories = {item["category_key"] for item in joins if item["category_key"]}
    unambiguous_categories = {
        item["category_key"] for item in joins
        if item["classification"] != "invalid_or_ambiguous"
    }
    instances = {item["instance_key"] for item in joins if item["instance_key"]}
    named_keys = {
        key for key, rows in indexed["instances"].items()
        if any(isinstance(row.get("name"), str) and row["name"].strip() for row in rows)
    }
    configured_keys = {
        key for key, rows in indexed["categories"].items()
        if any(number(row["count"], "inventory count") > 0 for row in rows)
    }
    return {
        "event_count": count, "total_gallons": total,
        "inventory": dict(
            indexed["counts"],
            categories_with_provisionally_attributed_events=len(categories),
            categories_without_provisionally_attributed_events=len(
                indexed["categories"].keys() - categories
            ),
            categories_with_unambiguous_events=len(unambiguous_categories),
            configured_categories_with_provisional_events=len(categories & configured_keys),
            unconfigured_categories_with_provisional_events=len(categories - configured_keys),
            named_instance_keys_with_events=len(named_keys & instances),
            named_instance_keys_without_events=len(named_keys - instances),
        ),
        "coverage": {
            label: fraction([item for item in joins if item["classification"] == label])
            for label in ("joinable", "category_only", "invalid_or_ambiguous")
        },
        "sources": {
            label: fraction([item for item in joins if item["source"] == label])
            for label in ("user_feedback", "prediction", "unknown", "invalid")
        },
        "reason_counts": dict(Counter(item["reason"] for item in joins)),
        "selected_subfixture_id_states": dict(
            Counter(item["subfixture_id_state"] for item in joins)
        ),
        "events_joined_to_inactive_instances": sum(item["inactive_instance"] for item in joins),
        "provisional_events_in_unconfigured_categories": fraction([
            item for item in joins
            if item["category_key"] is not None
            and item["category_key"] not in configured_keys
        ]),
        "limitations": [
            "Exact-ID joins are observed candidate relationships, not server identity guarantees.",
            "Zero IDs are reported, not assumed to be a sentinel or a physical instance.",
            "No singleton counts, names, top-level IDs, or unrelated predictions supply a missing ID.",
            "Only selected feedback or highest-confidence candidate supplies a sub-fixture ID.",
            "Current inventory cannot establish historical naming, activity, or ID stability.",
        ],
    }


def inventory_changes(device_id, before, after):
    first = inventory_index(device_id, before)["instances"]
    last = inventory_index(device_id, after)["instances"]
    comparable = {
        key for key in first.keys() & last.keys()
        if len(first[key]) == len(last[key]) == 1
    }
    return {
        "instance_keys_added": len(last.keys() - first.keys()),
        "instance_keys_removed": len(first.keys() - last.keys()),
        "instance_names_changed": sum(
            first[key][0].get("name") != last[key][0].get("name") for key in comparable
        ),
        "instance_activity_changed": sum(
            first[key][0].get("active") != last[key][0].get("active") for key in comparable
        ),
    }
