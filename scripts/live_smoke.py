"""Opt-in billable integration check; never silently substitutes fixture inference."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

from jev_cli.main import demo


async def main():
    if os.getenv("JEV_RUN_LIVE_TESTS") != "1":
        raise SystemExit("Set JEV_RUN_LIVE_TESTS=1 to explicitly enable billable provider calls")
    with tempfile.TemporaryDirectory() as directory:
        report = await demo("knowledge", str(Path(directory) / "live.sqlite"), live=True)
        state = report["runs"][0]
        # Do not print model text, provider errors, secrets or customer data in CI.
        result = {
            "mode": report["mode"],
            "status": state["status"],
            "calls": state.get("model_calls", 0),
            "usage": state.get("usage"),
            "error": state.get("error"),
        }
        print(json.dumps(result, indent=2))
        if state["status"] != "succeeded" or not state.get("model_calls"):
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
