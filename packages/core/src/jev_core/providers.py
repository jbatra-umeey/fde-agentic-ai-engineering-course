"""Fixture and real structured planners share the same authorization boundary."""

import os
from typing import Protocol

from .inference import HTTPModel, ModelConfig, ModelRouter, RoutingConfig, configured_router
from .models import Decision
from .prompt_registry import load_prompt


class Planner(Protocol):
    async def decide(self, context: dict) -> Decision: ...


class FixturePlanner:
    """Predictable branches make offline examples, failure tests, and CI repeatable."""

    async def decide(self, context):
        scenario = context["scenario"]
        observations = context["observations"]
        seen = {o["tool"] for o in observations}
        if scenario == "knowledge":
            if "search_knowledge" not in seen:
                return Decision(
                    kind="tool", tool="search_knowledge", arguments={"query": context["goal"]}
                )
            docs = next(
                o["result"]["documents"] for o in observations if o["tool"] == "search_knowledge"
            )
            return Decision(
                kind="final",
                answer=" ".join(d["content"] for d in docs) or "No matching evidence found.",
                citations=[d["id"] for d in docs],
            )
        if scenario in {"incident", "mobile_performance"}:
            if "analyze_metrics" not in seen:
                return Decision(
                    kind="tool", tool="analyze_metrics", arguments={"dataset": scenario}
                )
            if "create_ticket" not in seen:
                analysis = next(o["result"] for o in observations if o["tool"] == "analyze_metrics")
                if analysis["regression"]:
                    return Decision(
                        kind="tool",
                        tool="create_ticket",
                        arguments={
                            "title": f"Investigate {scenario}: p95 regression {analysis['change_pct']}%",
                            "severity": "high",
                        },
                    )
            return Decision(
                kind="final",
                answer="Metrics reviewed. The approved local investigation ticket is recorded; no production system was modified.",
            )
        if scenario == "refund":
            if "lookup_invoice" not in seen:
                return Decision(
                    kind="tool", tool="lookup_invoice", arguments={"invoice": "INV-100"}
                )
            if "issue_refund" not in seen:
                return Decision(
                    kind="tool",
                    tool="issue_refund",
                    arguments={"invoice": "INV-100", "amount_cents": 2500},
                )
            return Decision(
                kind="final",
                answer="An approved 2500-cent refund was recorded in the local ledger. No payment processor was contacted.",
            )
        if "release_review" not in seen:
            return Decision(kind="tool", tool="release_review", arguments={"dataset": "release"})
        review = next(o["result"] for o in observations if o["tool"] == "release_review")
        return Decision(
            kind="final",
            answer=f"Release recommendation: {review['recommendation']}. Performance and security specialists reviewed the synthetic evidence. No deployment occurred.",
        )


class LLMPlanner:
    def __init__(self, router):
        self.router = router

    async def decide(self, context):
        return await self.router.generate(
            load_prompt("planner"),
            {k: v for k, v in context.items() if k != "system"},
            Decision,
            "planner:" + context.get("scenario", "knowledge"),
        )


class HTTPPlanner(LLMPlanner):
    """Backward-compatible JSON-mode adapter; new configurations use native tool output."""

    def __init__(self, endpoint, model, api_key, transport=None):
        config = ModelConfig(
            provider="openai_compatible", endpoint=endpoint, model=model, key_env="JEV_MODEL_KEY"
        )
        model_client = HTTPModel(config, key=api_key, transport=transport, json_mode=True)
        super().__init__(
            ModelRouter(
                RoutingConfig(models={"legacy": config}, routes={"default": ["legacy"]}),
                {"legacy": model_client},
            )
        )


def configured_planner(require_live=False):
    mode = os.getenv("JEV_PLANNER", "fixture")
    if mode == "fixture":
        if require_live:
            raise ValueError(
                "--live requires JEV_PLANNER=router or http; refusing fixture fallback"
            )
        return FixturePlanner()
    if mode == "router":
        return LLMPlanner(configured_router())
    if mode == "http":
        return HTTPPlanner(
            os.environ["JEV_MODEL_ENDPOINT"], os.environ["JEV_MODEL"], os.environ["JEV_MODEL_KEY"]
        )
    raise ValueError("JEV_PLANNER must be fixture, http or router")
