import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from jev_api.app import create_app
from jev_core.models import Principal
from jev_core.providers import HTTPPlanner
from jev_core.telemetry import Telemetry
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

OP = "operator-test-token-not-a-secret-0001"
REVIEW = "reviewer-test-token-not-a-secret-0002"
OTHER = "other-tenant-token-not-a-secret-0003"


@pytest.fixture
def client(store, operator, reviewer):
    identities = {
        hashlib.sha256(token.encode()).hexdigest(): p
        for token, p in [
            (OP, operator),
            (REVIEW, reviewer),
            (OTHER, Principal(tenant="beta", subject="eve", role="operator")),
        ]
    }
    with TestClient(create_app(store=store, identities=identities)) as client:
        yield client


def headers(token=OP):
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": "api-test-key"}


def test_auth_limits_and_schema(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/v1/metrics").status_code == 401
    assert client.get("/v1/metrics", headers=headers("bad")).status_code == 401
    assert (
        client.post(
            "/v1/runs",
            headers=headers(),
            json={"scenario": "knowledge", "goal": "rollback", "tenant": "beta"},
        ).status_code
        == 422
    )
    assert client.post("/v1/runs", headers=headers(), content=b"x" * 20000).status_code == 413


def test_api_review_and_cross_tenant(client):
    request = {"scenario": "incident", "goal": "Investigate incident latency"}
    response = client.post("/v1/runs", headers=headers(), json=request)
    assert response.status_code == 200, response.text
    state = response.json()
    assert state["status"] == "waiting"
    run_id = state["id"]
    assert client.post("/v1/runs", headers=headers(), json=request).json()["id"] == run_id
    assert client.get(f"/v1/runs/{run_id}", headers=headers(OTHER)).status_code == 404
    assert client.get(f"/v1/runs/{run_id}/events", headers=headers(OTHER)).status_code == 404
    review = {"fingerprint": state["pending"]["fingerprint"], "approve": True}
    assert (
        client.post(f"/v1/runs/{run_id}/review", headers=headers(), json=review).status_code == 403
    )
    assert (
        client.post(f"/v1/runs/{run_id}/review", headers=headers(REVIEW), json=review).json()[
            "status"
        ]
        == "succeeded"
    )
    assert (
        client.post(f"/v1/runs/{run_id}/review", headers=headers(REVIEW), json=review).status_code
        == 409
    )
    events = client.get(f"/v1/runs/{run_id}/events", headers=headers()).json()
    assert any(e["name"] == "approval.applied" for e in events)
    assert client.get("/v1/metrics", headers=headers()).json()["runs_by_status"]["succeeded"] == 1
    assert client.delete("/v1/memory", headers=headers()).status_code == 204


def test_rate_limit(client):
    results = [client.get("/v1/metrics", headers=headers()).status_code for _ in range(61)]
    assert results[-1] == 429


async def test_provider_retries_then_parses_and_bounds():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        assert request.headers["authorization"] == "Bearer test-model-key"
        if attempts < 3:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"kind": "final", "answer": "ok"})}}]
            },
        )

    planner = HTTPPlanner(
        "https://provider.invalid/chat/completions",
        "test",
        "test-model-key",
        httpx.MockTransport(handler),
    )
    assert (await planner.decide({"system": "test", "goal": "goal"})).answer == "ok"
    assert attempts == 3


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content="x" * 70000),
        httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]}),
        httpx.Response(401),
        httpx.Response(302, headers={"Location": "https://evil.invalid"}),
    ],
)
async def test_provider_invalid_responses_fail_closed(response):
    planner = HTTPPlanner(
        "https://provider.invalid/chat/completions",
        "test",
        "test-key",
        httpx.MockTransport(lambda _: response),
    )
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        await planner.decide({"system": "test"})


@pytest.mark.parametrize(
    "url",
    [
        "http://provider.invalid",
        "https://user:pass@provider.invalid",
        "https://provider.invalid?q=secret",
    ],
)
def test_provider_endpoint_policy(url):
    with pytest.raises(ValueError):
        HTTPPlanner(url, "model", "key")


def test_trace_parentage_and_redaction():
    exporter = InMemorySpanExporter()
    telemetry = Telemetry(exporter)
    with telemetry.span("run", run_id="safe-id"):
        with pytest.raises(RuntimeError), telemetry.span("tool", tool="read"):
            raise RuntimeError("SECRET must not leak")
    telemetry.provider.force_flush()
    spans = exporter.get_finished_spans()
    child, root = spans
    assert child.parent.span_id == root.context.span_id
    assert "SECRET" not in str(
        [(dict(s.attributes), s.events, s.status.description) for s in spans]
    )
    telemetry.close()
