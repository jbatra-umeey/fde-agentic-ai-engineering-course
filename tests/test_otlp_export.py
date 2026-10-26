"""Real local HTTP exporter delivery; no external collector/backend is assumed."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jev_core.telemetry import Telemetry
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest


def test_local_otlp_trace_and_metric_delivery(monkeypatch):
    received = []

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("JEV_OTLP_TRACES_ENDPOINT", endpoint + "/v1/traces")
    monkeypatch.setenv("JEV_OTLP_METRICS_ENDPOINT", endpoint + "/v1/metrics")
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    telemetry = Telemetry()
    try:
        with telemetry.span("integration.run", scenario="knowledge"):
            telemetry.inference(
                {
                    "provider": "test",
                    "model": "contract",
                    "route": "default",
                    "status": "ok",
                    "latency_ms": 10,
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cost_usd": 0.0002,
                }
            )
        assert telemetry.provider.force_flush()
        assert telemetry.meter_provider.force_flush()
        traces = [
            ExportTraceServiceRequest.FromString(body)
            for path, body in received
            if path == "/v1/traces"
        ]
        metrics = [
            ExportMetricsServiceRequest.FromString(body)
            for path, body in received
            if path == "/v1/metrics"
        ]
        assert any(
            span.name == "integration.run"
            for request in traces
            for resource in request.resource_spans
            for scope in resource.scope_spans
            for span in scope.spans
        )
        names = {
            metric.name
            for request in metrics
            for resource in request.resource_metrics
            for scope in resource.scope_metrics
            for metric in scope.metrics
        }
        assert names >= {
            "jev.model.calls",
            "jev.model.tokens",
            "jev.model.duration",
            "jev.model.estimated_cost",
        }
    finally:
        telemetry.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
