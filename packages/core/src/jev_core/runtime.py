"""Harness: goal -> context -> bounded agent loop -> validated tool -> result."""

import asyncio
import time

from .context import build_context
from .models import DomainError, Principal, digest
from .telemetry import Telemetry


class Harness:
    def __init__(self, store, registry, planner, telemetry=None, max_steps=8, timeout=20):
        if not 1 <= max_steps <= 32 or not 0 < timeout < 40:
            raise ValueError("Budgets exceed supported lease window")
        self.store, self.registry, self.planner = store, registry, planner
        self.telemetry = telemetry or Telemetry()
        self.max_steps, self.timeout = max_steps, timeout

    async def run(self, tenant, run_id):
        claimed = self.store.claim(tenant, run_id)
        if not claimed:
            return self.store.get(tenant, run_id)
        state, lease = claimed
        p = Principal(tenant=tenant, subject=state["owner"], role="operator")
        with self.telemetry.span(
            "agent.run", run_id=run_id, scenario=state["request"]["scenario"]
        ) as span:
            trace_id = format(span.get_span_context().trace_id, "032x")
            try:
                async with asyncio.timeout(self.timeout):
                    while state["steps"] < self.max_steps:
                        context = build_context(
                            self.store,
                            p,
                            state,
                            self.registry.schemas(state["request"]["scenario"]),
                        )
                        # Reserve the step before network I/O: restarts cannot reset budgets.
                        state["steps"] += 1
                        self.store.checkpoint(
                            tenant,
                            state,
                            lease,
                            "agent.plan",
                            {"step": state["steps"], "trace_id": trace_id},
                        )
                        with self.telemetry.span("agent.plan", step=state["steps"]):
                            decision = await self.planner.decide(context)
                        if decision.kind == "final":
                            known_ids = {d["id"] for d in context["evidence"]}
                            for observation in state["observations"]:
                                known_ids.update(
                                    d["id"] for d in observation["result"].get("documents", [])
                                )
                            if not set(decision.citations) <= known_ids:
                                raise DomainError("unsupported_citations", 422)
                            if (
                                state["request"]["scenario"] == "knowledge"
                                and known_ids
                                and not decision.citations
                            ):
                                raise DomainError("citations_required", 422)
                            state.update(
                                status="succeeded",
                                answer=decision.answer,
                                citations=decision.citations,
                            )
                            # Explicit opt-in; summaries are data and never promoted to system rules.
                            if state["request"]["remember"]:
                                self.store.memory_put(
                                    p, state["request"]["session"], "session", decision.answer
                                )
                                self.store.memory_put(
                                    p, "*", "long_term", decision.answer, ttl=7 * 86400
                                )
                            self.store.checkpoint(
                                tenant,
                                state,
                                lease,
                                "run.succeeded",
                                {"steps": state["steps"], "trace_id": trace_id},
                                release=True,
                            )
                            return state
                        tool, args = self.registry.validate(
                            state["request"]["scenario"], decision.tool, decision.arguments
                        )
                        if tool.write:
                            binding = {
                                "run": run_id,
                                "step": state["steps"],
                                "tenant": tenant,
                                "tool": decision.tool,
                                "arguments": args,
                            }
                            state.update(
                                status="waiting",
                                pending={
                                    "tool": decision.tool,
                                    "arguments": args,
                                    "fingerprint": digest(binding),
                                    "expires": time.time() + 3600,
                                },
                            )
                            self.store.checkpoint(
                                tenant,
                                state,
                                lease,
                                "approval.requested",
                                {"tool": decision.tool},
                                release=True,
                            )
                            return state
                        start = time.perf_counter()
                        with self.telemetry.span("tool.execute", tool=decision.tool):
                            async with asyncio.timeout(3):
                                result = await tool.handler(self.store, p, args)
                        state["observations"].append({"tool": decision.tool, "result": result})
                        self.store.checkpoint(
                            tenant,
                            state,
                            lease,
                            "tool.observed",
                            {
                                "tool": decision.tool,
                                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                            },
                        )
                    raise DomainError("step_budget_exceeded", 422)
            except asyncio.CancelledError:
                state["status"] = "ready"
                self.store.checkpoint(tenant, state, lease, "run.interrupted", release=True)
                raise
            except Exception as exc:
                # Never send provider error bodies or exception text to logs/API.
                if isinstance(exc, DomainError) and exc.code == "lease_lost":
                    raise
                state.update(
                    status="failed",
                    error=exc.code if isinstance(exc, DomainError) else type(exc).__name__,
                )
                self.store.checkpoint(
                    tenant, state, lease, "run.failed", {"code": state["error"]}, release=True
                )
                return state
