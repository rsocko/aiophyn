# Example scripts

Examples are **local, explicitly invoked live tools**, not offline tests.
Importing them does not load credentials, parse arguments, log in or run an event
loop. Subsequent authorized, bounded read-only observations are documented in
[testing](testing.md#bounded-live-observations-2026-09-23-utc); they do not prove
all server behavior.
See [configuration](configuration.md) for local credentials and
[testing](testing.md#local-opt-in-read-only-checks) for the separately gated pytest
harness.

## Read-only diagnostics

Run from the repository root after installing the library. These entry points
share `examples/diagnostics.py`, use process environment variables by default,
and load a dotenv file **only** when `--env-file` names it explicitly:

```powershell
python examples\test_api.py --env-file .env.live
python examples\test_home_inventory.py --env-file .env.live
python examples\test_water_usage_events.py --env-file .env.live --days 1,7
python examples\test_comprehensive.py --env-file .env.live
python examples\test_alerts.py --env-file .env.live
```

| Entry point | Reads performed after authentication and discovery |
|-------------|----------------------------------------------------|
| `test_api.py` | Selected device state and today's consumption |
| `test_home_inventory.py` | Fixture catalog and selected device inventory |
| `test_water_usage_events.py` | Events and predicted fixture usage |
| `test_comprehensive.py` | Catalog, inventory, events, state, consumption, preferences, firmware and away-mode status |
| `test_alerts.py` | Selected home's latest alerts and active alert summary |

These commands do **not** exercise the full API surface, modify inventory, send
feedback, mark alerts read, operate valves or run leak tests. They select the
first discovered device unless `PHYN_DEVICE_ID` or `--device-id` selects another
discovered device. They no longer iterate over every device automatically.
Discovery with no devices is reported as incomplete, not a successful device
check. The legacy `config.py` setup is now used **only by the MQTT example**.

Every diagnostic prints a sanitized JSON report. Optional
`--report .artifacts\usage.json` creates a new report and refuses to overwrite an
existing file. Reports distinguish `passed`, `failed`, `empty` and `skipped`.
Exit codes: **0** completed reads (including valid empty responses), **1** failed
or incomplete reads, **2** configuration, argument or report-file errors.
Authentication failure contributes one failed check; dependent checks are
skipped. A malformed payload or partial request failure never becomes zero use.

Report output contains structural counts and aggregate usage, not credentials,
tokens, household/device/event IDs, addresses, free-text feedback or raw
exceptions. Custom fixture labels are combined into
`Unpublished custom predictions`. Raw responses are no longer saved
automatically. Even sanitized aggregates can reveal household activity; keep
reports local unless deliberately reviewed for sharing. Library/SDK logs are
suppressed during diagnostics to prevent secret-bearing debug/error output.

## Predicted fixture usage

This is explicitly an **ML prediction report**, not physical fixture ground
truth or a feedback-corrected consumption ledger.

Each event's full `total_flow` is assigned to the first returned prediction.
Missing/null prediction results, missing/null/empty suggestions and absent
fixture names are included in **Unknown**. The total is calculated independently
from **all** events: 2 gallons predicted as Sink plus 3 unclassified gallons
means Sink 2, Unknown 3, **total 5**, not 2. Volumes are not multiplied by
confidence or split among predictions. No events means `empty`; one zero-volume
event remains a counted event.

| Option | Default | Meaning |
|--------|---------|---------|
| `--days` | `1,7,30` for usage; `7` otherwise | Up to three unique ranges, each 1-31 days |
| `--low-confidence-threshold` | `0.70` | Top score strictly below this threshold |
| `--ambiguity-gap-threshold` | `0.15` | First-minus-second score strictly below this gap |
| `--max-review-events` | `10` | Accepted legacy option; raw per-event review output was replaced by aggregate counts |

Thresholds and confidence values must be finite and within 0-1. Flow must be
finite and nonnegative. Numeric strings are accepted; missing or malformed flow
or confidence fails explicitly, rather than silently becoming zero. Suggestions
are not guaranteed to be ordered by confidence: the first returned prediction
still receives the volume, without sorting or assuming it is the highest score.
Unordered confidence is counted in `unordered_prediction_events` and flagged
for review, not rejected. The first-minus-second gap refers to returned order,
not a ranking of all candidates. Unknown confidence is not a measured zero and
is reported as null. Missing suggestions generate a review signal.

User feedback presence generates a separate review signal. When both fixture
IDs are available, a disagreement with the first prediction is counted as a
**feedback conflict**; it does not override the predicted bucket. Without both
IDs, disagreement is unknown. Feedback presence does not establish real-world
classification accuracy.

Algorithm counts retain known algorithm labels; unfamiliar labels are combined
as `unrecognized` in shareable reports rather than echoing arbitrary API text.

## Bounded history characterization

```powershell
python examples\test_water_usage_events.py --env-file .env.live --days 7 --history --history-start 2025-01-01 --report .artifacts\history.json
```

History requires an explicitly selected device. An omitted `--history-start`
uses the seven UTC days ending at the most recent UTC midnight. A supplied date
selects a completed seven-day interval, useful for a known-active older period.
It does not initiate a large historical backfill. Details, comparison limits and
request limits are in [testing](testing.md#history-characterization).

## MQTT example (separate legacy setup)

`test_mqtt.py` still uses local `examples/config.py`; it does **not** read dotenv
or share the bounded HTTP diagnostic harness:

```powershell
Copy-Item examples\config.example examples\config.py
# Edit this ignored local Python file, then explicitly run:
python examples\test_mqtt.py
```

It authenticates, discovers the first home, subscribes to Phyn Plus device
updates for ten seconds and disconnects. It logs raw home/device/message data
to the console and does not save a JSON capture. Treat that output as private.
Its existing event-loop/platform requirements remain unchanged. MQTT streaming
is not part of the automated live checks or their timeout/request guarantees.
