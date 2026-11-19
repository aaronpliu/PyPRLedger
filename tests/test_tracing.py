"""Tests for the OpenTelemetry tracing setup.

Tracing is opt-in, so the tests pin the contract the app depends on: off by
default (nothing is instrumented, nothing is set globally), degraded to a
warning (not a crash) when the SDK is missing, and when enabled the provider,
exporter and the four instrumentations are wired so spans would flow - with a
stand-in exporter so nothing leaves the test process.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from src.utils.log import TraceContextFilter


class StandInExporter:
    """An exporter that records its endpoint instead of shipping spans."""

    endpoints: list[str] = []

    def __init__(self, endpoint: str = "", *args, **kwargs) -> None:
        StandInExporter.endpoints.append(endpoint)

    def export(self, *args, **kwargs) -> int:
        return 0

    def shutdown(self) -> None:
        return None


@pytest.fixture(autouse=True)
def restore_global_state():
    """Undo whatever a test instruments, so none of it leaks between tests."""
    yield
    StandInExporter.endpoints.clear()
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        RedisInstrumentor().uninstrument()
        HTTPXClientInstrumentor().uninstrument()
        SQLAlchemyInstrumentor().uninstrument()
    except ImportError:
        pass


def test_disabled_by_default_instruments_nothing() -> None:
    from src.core.tracing import setup_tracing

    app = FastAPI()
    setup_tracing(app)

    # an uninstrumented app carries no otel marker
    assert not getattr(app, "_is_instrumented_by_opentelemetry", False)


def test_enabled_wires_provider_exporter_and_instrumentations() -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    import src.core.tracing as tracing_module

    app = FastAPI()
    with (
        patch.object(tracing_module.settings, "OTEL_ENABLED", True),
        patch.object(tracing_module.settings, "OTEL_SERVICE_NAME", "test-backend"),
        patch.object(tracing_module, "OTLPSpanExporter", StandInExporter),
    ):
        tracing_module.setup_tracing(app)

    # the global provider is ours and the request instrumentation is on
    assert isinstance(trace.get_tracer_provider(), TracerProvider)
    assert getattr(app, "_is_instrumented_by_opentelemetry", False) is True
    # the exporter points where the settings say
    assert StandInExporter.endpoints == [tracing_module.settings.OTEL_EXPORTER_OTLP_ENDPOINT]


def test_missing_sdk_degrades_to_warning_not_crash(caplog) -> None:
    import src.core.tracing as tracing_module

    app = FastAPI()
    with (
        patch.object(tracing_module.settings, "OTEL_ENABLED", True),
        patch.object(tracing_module, "_OTEL_AVAILABLE", False),
        caplog.at_level(logging.WARNING),
    ):
        # must not raise: an incomplete install costs a warning, not an outage
        tracing_module.setup_tracing(app)

    assert "monitoring" in caplog.text


def test_trace_context_filter_always_leaves_ids_on_the_record() -> None:
    # with no active span the ids are the dash placeholder, so the same
    # formatter works whether tracing is on or off
    the_filter = TraceContextFilter()
    record = logging.LogRecord(
        "test", logging.INFO, "path.py", 1, "hello", None, None
    )
    assert the_filter.filter(record) is True
    assert record.trace_id == "-"
    assert record.span_id == "-"


def test_trace_context_filter_carries_the_active_span_ids() -> None:
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    # a local provider, not the process global: the global refuses to be
    # replaced once set, and this test only needs a recording span
    tracer = TracerProvider().get_tracer("test")
    span = tracer.start_span("probe")
    with trace.use_span(span):
        the_filter = TraceContextFilter()
        record = logging.LogRecord(
            "test", logging.INFO, "path.py", 1, "hello", None, None
        )
        the_filter.filter(record)

        context = span.get_span_context()
        assert record.trace_id == format(context.trace_id, "032x")
        assert record.span_id == format(context.span_id, "016x")
