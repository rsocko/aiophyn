"""User-first fixture attribution with model fallback. See docs/examples.md."""

import argparse
import math
from collections import defaultdict
from decimal import Decimal


class PayloadError(ValueError):
    """A response cannot be interpreted without inventing data."""


def number(value, field, maximum=None):
    """Validate finite, nonnegative API numbers without echoing private values."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise PayloadError(f"{field} must be a finite nonnegative number")
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise PayloadError(f"{field} must be a finite nonnegative number") from None
    if not math.isfinite(result) or result < 0:
        raise PayloadError(f"{field} must be a finite nonnegative number")
    if maximum is not None and result > maximum:
        raise PayloadError(f"{field} is outside the supported range")
    return result


def object_or_empty(value, field):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PayloadError(f"{field} must be an object or null")
    return value


def fixture_id(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value.isascii() and value.isdecimal():
            return int(value)
    elif isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise PayloadError("fixture_id must be a nonnegative integer or digit string")


def _fixture_label(identity, names, catalog):
    if identity in catalog:
        name = catalog[identity]
        if not isinstance(name, str) or not name.strip():
            raise PayloadError("Catalog fixture names must be nonempty strings")
        return name.strip(), bool(names and names != {name.strip()})
    if len(names) == 1:
        return next(iter(names)), False
    return f"Fixture type {identity}", len(names) > 1


def _model_quality(event, low, ambiguity, catalog):
    prediction = object_or_empty(
        event.get("latest_suggested_fixtures_result"),
        "latest_suggested_fixtures_result",
    )
    suggestions = prediction.get("suggested_fixtures")
    if suggestions is None:
        suggestions = []
    if not isinstance(suggestions, list):
        raise PayloadError("suggested_fixtures must be a list or null")
    confidences = []
    identities = []
    names_by_id = defaultdict(set)
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            raise PayloadError("Each suggested fixture must be an object")
        confidences.append(
            number(suggestion.get("confidence_score"), "confidence_score", 1)
        )
        identity = fixture_id(suggestion.get("fixture_id"))
        identities.append(identity)
        name = suggestion.get("fixture_name")
        if name is not None and not isinstance(name, str):
            raise PayloadError("fixture_name must be a string or null")
        if identity is not None and name and name.strip():
            names_by_id[identity].add(name.strip())
    unordered = any(
        right > left for left, right in zip(confidences, confidences[1:])
    )
    result = {
        "top_fixture": "Unknown",
        "top_fixture_id": None,
        "top_confidence": None,
        "algorithm": "unknown",
        "confidence_gap": None,
        "is_low_confidence": False,
        "is_ambiguous": False,
        "tied_confidence": False,
        "unordered_confidence": unordered,
        "conflicting_fixture_names": False,
        "candidate_names": names_by_id,
    }
    if suggestions:
        ranked = sorted(
            range(len(suggestions)), key=confidences.__getitem__, reverse=True
        )
        selected = ranked[0]
        top = suggestions[selected]
        identity = identities[selected]
        result["top_fixture_id"] = identity
        if identity is not None:
            result["top_fixture"], result["conflicting_fixture_names"] = _fixture_label(
                identity, names_by_id[identity], catalog
            )
        else:
            result["top_fixture"] = (top.get("fixture_name") or "").strip() or "Unknown"
        result["top_confidence"] = confidences[selected]
        algorithm = top.get("prediction_algorithm") or "unknown"
        if not isinstance(algorithm, str):
            raise PayloadError("prediction_algorithm must be a string or null")
        result["algorithm"] = algorithm
        result["is_low_confidence"] = confidences[selected] < low
        if len(confidences) > 1:
            # Decimal avoids binary rounding at the strict threshold boundary.
            gap = Decimal(str(confidences[selected])) - Decimal(
                str(confidences[ranked[1]])
            )
            result["confidence_gap"] = float(gap)
            result["is_ambiguous"] = gap < Decimal(str(ambiguity))
            result["tied_confidence"] = gap == 0
    return result


def _classify_event_quality(
    event, low_confidence_threshold, ambiguity_gap_threshold, fixture_names=None
):
    low = number(low_confidence_threshold, "low confidence threshold", 1)
    ambiguity = number(ambiguity_gap_threshold, "ambiguity gap threshold", 1)
    if not isinstance(event, dict):
        raise PayloadError("Each event must be an object")
    flow = number(event.get("total_flow"), "total_flow")
    feedback = object_or_empty(event.get("latest_user_feedback"), "latest_user_feedback")
    selected_id = fixture_id(feedback.get("fixture_id"))
    catalog = fixture_names or {}
    invalid_model = False
    try:
        result = _model_quality(event, low, ambiguity, catalog)
    except PayloadError:
        if selected_id is None:
            raise
        # Optional model metadata cannot overrule an explicit human choice.
        result = _model_quality({}, low, ambiguity, {})
        invalid_model = True
    names_by_id = result.pop("candidate_names")
    has_prediction = (
        result["top_fixture_id"] is not None or result["top_fixture"] != "Unknown"
    )
    result.update(
        total_flow=flow,
        has_user_feedback=bool(feedback),
        feedback_conflict=(
            selected_id is not None
            and result["top_fixture_id"] is not None
            and selected_id != result["top_fixture_id"]
        ),
        invalid_prediction_metadata=invalid_model,
        attributed_fixture=result["top_fixture"],
        attributed_fixture_id=result["top_fixture_id"],
        attributed_confidence=result["top_confidence"] if has_prediction else None,
        attribution_source="prediction" if has_prediction else "unknown",
        review_reasons=[],
    )
    reasons = result["review_reasons"]
    if selected_id is not None:
        label, conflict = _fixture_label(selected_id, names_by_id[selected_id], catalog)
        result.update(
            attributed_fixture=label,
            attributed_fixture_id=selected_id,
            attributed_confidence=None,
            attribution_source="user_feedback",
            conflicting_fixture_names=conflict,
        )
    else:
        if not has_prediction:
            reasons.append("no_attributable_prediction")
        if result["is_low_confidence"]:
            reasons.append("low_confidence")
        if result["is_ambiguous"]:
            reasons.append("ambiguous_top2")
        if result["tied_confidence"]:
            reasons.append("tied_highest_confidence")
        if result["unordered_confidence"]:
            reasons.append("unordered_confidence")
        if feedback:
            reasons.append("feedback_without_fixture_selection")
    if invalid_model:
        reasons.append("invalid_prediction_metadata")
    if result["conflicting_fixture_names"]:
        reasons.append("conflicting_fixture_names")
    result["needs_review"] = bool(reasons)
    return result


def summarize_usage(
    events,
    low_confidence_threshold=0.70,
    ambiguity_gap_threshold=0.15,
    fixture_names=None,
):
    """Explicit user category wins; otherwise use the highest-confidence model."""
    number(low_confidence_threshold, "low confidence threshold", 1)
    number(ambiguity_gap_threshold, "ambiguity gap threshold", 1)
    if not isinstance(events, list):
        raise PayloadError("water usage events must be a list")
    buckets = defaultdict(lambda: {"volumes": [], "event_count": 0, "confidences": []})
    quality = []
    for event in events:
        item = _classify_event_quality(
            event, low_confidence_threshold, ambiguity_gap_threshold, fixture_names
        )
        quality.append(item)
        bucket = buckets[item["attributed_fixture"]]
        bucket["volumes"].append(item["total_flow"])
        bucket["event_count"] += 1
        if item["attributed_confidence"] is not None:
            bucket["confidences"].append(item["attributed_confidence"])
    fixtures = {
        name: {
            "total_gallons": math.fsum(bucket["volumes"]),
            "event_count": bucket["event_count"],
            "average_confidence": (
                math.fsum(bucket["confidences"]) / len(bucket["confidences"])
                if bucket["confidences"]
                else None
            ),
        }
        for name, bucket in buckets.items()
    }
    total = math.fsum(item["total_flow"] for item in quality)
    algorithms = defaultdict(int)
    for item in quality:
        algorithms[item["algorithm"]] += 1
    return {
        "label": "Attributed fixture usage",
        "attribution_policy": "explicit user fixture, else highest-confidence prediction",
        "status": "empty" if not events else "passed",
        "event_count": len(events),
        "total_gallons": total,
        "fixtures": fixtures,
        "algorithm_counts": dict(algorithms),
        "attribution_counts": {
            source: sum(item["attribution_source"] == source for item in quality)
            for source in ("user_feedback", "prediction", "unknown")
        },
        "invalid_prediction_events": sum(
            q["invalid_prediction_metadata"] for q in quality
        ),
        "low_confidence_events": sum(q["is_low_confidence"] for q in quality),
        "ambiguous_events": sum(q["is_ambiguous"] for q in quality),
        "unordered_prediction_events": sum(q["unordered_confidence"] for q in quality),
        "feedback_events": sum(q["has_user_feedback"] for q in quality),
        "feedback_conflicts": sum(q["feedback_conflict"] for q in quality),
        "review_events": sum(q["needs_review"] for q in quality),
    }


def _parse_day_ranges(value):
    try:
        parts = [int(v.strip()) for v in value.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--days must be comma-separated integers"
        ) from None
    if not parts or any(p < 1 or p > 31 for p in parts) or len(set(parts)) > 3:
        raise argparse.ArgumentTypeError(
            "--days permits up to three ranges of 1-31 days"
        )
    return sorted(set(parts))


if __name__ == "__main__":
    if __package__:
        from .diagnostics import cli
    else:
        from diagnostics import cli

    raise SystemExit(cli("usage"))
