"""Harness: goal -> context -> bounded agent loop -> validated tool -> result."""

import asyncio
import time

from pydantic import ValidationError

from .context import build_context
from .inference import InferenceSession, inference_scope, usage_summary
from .models import DomainError, Principal, digest
from .telemetry import Telemetry


class Harness:
    def __init__(self, store, registry, planner, telemetry=None, max_steps=8, timeout=35):
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
        session = InferenceSession(
            self.telemetry,
            state,
            lambda event, data: self.store.checkpoint(tenant, state, lease, event, data),
        )
        with (
            inference_scope(session),
            self.telemetry.span(
                "agent.run", run_id=run_id, scenario=state["request"]["scenario"]
            ) as span,
        ):
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
                            if state["request"]["scenario"] == "release":
                                reviews = [
                                    o["result"]
                                    for o in state["observations"]
                                    if o["tool"] == "release_review"
                                    and "recommendation" in o["result"]
                                ]
                                if (
                                    not reviews
                                    or reviews[-1]["recommendation"].lower()
                                    not in decision.answer.lower()
                                ):
                                    raise DomainError("release_policy_mismatch", 422)
                                state["release_recommendation"] = reviews[-1]["recommendation"]
                            state["usage"] = usage_summary(state["inference"])
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
                        try:
                            tool, args = self.registry.validate(
                                state["request"]["scenario"], decision.tool, decision.arguments
                            )
                        except ValidationError:
                            self._recover(
                                tenant, state, lease, decision.tool, "invalid_tool_arguments"
                            )
                            continue
                        if tool.write:
                            binding = {
                                "run": run_id,
                                "step": state["steps"],
                                "tenant": tenant,
                                "tool": decision.tool,
                                "arguments": args,
                            }
                            state["usage"] = usage_summary(state["inference"])
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
                        try:
                            with self.telemetry.span("tool.execute", tool=decision.tool):
                                async with asyncio.timeout(tool.timeout_seconds):
                                    result = await tool.handler(self.store, p, args)
                        except TimeoutError:
                            self._recover(tenant, state, lease, decision.tool, "read_tool_timeout")
                            continue
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
                state["usage"] = usage_summary(state["inference"])
                state.update(
                    status="failed",
                    error=exc.code if isinstance(exc, DomainError) else type(exc).__name__,
                )
                self.store.checkpoint(
                    tenant, state, lease, "run.failed", {"code": state["error"]}, release=True
                )
                return state

    def _recover(self, tenant, state, lease, tool, code):
        state["recoveries"] = state.get("recoveries", 0) + 1
        if state["recoveries"] > 2:
            raise DomainError("tool_recovery_exhausted", 422)
        # No rejected arguments or exception messages enter the feedback channel.
        state["observations"].append({"tool": tool, "result": {"error": code, "retryable": True}})
        self.store.checkpoint(
            tenant, state, lease, "tool.recoverable_error", {"tool": tool, "code": code}
        )
