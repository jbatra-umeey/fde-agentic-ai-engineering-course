"""OpenTelemetry spans export metadata only; prompts and outputs are excluded."""

import os
from contextlib import contextmanager

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import Status, StatusCode


class Telemetry:
    def __init__(self, exporter=None):
        self.provider = TracerProvider(
            resource=Resource.create({"service.name": "jev-agent-engineering"}),
            sampler=ALWAYS_ON if exporter is not None else None,
        )
        endpoint = os.getenv("JEV_OTLP_TRACES_ENDPOINT")
        if exporter is not None:
            self.provider.add_span_processor(BatchSpanProcessor(exporter))
        elif endpoint:
            self.provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=3))
            )
        self.tracer = self.provider.get_tracer("jev.harness", "0.2.0")
        metrics_endpoint = os.getenv("JEV_OTLP_METRICS_ENDPOINT")
        readers = (
            [
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=metrics_endpoint, timeout=3)
                )
            ]
            if metrics_endpoint
            else []
        )
        self.meter_provider = MeterProvider(
            resource=Resource.create({"service.name": "jev-agent-engineering"}),
            metric_readers=readers,
        )
        meter = self.meter_provider.get_meter("jev.inference", "0.2.0")
        self.calls = meter.create_counter("jev.model.calls")
        self.tokens = meter.create_counter("jev.model.tokens")
        self.cost = meter.create_counter("jev.model.estimated_cost", unit="USD")
        self.latency = meter.create_histogram("jev.model.duration", unit="ms")

    @contextmanager
    def span(self, name, **attributes):
        with self.tracer.start_as_current_span(
            name, attributes=attributes, record_exception=False, set_status_on_exception=False
        ) as s:
            try:
                yield s
            except BaseException as exc:
                s.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                raise

    def inference(self, record):
        labels = {k: record[k] for k in ("provider", "model", "route", "status")}
        self.calls.add(1, labels)
        self.latency.record(record["latency_ms"], labels)
        for kind in ("input", "output"):
            count = record.get(kind + "_tokens")
            if count is not None:
                self.tokens.add(count, {**labels, "direction": kind})
        if record.get("cost_usd") is not None:
            self.cost.add(record["cost_usd"], labels)

    def close(self):
        self.provider.shutdown()
        self.meter_provider.shutdown()
