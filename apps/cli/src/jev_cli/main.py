import argparse
import asyncio
import json
import uuid

from jev_core.models import Approval, Principal, RunRequest
from jev_core.providers import FixturePlanner, configured_planner
from jev_core.runtime import Harness
from jev_core.store import Store
from jev_tools.registry import Registry
from jev_workflows.scenarios import SCENARIOS, seed


async def demo(scenario="all", db="var/demo.sqlite", approve=False, live=False):
    store = Store(db)
    tenant = "demo-" + uuid.uuid4().hex[:8]
    seed(store, tenant)
    operator = Principal(tenant=tenant, subject="demo-operator", role="operator")
    reviewer = Principal(tenant=tenant, subject="demo-reviewer", role="reviewer")
    planner = configured_planner(require_live=True) if live else FixturePlanner()
    harness = Harness(store, Registry(getattr(planner, "router", None)), planner)
    results = []
    try:
        for name in SCENARIOS if scenario == "all" else [scenario]:
            state = store.create(
                operator, RunRequest(scenario=name, goal=SCENARIOS[name]), uuid.uuid4().hex
            )
            state = await harness.run(tenant, state["id"])
            if approve and state["status"] == "waiting":
                # Explicit teaching simulation only. The API never auto-approves.
                store.approve(
                    reviewer,
                    state["id"],
                    Approval(fingerprint=state["pending"]["fingerprint"], approve=True),
                )
                state = await harness.run(tenant, state["id"])
            results.append(state)
        return {
            "mode": "live_http" if live else "synthetic_fixture",
            "review_simulated": approve,
            "runs": results,
        }
    finally:
        harness.telemetry.close()


def main():
    parser = argparse.ArgumentParser(description="Jev agent engineering reference examples")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--scenario", choices=["all", *SCENARIOS], default="all")
    d.add_argument("--db", default="var/demo.sqlite")
    d.add_argument(
        "--live", action="store_true", help="Real inference via JEV_PLANNER=router or http"
    )
    d.add_argument(
        "--simulate-review",
        action="store_true",
        help="Simulate an independent reviewer for synthetic data only",
    )
    lesson = sub.add_parser("lesson")
    lesson.add_argument("number", type=int, choices=range(1, 11))
    lesson.add_argument(
        "--live", action="store_true", help="Use configured model for lessons involving the harness"
    )
    args = parser.parse_args()
    if args.command == "demo":
        result = asyncio.run(demo(args.scenario, args.db, args.simulate_review, args.live))
    else:
        from .lessons import run_lesson

        result = asyncio.run(run_lesson(args.number, live=args.live))
    print(json.dumps(result, indent=2))
    if args.command == "demo" and any(r["status"] == "failed" for r in result["runs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
