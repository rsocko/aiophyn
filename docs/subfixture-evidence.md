# Inventory-to-event sub-fixture evidence

This is a feasibility assessment, not a new SDK identity guarantee or an
implementation of sub-fixture statistics. The runtime SDK still returns decoded
inventory and events unchanged.

## What can be joined

Inventory categories use `list[].home_inventory_type_id`. Historical examples
also contain optional `list[].sub_fixtures[]` entries with `id`, `name`, and
`active`. An event's explicit `latest_user_feedback.fixture_id` takes precedence
over model category selection. Without it, the existing diagnostic policy uses
the highest-confidence suggestion in
`latest_suggested_fixtures_result.suggested_fixtures[]`.

An individual fixture requires an explicit `sub_fixture_id` from that **same
selected source**, a matching parent category, and exactly one inventory entry
under the same device. Do not borrow a model instance ID for an ID-only human
category correction, combine an orphan human instance with a predicted parent,
match by name, or infer identity from a category having count one.

`examples/subfixture_evidence.py` provides an offline, conservative evidence
analyzer. It is not wired into runtime statistics or the live CLI. It reports
event counts and full volume in three mutually exclusive groups:

| Group | Meaning |
|---|---|
| `joinable` | One nonzero instance ID matches exactly one device/category-scoped inventory entry |
| `category_only` | A uniquely selected category maps, but instance identity is absent or unmapped |
| `invalid_or_ambiguous` | Invalid identity/metadata, missing category mapping, duplicate identity, or distinct tied maxima prevent a unique interpretation |

This deliberately distinguishes uncertain joins from the existing usage
report's provisional first-among-equal-maxima bucket. It does **not** change that
attribution policy. Exact ties between different fixture identities are
ambiguous for this assessment, even though the report can provisionally display
one category. No event volume is discarded.

IDs normalize nonnegative integers and ASCII digit strings; bools, floats,
negative values and malformed strings are rejected. A zero instance ID is
reported explicitly: zero is neither assumed to be a sentinel nor promoted to
a physical-instance identity just because inventory also contains zero.
An inactive matching entry remains identifiable and its volume is counted, with
an inactive flag. A renamed label does not change a scoped key. Current inventory
cannot establish an entry's historical name/activity or ID stability.

Inventory `count` is configuration, not a usage filter. An event can refer to a
category whose configured count is zero. Parent-category statistics must not
drop that event. The analyzer also reports inventory categories/instances with
and without matching events, including named inventory entries with no observed
usage. All exposed output is aggregate; names and device/event/instance IDs stay
private.

## Bounded live observations

An explicitly authorized read-only assessment used unchanged SDK source
`b187b745eeb9e0dfd9ba7bf86bcf706a50e41280`, version `2026.9.2.dev1`, for two
devices in distinct homes over the same completed interval:
**2026-09-16 00:00 UTC through 2026-09-23 00:00 UTC**, locally interpreted as
half-open by event opening timestamp.

Each device used 14 sends out of a 24-send budget: two Cognito requests, one
home-discovery GET, inventory before/after, and nine event GETs (week, seven
days, identical week). No further endpoints or mutation calls were used.
Inventory snapshots matched, and weekly/daily/repeated-week event IDs, volumes,
timestamps and retained attribution metadata were consistent, with no duplicate
or out-of-window events.

Both inventory responses omitted `sub_fixtures` on every category row. No
sub-fixture field was found in the recursive event-field inspection, and all
returned user-feedback objects were empty. Consequently **no named inventory
instances or individually attributable instance usage were established** in
either device's sampled data. Category IDs were shared across devices, which
reinforces the need for device scope. Category-level usage also occurred for a
category with configured count zero.

These observations support category-level presentation for the sampled data.
They do not establish that Phyn globally lacks named fixtures, that another
account/window cannot return them, or that the observed weekly responses are
complete. Weekly/daily agreement is consistency evidence, not proof against
server caps or undisclosed pagination. No paging parameters were invented.
Zero/inactive/rename/collision and explicit human-sub-fixture cases remain
synthetic coverage, not live observations.

Exact per-device count and volume fractions are retained in private local
reports rather than committed household activity records. No live feedback was
submitted to manufacture a joinable case.

## Historical example provenance

The optional-sub-fixture docstring/shared sample was added in commit
`2e3b1ff402bcecad5b71dfa1948145ef3a1ed07d` (authored 2026-02-25).
That commit and the shared fixture comment describe adaptation from real API
responses and reference the historical exploration `test-data` directory.
The checked-in example is **not the original raw capture**; its specific
sub-fixture contents have not been independently reverified from a raw capture
in this assessment. Treat it as historical response-shape evidence, not as
proof that the current two device inventories contain named fixtures.

Synthetic tests in `tests/test_subfixture_evidence.py` cover bidirectional
mapping, strict IDs, missing/unmapped/zero IDs, device/category collisions,
duplicate entries, inactive and renamed instances, human precedence, highest
confidence and ambiguous ties, count-zero usage, volume conservation, redaction,
and SDK pass-through. These tests demonstrate how to avoid false joins, not
that individual-fixture statistics are possible with the sampled live data.
