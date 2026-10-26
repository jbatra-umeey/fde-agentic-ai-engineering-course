"""Provider protocol contracts use controlled HTTP transports, not paid live services."""

import asyncio
import json

import httpx
import pytest
from jev_core.inference import (
    HTTPModel,
    InferenceSession,
    ModelConfig,
    ModelRouter,
    ProviderOutputError,
    RoutingConfig,
    configured_router,
    inference_scope,
    usage_summary,
)
from jev_core.models import Decision, DomainError
from jev_core.prompt_registry import load_prompt
from jev_core.providers import configured_planner
from jev_core.telemetry import Telemetry
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def config(provider="openai", **overrides):
    return ModelConfig(
        provider=provider,
        endpoint="https://api.anthropic.com/v1/messages"
        if provider == "anthropic"
        else "https://api.openai.com/v1/chat/completions",
        model="contract-test",
        key_env="TEST_MODEL_KEY",
        **overrides,
    )


def response(value=None, provider="openai", **extras):
    value = value or {"kind": "final", "answer": "ok"}
    if provider == "anthropic":
        body = {
            "content": [{"type": "tool_use", "name": "emit_result", "input": value}],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
    else:
        body = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "emit_result", "arguments": json.dumps(value)}}
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
    return httpx.Response(200, json={**body, **extras})


@pytest.mark.parametrize("provider", ["openai", "anthropic", "openai_compatible"])
async def test_native_protocol_usage_cost_and_trace(provider):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["messages"][-1]["role"] == "user"
        assert "untrusted-secret" in payload["messages"][-1]["content"]
        if provider == "anthropic":
            assert request.headers["x-api-key"] == "test-secret"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert payload["tool_choice"]["name"] == "emit_result"
        else:
            assert request.headers["authorization"] == "Bearer test-secret"
            assert payload["tool_choice"]["function"]["name"] == "emit_result"
            assert payload["parallel_tool_calls"] is False
        return response(provider=provider)

    model = HTTPModel(
        config(provider, input_usd_per_million=1, output_usd_per_million=5),
        key="test-secret",
        transport=httpx.MockTransport(handler),
    )
    exporter = InMemorySpanExporter()
    telemetry, state = Telemetry(exporter), {}
    try:
        with inference_scope(InferenceSession(telemetry, state)), telemetry.span("parent"):
            result = await model.generate(
                load_prompt("planner"), {"goal": "untrusted-secret"}, Decision
            )
        assert result.answer == "ok"
        summary = usage_summary(state["inference"])
        assert summary["known_cost_usd"] == 0.0002
        assert summary["input_tokens"] == 100
        assert state["model_calls"] == 1
        telemetry.provider.force_flush()
        spans = exporter.get_finished_spans()
        assert spans[0].parent.span_id == spans[-1].context.span_id
        assert "secret" not in str([(dict(s.attributes), s.events) for s in spans])
    finally:
        telemetry.close()


@pytest.mark.parametrize("failure", [503, 429, "invalid", "connect"])
async def test_explicit_fallback(failure):
    calls = []

    def first(_):
        calls.append("primary")
        if failure == "connect":
            raise httpx.ConnectError("sensitive provider failure")
        return httpx.Response(failure) if isinstance(failure, int) else httpx.Response(200, json={})

    def second(_):
        calls.append("backup")
        return response(provider="anthropic")

    a, b = config(retries=0), config("anthropic", retries=0)
    router = ModelRouter(
        RoutingConfig(models={"a": a, "b": b}, routes={"default": ["a", "b"], "judge": ["b"]}),
        {
            "a": HTTPModel(a, key="a", transport=httpx.MockTransport(first)),
            "b": HTTPModel(b, key="b", transport=httpx.MockTransport(second)),
        },
    )
    assert (await router.generate(load_prompt("planner"), {}, Decision)).answer == "ok"
    assert calls == ["primary", "backup"]
    calls.clear()
    await router.generate(load_prompt("judge"), {}, Decision, "judge")
    assert calls == ["backup"]


@pytest.mark.parametrize("failure", [401, 403, 302, "refusal"])
async def test_auth_redirect_refusal_never_fallback(failure):
    calls = []

    def handler(_):
        calls.append(1)
        return (
            response(choices=[{"message": {"refusal": "no"}}])
            if failure == "refusal"
            else httpx.Response(failure)
        )

    c = config(retries=2)
    model = HTTPModel(c, key="a", transport=httpx.MockTransport(handler))
    router = ModelRouter(
        RoutingConfig(models={"a": c, "b": c}, routes={"default": ["a", "b"]}),
        {"a": model, "b": model},
    )
    with pytest.raises((httpx.HTTPStatusError, DomainError)):
        await router.generate(load_prompt("planner"), {}, Decision)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"choices": []},
        {"choices": [{"message": {"tool_calls": []}}]},
        {"choices": [{"finish_reason": "length", "message": {}}]},
    ],
)
async def test_malformed_envelope(body):
    model = HTTPModel(
        config(), key="a", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    )
    with pytest.raises(ProviderOutputError):
        await model.generate(load_prompt("planner"), {}, Decision)


@pytest.mark.parametrize(
    "body",
    [
        {"stop_reason": "max_tokens", "content": []},
        {"content": []},
        {"content": [{"type": "tool_use", "name": "wrong", "input": {}}]},
    ],
)
async def test_anthropic_bad_result(body):
    model = HTTPModel(
        config("anthropic"),
        key="a",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)),
    )
    with pytest.raises(ProviderOutputError):
        await model.generate(load_prompt("planner"), {}, Decision)


async def test_attempt_deadline_and_unknown_usage():
    async def slow(_):
        await asyncio.sleep(0.05)
        return response()

    model = HTTPModel(
        config(timeout_seconds=0.001, retries=1), key="a", transport=httpx.MockTransport(slow)
    )
    telemetry, state = Telemetry(), {}
    try:
        with inference_scope(InferenceSession(telemetry, state)), pytest.raises(httpx.ReadTimeout):
            await model.generate(load_prompt("planner"), {}, Decision)
        assert state["model_calls"] == 2
        assert usage_summary(state["inference"])["unpriced_attempts"] == 2
    finally:
        telemetry.close()


async def test_concurrent_usage_isolation_and_durable_budget():
    async def handler(request):
        await asyncio.sleep(0)
        return response()

    model = HTTPModel(config(), key="a", transport=httpx.MockTransport(handler))
    telemetry = Telemetry()
    checkpoints = []

    async def run():
        state = {"model_calls": 22}
        with inference_scope(
            InferenceSession(telemetry, state, lambda e, d: checkpoints.append(e))
        ):
            await asyncio.gather(
                *(model.generate(load_prompt("planner"), {}, Decision) for _ in range(2))
            )
            with pytest.raises(DomainError, match="model_call_budget"):
                await model.generate(load_prompt("planner"), {}, Decision)
        return state

    try:
        a, b = await asyncio.gather(run(), run())
        assert a["model_calls"] == b["model_calls"] == 24
        assert len(a["inference"]) == len(b["inference"]) == 2
        assert a["inference"] is not b["inference"]
        assert checkpoints.count("model.call.started") == 4
    finally:
        telemetry.close()


@pytest.mark.parametrize(
    "routes",
    [
        {},
        {"default": []},
        {"default": ["missing"]},
        {"default": ["a", "a"]},
        {"default": ["a"], "evil": ["a"]},
    ],
)
def test_bad_routes(routes):
    with pytest.raises(ValueError):
        RoutingConfig(models={"a": config()}, routes=routes)


def test_configuration_and_no_silent_fixture(tmp_path, monkeypatch):
    monkeypatch.delenv("JEV_PLANNER", raising=False)
    with pytest.raises(ValueError, match="requires"):
        configured_planner(require_live=True)
    c = RoutingConfig(models={"a": config()}, routes={"default": ["a"]})
    path = tmp_path / "models.json"
    path.write_text(c.model_dump_json())
    monkeypatch.setenv("JEV_MODELS_CONFIG", str(path))
    monkeypatch.setenv("JEV_PLANNER", "router")
    monkeypatch.setenv("TEST_MODEL_KEY", "test-key")
    assert configured_planner(require_live=True).router.config == c
    path.write_text(" " * 65537)
    with pytest.raises(ValueError, match="too large"):
        configured_router()
    monkeypatch.setenv("JEV_PLANNER", "typo")
    with pytest.raises(ValueError):
        configured_planner()
    with pytest.raises(ValueError):
        load_prompt("../secret")
    with pytest.raises(ValueError):
        HTTPModel(config(), key="")
    with pytest.raises(ValueError):
        ModelConfig(provider="anthropic", endpoint="https://evil.invalid", model="x", key_env="KEY")
    with pytest.raises(ValueError):
        ModelConfig(provider="openai", endpoint="https://evil.invalid", model="x", key_env="KEY")
