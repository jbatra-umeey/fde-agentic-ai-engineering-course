"""Provider boundary. Fixture mode is scripted, not an LLM or autonomous learning."""

import asyncio
import json
import os
from typing import Protocol
from urllib.parse import urlparse

import httpx

from .models import Decision, canonical


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


class HTTPPlanner:
    """Explicit opt-in chat-completions-compatible JSON planner.

    Endpoint/model are operator configuration, never model/user controlled.
    Bounded retries apply only to model reads, never write tools.
    """

    def __init__(self, endpoint, model, api_key, transport=None):
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Model endpoint must be a credential-free HTTPS URL")
        if not model or not api_key:
            raise ValueError("Model and key required")
        self.endpoint, self.model, self.api_key = endpoint, model, api_key
        self.transport = transport

    async def decide(self, context):
        schema = Decision.model_json_schema()
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": context["system"] + " Schema: " + canonical(schema)},
                {
                    "role": "user",
                    "content": canonical({k: v for k, v in context.items() if k != "system"}),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(
            transport=self.transport, timeout=8, follow_redirects=False, trust_env=False
        ) as client:
            for attempt in range(3):
                try:
                    async with client.stream(
                        "POST",
                        self.endpoint,
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    ) as r:
                        if r.status_code in {429, 502, 503, 504} and attempt < 2:
                            await asyncio.sleep(0.1 * (2**attempt))
                            continue
                        r.raise_for_status()
                        chunks = bytearray()
                        async for chunk in r.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 65536:
                                raise ValueError("Provider response too large")
                    body = json.loads(chunks)
                    return Decision.model_validate_json(body["choices"][0]["message"]["content"])
                except (httpx.ConnectError, httpx.TimeoutException):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(0.1 * (2**attempt))
        raise RuntimeError("Provider exhausted")


def configured_planner():
    mode = os.getenv("JEV_PLANNER", "fixture")
    if mode == "fixture":
        return FixturePlanner()
    if mode != "http":
        raise ValueError("JEV_PLANNER must be fixture or http")
    return HTTPPlanner(
        os.environ["JEV_MODEL_ENDPOINT"], os.environ["JEV_MODEL"], os.environ["JEV_MODEL_KEY"]
    )
