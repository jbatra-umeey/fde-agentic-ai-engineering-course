"""App factory avoids import-time secrets or connections. Swagger is the API explorer."""

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jev_core.models import Approval, DomainError, Principal, RunRequest
from jev_core.providers import configured_planner
from jev_core.runtime import Harness
from jev_core.store import Store
from jev_tools.registry import Registry

from .security import authenticate, load_identities


class BodyLimit:
    """Cap actual ASGI body bytes, including chunked requests, before JSON parsing."""

    def __init__(self, app, maximum=16384):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        messages, count = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            count += len(message.get("body", b""))
            if count > self.maximum:
                response = JSONResponse({"error": "body_too_large"}, status_code=413)
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def replay():
            nonlocal index
            if index < len(messages):
                message = messages[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay, send)


def create_app(store=None, planner=None, identities=None):
    store = store or Store(os.getenv("JEV_DB", "var/jev.sqlite"))
    identities = identities if identities is not None else load_identities()
    harness = Harness(store, Registry(), planner or configured_planner())

    @asynccontextmanager
    async def lifespan(_app):
        yield
        harness.telemetry.close()

    app = FastAPI(title="Jev Agent Engineering", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BodyLimit)
    app.state.store, app.state.harness = store, harness

    @app.exception_handler(DomainError)
    async def domain_error(_request, exc):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else {}
        if exc.status == 429:
            headers["Retry-After"] = "60"
        return JSONResponse({"error": exc.code}, status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        # Do not echo rejected input, which may contain secrets.
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    def identity(authorization: Annotated[str | None, Header()] = None):
        p = authenticate(authorization, identities)
        store.rate_limit(p)
        return p

    User = Annotated[Principal, Depends(identity)]

    @app.get("/healthz")
    def health():
        with store.connection() as c:
            c.execute("SELECT 1").fetchone()
        return {"status": "ok"}

    @app.post("/v1/runs")
    async def create(
        body: RunRequest,
        p: User,
        idempotency_key: Annotated[str, Header(min_length=8, max_length=100)],
    ):
        state = store.create(p, body, idempotency_key)
        return await harness.run(p.tenant, state["id"])

    @app.get("/v1/runs/{run_id}")
    def get(run_id: str, p: User):
        return store.get(p.tenant, run_id)

    @app.get("/v1/runs/{run_id}/events")
    def events(run_id: str, p: User):
        return store.events(p.tenant, run_id)

    @app.post("/v1/runs/{run_id}/resume")
    async def resume(run_id: str, p: User):
        state = store.get(p.tenant, run_id)
        if p.role != "operator" or state["owner"] != p.subject:
            raise DomainError("owner_operator_required", 403)
        return await harness.run(p.tenant, run_id)

    @app.post("/v1/runs/{run_id}/review")
    async def review(run_id: str, body: Approval, p: User):
        store.approve(p, run_id, body)
        return await harness.run(p.tenant, run_id)

    @app.delete("/v1/memory", status_code=204)
    def forget(p: User):
        store.memory_delete(p)

    @app.get("/v1/metrics")
    def metrics(p: User):
        with store.connection() as c:
            counts = c.execute(
                "SELECT json_extract(state,'$.status') status, count(*) n FROM runs "
                "WHERE tenant=? GROUP BY status",
                (p.tenant,),
            ).fetchall()
        return {"runs_by_status": {r["status"]: r["n"] for r in counts}}

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
