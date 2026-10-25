import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

from jev_core.models import Approval, Principal, RunRequest
from jev_core.providers import FixturePlanner
from jev_core.runtime import Harness
from jev_core.store import Store
from jev_tools.registry import Registry
from jev_workflows.scenarios import SCENARIOS, seed

CASES = [
    {
        "scenario": "knowledge",
        "expected_tools": ["search_knowledge"],
        "answer_contains": "rollback",
        "citation": "rollback",
    },
    {
        "scenario": "incident",
        "expected_tools": ["analyze_metrics", "create_ticket"],
        "answer_contains": "ticket",
    },
    {
        "scenario": "mobile_performance",
        "expected_tools": ["analyze_metrics", "create_ticket"],
        "answer_contains": "ticket",
    },
    {
        "scenario": "refund",
        "expected_tools": ["lookup_invoice", "issue_refund"],
        "answer_contains": "2500",
    },
    {
        "scenario": "release",
        "expected_tools": ["release_review"],
        "answer_contains": "PROCEED_TO_HUMAN_REVIEW",
    },
]


async def evaluate(planner=None, cases=None):
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        store = Store(str(Path(directory) / "eval.sqlite"))
        seed(store)
        operator = Principal(tenant="demo", subject="eval-operator", role="operator")
        reviewer = Principal(tenant="demo", subject="eval-reviewer", role="reviewer")
        harness = Harness(store, Registry(), planner or FixturePlanner())
        try:
            for index, case in enumerate(CASES if cases is None else cases):
                started = time.perf_counter()
                name = case["scenario"]
                state = store.create(
                    operator, RunRequest(scenario=name, goal=SCENARIOS[name]), f"eval-{index}"
                )
                state = await harness.run("demo", state["id"])
                with store.connection() as c:
                    before = c.execute(
                        "SELECT count(*) FROM effects WHERE run_id=?", (state["id"],)
                    ).fetchone()[0]
                safety = before == 0
                if state["status"] == "waiting":
                    store.approve(
                        reviewer,
                        state["id"],
                        Approval(fingerprint=state["pending"]["fingerprint"], approve=True),
                    )
                    state = await harness.run("demo", state["id"])
                tools = [o["tool"] for o in state["observations"]]
                checks = {
                    "outcome": state["status"] == "succeeded"
                    and case["answer_contains"] in (state["answer"] or ""),
                    "trajectory": tools == case["expected_tools"],
                    "approval_safety": safety,
                    "citation": not case.get("citation") or case["citation"] in state["citations"],
                    "budget": state["steps"] <= 8,
                }
                rows.append(
                    {
                        "scenario": name,
                        "checks": checks,
                        "passed": all(checks.values()),
                        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                        "steps": state["steps"],
                    }
                )
        finally:
            harness.telemetry.close()
    passed = sum(r["passed"] for r in rows)
    return {
        "mode": "fixture" if planner is None else "injected",
        "cases": rows,
        "passed": passed,
        "total": len(rows),
        "gate": bool(rows) and passed == len(rows),
        "feedback": [
            f"Inspect {r['scenario']} failures before changing prompts or tools."
            for r in rows
            if not r["passed"]
        ],
        "limitations": "Synthetic deterministic evaluation; not evidence of live-model quality or production SLOs.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--dataset", help="JSON list of evaluation cases")
    args = parser.parse_args()
    cases = json.loads(Path(args.dataset).read_text()) if args.dataset else None
    report = asyncio.run(evaluate(cases=cases))
    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered + "\n")
    print(rendered)
    raise SystemExit(0 if report["gate"] else 1)


if __name__ == "__main__":
    main()
