"""
OpenTelemetry instrumentation helper for Elastic Document Intelligence Platform.
Exports distributed traces to Jaeger (or any OTLP-compliant collector) via HTTP.
"""

from __future__ import annotations

import atexit
import os
import sys
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


DEFAULT_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "docling-platform")

_tracer: Optional[Any] = None
_provider: Optional[Any] = None


def init_tracer(service_name: str = SERVICE_NAME, endpoint: str = DEFAULT_OTLP_ENDPOINT) -> Any:
    """Initialize OpenTelemetry tracer provider with OTLP HTTP exporter."""
    global _tracer, _provider
    if not OTEL_AVAILABLE:
        return None

    if _tracer is not None:
        return _tracer

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "document-intelligence",
            "service.version": "1.0.0",
        }
    )

    _provider = TracerProvider(resource=resource)
    try:
        exporter = OTLPSpanExporter(endpoint=endpoint, timeout=3)
        processor = BatchSpanProcessor(exporter, max_queue_size=512, schedule_delay_millis=500)
        _provider.add_span_processor(processor)
        trace.set_tracer_provider(_provider)
        _tracer = trace.get_tracer(service_name)

        def shutdown():
            try:
                _provider.shutdown()
            except Exception:
                pass

        atexit.register(shutdown)
    except Exception as e:
        print(f"[OTel WARN] Failed to initialize OTLP exporter at {endpoint}: {e}", file=sys.stderr)
        _tracer = trace.get_tracer(service_name)

    return _tracer


def get_tracer() -> Any:
    """Return configured OpenTelemetry tracer or initialize it if needed."""
    if _tracer is None:
        return init_tracer()
    return _tracer


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[Optional[Any], None, None]:
    """Context manager for creating OpenTelemetry spans with automatic status setting."""
    tracer = get_tracer()
    if not OTEL_AVAILABLE or tracer is None:
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(str(k), v if isinstance(v, (str, int, float, bool)) else str(v))
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
