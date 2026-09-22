"""Local opt-in only. Collection/import never reads credentials or contacts Phyn."""

import json

import pytest

from examples.diagnostics import run_diagnostics, write_report


@pytest.mark.live_readonly
@pytest.mark.asyncio
async def test_readonly_contracts(live_configuration, request):
    try:
        report = await run_diagnostics(
            live_configuration,
            history=request.config.getoption("--history"),
            history_start=request.config.getoption("--history-start"),
        )
        path = request.config.getoption("--live-report")
        if path:
            write_report(report, path)
    except Exception:
        pytest.fail(
            "Live diagnostic setup/report failed; check interval, configuration and output-file access. "
            "No raw exception retained.",
            pytrace=False,
        )
    print(json.dumps(report, indent=2, allow_nan=False))
    if report["status"] != "passed":
        pytest.fail(
            "Live read-only checks failed or were incomplete; see sanitized report",
            pytrace=False,
        )
