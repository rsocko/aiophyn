# Changelog

All notable changes to the `aiophyn` library will be documented in this file.

## [2026.2.1] — 2026-02-27

### New Features

- **`HomeInventory` module** — New `HomeInventory` class with methods to fetch the
  master fixture type catalog (`get_fixture_types`), query per-device fixture
  inventory (`get_device_inventory`), and update fixture counts
  (`update_device_inventory`).

- **`submit_water_usage_event_feedback`** — New `Device` method to submit user
  fixture correction feedback for a water usage event (uses `token_type="id"`).

- **`HomeInventory` exported from top-level package** — `from aiophyn import HomeInventory`
  now works.

### Non-Breaking Changes

- **`get_homes` return type corrected** — `dict` → `list` to match actual API response.
- **`run_leak_test` `extended_test` parameter** — Now accepts `Union[bool, str]`
  for service call compatibility.

## [2026.2.0] — 2026-02-25

### Breaking Changes

- **`get_autoshuftoff_status` removed** — The misspelled method alias
  `get_autoshuftoff_status` (note the `f` instead of `t`) has been removed.
  Callers must migrate to the correctly-spelled `get_autoshutoff_status`.
  The method behavior and return type (`dict`) are unchanged.

- **`get_device_preferences` return type changed: `dict` → `list[dict]`** —
  The API actually returns a JSON array of preference objects. The old `dict`
  annotation was incorrect. Callers that treated the result as a single dict
  (e.g. `result["name"]`) will break; they must iterate the list instead.
  The homeassistant-phyn integration (`pp.py`) already iterates with
  `for item in data:`, so it is **not affected**.
  *Verified via real API output in exploration scripts.*

- **`get_latest_firmware_info` return type changed: `dict` → `list[dict]`** —
  The API actually returns a JSON array (usually with a single entry).
  Callers that accessed fields directly on the result (e.g. `result["fw_version"]`)
  must now index into the list first: `result[0]["fw_version"]`.
  The homeassistant-phyn integration (`base.py`) already handles both `list` and
  `dict` via `isinstance` guards, so it is **not affected**.
  *Verified via real API output in exploration scripts and HA integration patterns.*

### Potentially Breaking (return type was `None`, now `dict`)

These methods previously had `-> None` annotations but always returned the API
response (Python `return await self._request(...)` was already present). The
annotation has been corrected to `-> dict`. **This is not a runtime breaking
change** — the methods already returned a value; the annotation just didn't
reflect it. However, callers that specifically relied on the `None` type hint
(e.g. for static analysis) may see type-checker warnings.

- **`open_valve`** — Return type `None` → `dict`. No callers use the return
  value (all fire-and-forget). **Not breaking in practice.**

- **`close_valve`** — Return type `None` → `dict`. Same as `open_valve`.
  **Not breaking in practice.**

- **`run_leak_test`** — Return type (untyped) → `dict`. The homeassistant-phyn
  `services.py` already uses the return value
  (`assert 'code' in result and result['code'] == 'success'`), confirming the
  API does return a dict. Adding the annotation is a correction, not a change
  in behavior.

- **`set_autoshutoff_enabled`** — Return type `None` → `dict`. No callers
  use the return value. **Not breaking in practice.**

### Non-Breaking Changes

- **`get_water_statistics` parameter types clarified** — `from_ts` and `to_ts`
  changed from untyped to `int`. Return type annotation added as
  `list[dict[str, Any]]`. The method already returned this type; the annotation
  is new. Callers in homeassistant-phyn (`pw.py`) already iterate with
  `for entry in data:` and use `.get()` / `.update()`, so this is compatible.
  *Verified against real API output captured in
  `test-data/fixture-exploration/exploration_20260223_000950.json`.*

- **`get_consumption` parameter types corrected** — `details`, `event_count`,
  and `comparison` changed from `Optional[str] = False` to `bool = False`.
  All callers pass booleans, so this is compatible.

- **`get_autoshutoff_status` docstring updated** — Return documentation
  changed from "List of dicts with keys: created_ts, device_id, name,
  updated_ts, value" to "Dict with auto_shutoff_enable (bool) and
  auto_shutoff_eligible (int)." The return **type** (`dict`) is unchanged.
  The old docstring was a copy-paste error from `get_device_preferences`.
  *Verified via mock test data and HA integration usage pattern
  (`self._auto_shutoff.update(data)` expects a dict).*

### New Features

- **`get_water_usage_events`** — New method to fetch water usage events with
  ML-based fixture predictions for a given time range.

- **`submit_water_usage_event_feedback`** — New method to submit fixture
  correction feedback for a water usage event.

- **`run_leak_test` accepts string parameter** — `extended_test` now accepts
  `Union[bool, str]` for compatibility with Home Assistant service calls that
  may pass string `"true"`/`"false"`.
