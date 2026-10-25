"""OpenTelemetry spans export metadata only; prompts and outputs are excluded."""

import os
from contextlib import contextmanager

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
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
        self.tracer = self.provider.get_tracer("jev.harness", "0.1.0")

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

    def close(self):
        self.provider.shutdown()
