"""Real HTTP inference, typed routing, bounded retries and per-run usage accounting.

No global last_usage: ContextVar scopes accounting to one run while TaskGroup
children share that run's recorder. Prompts, keys and provider bodies are never logged.
"""

import asyncio
import json
import os
import time
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import Field, ValidationError, model_validator

from .models import DomainError, StrictModel, canonical


class ModelConfig(StrictModel):
    provider: Literal["openai", "anthropic", "openai_compatible"]
    endpoint: str
    model: str = Field(min_length=1, max_length=150)
    key_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    max_output_tokens: int = Field(default=1500, ge=128, le=4096)
    timeout_seconds: float = Field(default=5, gt=0, le=10, allow_inf_nan=False)
    retries: int = Field(default=2, ge=0, le=2)
    input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def endpoint_policy(self):
        url = urlparse(self.endpoint)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Model endpoint must be a credential-free HTTPS URL")
        if self.provider == "openai" and url.hostname != "api.openai.com":
            raise ValueError("OpenAI credentials require api.openai.com")
        if self.provider == "anthropic" and url.hostname != "api.anthropic.com":
            raise ValueError("Anthropic credentials require api.anthropic.com")
        return self


class RoutingConfig(StrictModel):
    models: dict[str, ModelConfig] = Field(min_length=1, max_length=16)
    routes: dict[str, list[str]]

    @model_validator(mode="after")
    def routes_exist(self):
        if "default" not in self.routes:
            raise ValueError("default route required")
        allowed = {"default", "judge", "supervisor"}
        allowed |= {
            f"planner:{s}"
            for s in ("knowledge", "incident", "mobile_performance", "refund", "release")
        }
        allowed |= {f"specialist:{s}" for s in ("research", "coding", "analysis", "security")}
        if not self.routes.keys() <= allowed:
            raise ValueError("Unknown route")
        for names in self.routes.values():
            if (
                not 1 <= len(names) <= 3
                or len(set(names)) != len(names)
                or not set(names) <= self.models.keys()
            ):
                raise ValueError("Routes require 1-3 distinct configured models")
        return self


class ProviderOutputError(ValueError):
    """Malformed/truncated output is eligible for explicitly configured fallback."""


class InferenceSession:
    def __init__(self, telemetry, state, checkpoint=None, max_calls=24):
        self.telemetry, self.state, self.checkpoint = telemetry, state, checkpoint
        self.max_calls = max_calls
        state.setdefault("inference", [])
        state.setdefault("model_calls", 0)

    def reserve(self):
        if self.state["model_calls"] >= self.max_calls:
            raise DomainError("model_call_budget_exceeded", 422)
        self.state["model_calls"] += 1
        if self.checkpoint:
            self.checkpoint("model.call.started", {"call": self.state["model_calls"]})

    def record(self, record):
        self.state["inference"].append(record)
        self.telemetry.inference(record)
        if self.checkpoint:
            self.checkpoint("model.call.completed", record)


_session: ContextVar[InferenceSession | None] = ContextVar("inference_session", default=None)


@contextmanager
def inference_scope(session):
    token = _session.set(session)
    try:
        yield session
    finally:
        _session.reset(token)


def usage_summary(records):
    return {
        "attempts": len(records),
        "input_tokens": sum(r.get("input_tokens") or 0 for r in records),
        "output_tokens": sum(r.get("output_tokens") or 0 for r in records),
        "known_cost_usd": round(sum(r.get("cost_usd") or 0 for r in records), 8),
        "unpriced_attempts": sum(r.get("cost_usd") is None for r in records),
        "unknown_usage_attempts": sum(
            r.get("input_tokens") is None or r.get("output_tokens") is None for r in records
        ),
        "latency_ms_sum": round(sum(r["latency_ms"] for r in records), 2),
    }


def retryable(exc):
    return isinstance(exc, (httpx.TransportError, ProviderOutputError)) or (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in {429, 500, 502, 503, 504, 529}
    )


class HTTPModel:
    def __init__(self, config, key=None, transport=None, json_mode=False):
        self.config = config
        self.key = key if key is not None else os.environ.get(config.key_env)
        if not self.key:
            raise ValueError(f"Missing provider credential in {config.key_env}")
        self.transport, self.json_mode = transport, json_mode

    def request(self, prompt, data, schema):
        c = self.config
        # emit_result is an output schema, not an executable business tool.
        system = prompt.text + "\nOutput JSON schema: " + canonical(schema.model_json_schema())
        user = canonical(data)
        if len(user.encode()) > 48000:
            raise ValueError("Model input exceeds byte budget")
        if c.provider == "anthropic":
            return {
                "model": c.model,
                "max_tokens": c.max_output_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "tools": [
                    {
                        "name": "emit_result",
                        "description": "Return the structured result",
                        "input_schema": schema.model_json_schema(),
                    }
                ],
                "tool_choice": {"type": "tool", "name": "emit_result"},
            }, {"x-api-key": self.key, "anthropic-version": "2023-06-01"}
        payload = {
            "model": c.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        payload["max_completion_tokens" if c.provider == "openai" else "max_tokens"] = (
            c.max_output_tokens
        )
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        else:
            payload.update(
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "emit_result",
                            "description": "Return the structured result",
                            "parameters": schema.model_json_schema(),
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "emit_result"}},
                parallel_tool_calls=False,
            )
        return payload, {"Authorization": f"Bearer {self.key}"}

    def parse(self, body, schema):
        try:
            if self.config.provider == "anthropic":
                if body.get("stop_reason") == "refusal":
                    raise DomainError("model_refusal", 422)
                if body.get("stop_reason") == "max_tokens":
                    raise ProviderOutputError("Truncated model output")
                blocks = [b for b in body["content"] if b["type"] == "tool_use"]
                if len(blocks) != 1 or blocks[0]["name"] != "emit_result":
                    raise ProviderOutputError("Expected one structured result")
                value = blocks[0]["input"]
            else:
                choice = body["choices"][0]
                message = choice["message"]
                if message.get("refusal") or choice.get("finish_reason") == "content_filter":
                    raise DomainError("model_refusal", 422)
                if choice.get("finish_reason") == "length":
                    raise ProviderOutputError("Truncated model output")
                if self.json_mode:
                    value = json.loads(message["content"])
                else:
                    calls = message["tool_calls"]
                    if len(calls) != 1 or calls[0]["function"]["name"] != "emit_result":
                        raise ProviderOutputError("Expected one structured result")
                    value = json.loads(calls[0]["function"]["arguments"])
            return schema.model_validate(value, strict=True)
        except (
            AttributeError,
            KeyError,
            IndexError,
            TypeError,
            ValidationError,
            json.JSONDecodeError,
        ) as exc:
            raise ProviderOutputError("Invalid structured provider response") from exc

    async def generate(self, prompt, data, schema, route="default"):
        payload, headers = self.request(prompt, data, schema)
        c, session = self.config, _session.get()
        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=c.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for attempt in range(c.retries + 1):
                if session:
                    session.reserve()
                started = time.perf_counter()
                record = {
                    "provider": c.provider,
                    "model": c.model,
                    "route": route,
                    "prompt": prompt.name,
                    "prompt_version": prompt.version,
                    "prompt_sha256": prompt.sha256,
                    "attempt": attempt + 1,
                    "input_tokens": None,
                    "output_tokens": None,
                    "cost_usd": None,
                    "status": "error",
                }
                span_context = (
                    session.telemetry.span(
                        "gen_ai.inference",
                        **{
                            "gen_ai.system": c.provider,
                            "gen_ai.request.model": c.model,
                            "jev.route": route,
                            "jev.prompt.sha256": prompt.sha256,
                            "jev.prompt.version": prompt.version,
                        },
                    )
                    if session
                    else nullcontext()
                )
                try:
                    with span_context as span:
                        # Total attempt deadline also bounds slow streaming bodies.
                        async with asyncio.timeout(c.timeout_seconds):
                            async with client.stream(
                                "POST", c.endpoint, json=payload, headers=headers
                            ) as response:
                                response.raise_for_status()
                                chunks = bytearray()
                                async for chunk in response.aiter_bytes():
                                    chunks.extend(chunk)
                                    if len(chunks) > 65536:
                                        raise ProviderOutputError("Provider response too large")
                            try:
                                body = json.loads(chunks)
                            except (ValueError, UnicodeDecodeError) as exc:
                                raise ProviderOutputError("Invalid provider envelope") from exc
                            usage = body.get("usage", {}) if isinstance(body, dict) else {}
                            for destination, source in (
                                (
                                    "input_tokens",
                                    "input_tokens"
                                    if c.provider == "anthropic"
                                    else "prompt_tokens",
                                ),
                                (
                                    "output_tokens",
                                    "output_tokens"
                                    if c.provider == "anthropic"
                                    else "completion_tokens",
                                ),
                            ):
                                count = usage.get(source) if isinstance(usage, dict) else None
                                if type(count) is int and count >= 0:
                                    record[destination] = count
                            if (
                                record["input_tokens"] is not None
                                and record["output_tokens"] is not None
                                and c.input_usd_per_million is not None
                                and c.output_usd_per_million is not None
                            ):
                                record["cost_usd"] = round(
                                    (
                                        record["input_tokens"] * c.input_usd_per_million
                                        + record["output_tokens"] * c.output_usd_per_million
                                    )
                                    / 1_000_000,
                                    8,
                                )
                            result = self.parse(body, schema)
                            record["status"] = "ok"
                            if span:
                                span.set_attributes(
                                    {f"jev.{k}": v for k, v in record.items() if v is not None}
                                )
                            return result
                except TimeoutError as exc:
                    record["error"] = "TimeoutError"
                    if attempt == c.retries:
                        raise httpx.ReadTimeout("Model deadline exceeded") from exc
                except Exception as exc:
                    record["error"] = type(exc).__name__
                    # Bad schema uses fallback, not repeated identical requests.
                    if (
                        not retryable(exc)
                        or isinstance(exc, ProviderOutputError)
                        or attempt == c.retries
                    ):
                        raise
                finally:
                    record["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
                    if session:
                        session.record(record)
                await asyncio.sleep(0.1 * (2**attempt))
        raise RuntimeError("Provider attempts exhausted")


class ModelRouter:
    def __init__(self, config, models=None):
        self.config = config
        self.models = (
            models
            if models is not None
            else {name: HTTPModel(c) for name, c in config.models.items()}
        )

    async def generate(self, prompt, data, schema, route="default"):
        names = self.config.routes.get(route, self.config.routes["default"])
        for index, name in enumerate(names):
            try:
                return await self.models[name].generate(prompt, data, schema, route)
            except Exception as exc:
                if not retryable(exc) or index == len(names) - 1:
                    raise
        raise RuntimeError("Empty model route")


def configured_router():
    path = os.environ["JEV_MODELS_CONFIG"]
    raw = Path(path).read_bytes()
    if len(raw) > 65536:
        raise ValueError("Model configuration too large")
    return ModelRouter(RoutingConfig.model_validate_json(raw))
