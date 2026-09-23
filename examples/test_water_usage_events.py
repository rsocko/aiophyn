"""Predicted fixture usage, not ground truth. See docs/examples.md."""

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


def _classify_event_quality(event, low_confidence_threshold, ambiguity_gap_threshold):
    low = number(low_confidence_threshold, "low confidence threshold", 1)
    ambiguity = number(ambiguity_gap_threshold, "ambiguity gap threshold", 1)
    if not isinstance(event, dict):
        raise PayloadError("Each event must be an object")
    flow = number(event.get("total_flow"), "total_flow")
    prediction = object_or_empty(
        event.get("latest_suggested_fixtures_result"),
        "latest_suggested_fixtures_result",
    )
    suggestions = prediction.get("suggested_fixtures")
    if suggestions is None:
        suggestions = []
    if not isinstance(suggestions, list):
        raise PayloadError("suggested_fixtures must be a list or null")
    feedback = object_or_empty(
        event.get("latest_user_feedback"), "latest_user_feedback"
    )
    confidences = []
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            raise PayloadError("Each suggested fixture must be an object")
        confidences.append(
            number(suggestion.get("confidence_score"), "confidence_score", 1)
        )
    unordered = any(
        right > left for left, right in zip(confidences, confidences[1:])
    )
    result = {
        "total_flow": flow,
        "top_fixture": "Unknown",
        "top_confidence": None,
        "algorithm": "unknown",
        "confidence_gap": None,
        "is_low_confidence": False,
        "is_ambiguous": False,
        "unordered_confidence": unordered,
        "has_user_feedback": bool(feedback),
        "feedback_conflict": False,
        "review_reasons": [],
    }
    reasons = result["review_reasons"]
    if unordered:
        reasons.append("unordered_confidence")
    if not suggestions:
        reasons.append("no_suggestions")
    else:
        top = suggestions[0]
        name = top.get("fixture_name")
        if name is not None and not isinstance(name, str):
            raise PayloadError("fixture_name must be a string or null")
        result["top_fixture"] = name or "Unknown"
        result["top_confidence"] = confidences[0]
        algorithm = top.get("prediction_algorithm") or "unknown"
        if not isinstance(algorithm, str):
            raise PayloadError("prediction_algorithm must be a string or null")
        result["algorithm"] = algorithm
        result["is_low_confidence"] = confidences[0] < low
        if len(confidences) > 1:
            # Decimal avoids binary rounding at the strict threshold boundary.
            gap = Decimal(str(confidences[0])) - Decimal(str(confidences[1]))
            result["confidence_gap"] = float(gap)
            result["is_ambiguous"] = gap < Decimal(str(ambiguity))
        result["feedback_conflict"] = (
            feedback.get("fixture_id") is not None
            and top.get("fixture_id") is not None
            and str(feedback["fixture_id"]) != str(top["fixture_id"])
        )
        if result["is_low_confidence"]:
            reasons.append("low_confidence")
        if result["is_ambiguous"]:
            reasons.append("ambiguous_top2")
    if feedback:
        reasons.append("has_user_feedback")
    if result["feedback_conflict"]:
        reasons.append("feedback_conflict")
    result["needs_review"] = bool(reasons)
    return result


def summarize_usage(
    events, low_confidence_threshold=0.70, ambiguity_gap_threshold=0.15
):
    """Attribute the full event volume to its first prediction, including Unknown."""
    number(low_confidence_threshold, "low confidence threshold", 1)
    number(ambiguity_gap_threshold, "ambiguity gap threshold", 1)
    if not isinstance(events, list):
        raise PayloadError("water usage events must be a list")
    buckets = defaultdict(lambda: {"volumes": [], "event_count": 0, "confidences": []})
    quality = []
    for event in events:
        item = _classify_event_quality(
            event, low_confidence_threshold, ambiguity_gap_threshold
        )
        quality.append(item)
        bucket = buckets[item["top_fixture"]]
        bucket["volumes"].append(item["total_flow"])
        bucket["event_count"] += 1
        if item["top_confidence"] is not None:
            bucket["confidences"].append(item["top_confidence"])
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
        "label": "Predicted fixture usage",
        "status": "empty" if not events else "passed",
        "event_count": len(events),
        "total_gallons": total,
        "fixtures": fixtures,
        "algorithm_counts": dict(algorithms),
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
