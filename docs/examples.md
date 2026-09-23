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
| `test_water_usage_events.py` | Events and user-first fixture attribution |
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
`Unpublished custom labels`. Public category IDs may appear as `Fixture type N`
when a category name is unavailable. Raw responses are no longer saved
automatically. Even sanitized aggregates can reveal household activity; keep
reports local unless deliberately reviewed for sharing. Library/SDK logs are
suppressed during diagnostics to prevent secret-bearing debug/error output.

## Attributed fixture usage

Each event's full `total_flow` is assigned using **explicit user choice first,
otherwise the highest-confidence prediction, otherwise Unknown**. A non-null
`latest_user_feedback.fixture_id` is the explicit category choice, including ID
zero. Nonnegative integer IDs and digit strings are normalized to the same ID;
invalid non-null IDs fail instead of silently reverting to a model. Missing/null
prediction results and suggestions do not invalidate a valid user selection.
This is a consumer attribution policy, not proof of server revision precedence,
physical fixture accuracy, or a persisted consumption ledger. The SDK still
returns raw events unchanged.

Category names come from an already available catalog, then an unambiguous
suggestion with the **same category ID**, otherwise `Fixture type N`. A different
model category's name is never reused for a user selection. Conflicting names for
one ID are flagged; without a catalog, the ID label is retained. Catalog versus
suggestion conflicts use the catalog label with a warning. Usage-only mode does
not add a catalog request; comprehensive/live modes reuse their existing read.
`sub_fixture_id` identifies a separate household instance where supplied, not
the category. Free text `tell_us`, unproven label fields, and a model algorithm
named `user-feedback` do not independently establish a category selection.

Events with neither an explicit category nor an attributable prediction are
included in **Unknown**. The total is calculated independently from **all**
events: 2 gallons attributed to Sink plus 3 unclassified gallons
means Sink 2, Unknown 3, **total 5**, not 2. Volumes are not multiplied by
confidence or split among predictions. No events means `empty`; one zero-volume
event remains a counted event.

| Option | Default | Meaning |
|--------|---------|---------|
| `--days` | `1,7,30` for usage; `7` otherwise | Up to three unique ranges, each 1-31 days |
| `--low-confidence-threshold` | `0.70` | Top score strictly below this threshold |
| `--ambiguity-gap-threshold` | `0.15` | Highest-minus-second-highest score strictly below this gap |
| `--max-review-events` | `10` | Accepted legacy option; raw per-event review output was replaced by aggregate counts |

Thresholds and confidence values must be finite and within 0-1. Flow must be
finite and nonnegative. Numeric strings are accepted; booleans are not numbers.
Malformed flow or explicit feedback fails. Without a user selection, malformed
model metadata (including a missing confidence) fails rather than silently
discarding a potentially dominant candidate. With a valid user selection,
malformed optional model metadata is excluded and explicitly counted in
`invalid_prediction_events`; the user's category and full volume are retained.

Model candidates are ranked without modifying the raw response. Exact maximum
ties provisionally retain the first **tied maximum**, always flagged for review
even with a zero ambiguity threshold. Reordering tied maxima can change that
provisional label; this does not establish a uniquely confident winner.
`unordered_prediction_events` remains an ordering observation, not an error.

`attribution_counts` distinguishes `user_feedback`, `prediction`, and `unknown`.
User choices never inherit a model confidence: their confidence is null, and
bucket `average_confidence` averages only model-attributed events. Model quality
and algorithm counts remain separate metadata even for corrected events.
When both IDs are available, disagreement between the user's category and the
highest-confidence model is a **feedback conflict**, not permission to override
the user or a reason by itself to request another correction.

### Review and correction

Review or change an event's attribution in the **Phyn app**. An intentional SDK
client can use the existing `submit_water_usage_event_feedback(event_id,
fixture_id, sub_fixture_id=None, tell_us=None)` method; it is a write operation,
not part of these diagnostics. Refetch events to observe returned corrections.
The diagnostics never submit feedback automatically or infer a new selection
from review flags. No new editing UI, event export, or Home Assistant mutation
service is introduced here.

`review_events` flags uncorrected unknown/low-confidence/ambiguous/unsorted
predictions, incomplete feedback, and inconsistent names or invalid model
metadata. A human correction resolves model uncertainty, but metadata warnings
can remain. Reports contain aggregate counts, not actionable raw event IDs or
private text.

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
