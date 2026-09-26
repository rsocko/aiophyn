# Category inventory evidence and removed instance assumptions

The supported interpretation is device-scoped category inventory and usage.
Inventory categories use `list[].home_inventory_type_id`, `name`, and `count`.
Event category selection uses explicit `latest_user_feedback.fixture_id`,
otherwise the highest-confidence model suggestion, otherwise Unknown.
Configured counts do not identify individual physical fixtures.

## Bounded live observations

An authorized read-only assessment used unchanged SDK source
`b187b745eeb9e0dfd9ba7bf86bcf706a50e41280`, version `2026.9.2.dev1`, for two
devices in distinct homes over **2026-09-16 00:00 UTC through
2026-09-23 00:00 UTC**, locally interpreted as half-open by event opening time.

Each device used 14 sends: two Cognito requests, home discovery, inventory
before/after, and nine event GETs (week, seven days, identical week).
Inventory snapshots matched. Weekly/daily/repeated-week event IDs, volumes,
timestamps and attribution metadata were consistent, without duplicate or
out-of-window events. This is consistency evidence, not proof against server
caps, undisclosed pagination, or incomplete history.

Both inventory responses omitted `sub_fixtures` on every category row. No
sub-fixture field was found by recursive event inspection, and returned
user-feedback objects were empty. No named inventory instances or individually
attributable instance usage were established on either device in that window.
This does not prove the fields cannot exist on any Phyn device or account.

Category IDs were shared across devices, requiring device scope. Category usage
also occurred with configured count zero. Counts must not filter, divide, or
multiply category usage. Exact household activity and identifiers remain in
private reports, not public examples.

## Why the assumed instance support was removed

The optional feedback argument `sub_fixture_id` entered the SDK in commit
`9c98576c17f74f07ca6786fc1a8a88cd4b793d55` on February 25, 2026.
Inventory `sub_fixtures` examples followed in
`2e3b1ff402bcecad5b71dfa1948145ef3a1ed07d`. The latter commit and shared fixture
comment describe adaptation from real API responses, but the checked-in example
is not an original raw capture. The particular instance fields and their
semantics were not independently verified against a raw capture.

Our outgoing request field, adapted samples, and synthetic matching tests were
not sufficient proof of a supported server feature. The unsupported feedback
argument/body field, named-instance examples, and hypothetical join analyzer
have therefore been removed. Category-level behavior remains.

Feedback now accepts
`submit_water_usage_event_feedback(event_id, fixture_id, *, tell_us=None)`.
The revised outgoing body is checked offline; no live feedback write was made
to validate it. The published immutable `2026.9.2.dev1` artifact is unchanged.

Inventory and usage methods still return decoded responses unchanged, including
unknown fields. Passing through unknown metadata is not interpreting it or
claiming support for individual-fixture attribution.
