"""Real loopback API smoke using temporary data and freshly generated identities."""

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from jev_core.store import Store
from jev_workflows.scenarios import seed


def main():
    with tempfile.TemporaryDirectory() as directory:
        db = str(Path(directory) / "api.sqlite")
        seed(Store(db))
        tokens = {role: secrets.token_urlsafe(32) for role in ["operator", "reviewer"]}
        identities = {
            hashlib.sha256(token.encode()).hexdigest(): {
                "tenant": "demo",
                "subject": role,
                "role": role,
            }
            for role, token in tokens.items()
        }
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {
            **os.environ,
            "JEV_DB": db,
            "JEV_PLANNER": "fixture",
            "JEV_IDENTITIES_JSON": json.dumps(identities),
        }
        # These exporter settings are irrelevant to API smoke and could leak local test metadata.
        env.pop("JEV_OTLP_TRACES_ENDPOINT", None)
        env.pop("JEV_OTLP_METRICS_ENDPOINT", None)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "jev_api.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=5
            ) as client:
                for _ in range(100):
                    try:
                        if client.get("/healthz").status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    if process.poll() is not None:
                        raise RuntimeError("API exited during startup")
                    time.sleep(0.05)
                else:
                    raise RuntimeError("API startup deadline exceeded")
                headers = {
                    "Authorization": "Bearer " + tokens["operator"],
                    "Idempotency-Key": "loopback-smoke",
                }
                assert client.get("/v1/metrics").status_code == 401
                result = client.post(
                    "/v1/runs",
                    headers=headers,
                    json={"scenario": "incident", "goal": "Investigate incident latency"},
                )
                result.raise_for_status()
                state = result.json()
                assert state["status"] == "waiting"
                review = {"fingerprint": state["pending"]["fingerprint"], "approve": True}
                assert (
                    client.post(
                        f"/v1/runs/{state['id']}/review", headers=headers, json=review
                    ).status_code
                    == 403
                )
                result = client.post(
                    f"/v1/runs/{state['id']}/review",
                    headers={"Authorization": "Bearer " + tokens["reviewer"]},
                    json=review,
                )
                result.raise_for_status()
                assert result.json()["status"] == "succeeded"
            print(
                json.dumps(
                    {
                        "loopback_api": "passed",
                        "health": True,
                        "anonymous_denied": True,
                        "self_review_denied": True,
                        "independent_review": True,
                        "mode": "fixture",
                    }
                )
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
