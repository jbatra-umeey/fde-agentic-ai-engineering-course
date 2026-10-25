"""Ten agent engineering walkthroughs; temporary stores make each independently repeatable."""

import tempfile
from pathlib import Path

from jev_core.context import build_context
from jev_core.models import Approval, DomainError, Principal, RunRequest
from jev_core.providers import FixturePlanner
from jev_core.runtime import Harness
from jev_core.store import Store
from jev_core.telemetry import Telemetry
from jev_tools.registry import Registry
from jev_workflows.patterns import release_review, route, sequential
from jev_workflows.scenarios import SCENARIOS, seed
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


async def run_lesson(number):
    with tempfile.TemporaryDirectory() as directory:
        store = Store(str(Path(directory) / "lesson.sqlite"))
        seed(store)
        p = Principal(tenant="demo", subject="learner", role="operator")
        reviewer = Principal(tenant="demo", subject="reviewer", role="reviewer")
        registry = Registry()
        exporter = InMemorySpanExporter()
        telemetry = Telemetry(exporter)
        harness = Harness(store, registry, FixturePlanner(), telemetry)
        try:
            scenario = "incident" if number in {2, 9} else "knowledge"
            state = store.create(
                p,
                RunRequest(scenario=scenario, goal=SCENARIOS[scenario], remember=number == 5),
                "lesson-run",
            )
            if number == 3:
                return build_context(store, p, state, registry.schemas(scenario))
            if number == 4:
                tool, args = registry.validate(
                    "knowledge", "search_knowledge", {"query": "rollback"}
                )
                return {
                    "contract": registry.schemas("knowledge"),
                    "result": await tool.handler(store, p, args),
                }
            if number == 6:

                async def plan(goal):
                    return route(goal)

                async def review(dataset):
                    return await release_review(dataset)

                return {
                    "router_then_parallel_specialists": await sequential(
                        "review release", [plan, review]
                    )
                }
            if number == 7:
                denied = []
                for tool in ["issue_refund", "shell", "http_get"]:
                    try:
                        registry.validate("knowledge", tool, {})
                    except DomainError as exc:
                        denied.append({"tool": tool, "error": exc.code})
                return {"denied": denied, "allowed": registry.schemas("knowledge")}
            if number == 8:
                from jev_evals.runner import evaluate

                return await evaluate()
            state = await harness.run(p.tenant, state["id"])
            if number == 9:
                proposed = state["pending"].copy()
                store.approve(
                    reviewer,
                    state["id"],
                    Approval(fingerprint=proposed["fingerprint"], approve=True),
                )
                state = await harness.run(p.tenant, state["id"])
                return {
                    "proposed_output": proposed,
                    "simulated_human_review": True,
                    "final": state,
                    "events": store.events(p.tenant, state["id"]),
                }
            if number == 5:
                memory = store.memory_get(p, "default")
                store.memory_delete(p)
                return {"after_opt_in": memory, "after_forget": store.memory_get(p, "default")}
            if number == 10:
                telemetry.provider.force_flush()
                return {
                    "spans": [
                        {
                            "name": s.name,
                            "trace_id": format(s.context.trace_id, "032x"),
                            "parent_span_id": format(s.parent.span_id, "016x")
                            if s.parent
                            else None,
                            "attributes": dict(s.attributes),
                        }
                        for s in exporter.get_finished_spans()
                    ],
                    "events": store.events(p.tenant, state["id"]),
                }
            return {"run": state, "events": store.events(p.tenant, state["id"])}
        finally:
            telemetry.close()
