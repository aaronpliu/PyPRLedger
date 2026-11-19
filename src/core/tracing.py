"""Distributed tracing via OpenTelemetry.

Tracing is opt-in: with ``OTEL_ENABLED=false`` (the default) the application
starts exactly as before, and a missing SDK install is a warning, not a crash.
When enabled, spans export over OTLP/HTTP to the configured collector - the
Jaeger all-in-one in ``monitoring/docker-compose.yml`` is the local answer -
and the calls the application actually makes are instrumented automatically:

- FastAPI: every request becomes a server span (health and metrics probes are
  excluded, they would otherwise flood the trace with scrapes)
- SQLAlchemy: every query becomes a child span of the request
- Redis: cache reads and pub/sub as child spans
- HTTPX: every Git provider call as a child span, so a slow diff reads hop by
  hop without any service code knowing tracing exists

The trace ids also ride in every log line (see ``TraceContextFilter``), so a
slow request in the logs jumps straight to its span view in Jaeger.
"""

from __future__ import annotations

import logging

from src import __version__
from src.core.config import settings
from src.core.database import get_engine


logger = logging.getLogger(__name__)

try:  # the SDK lives in the `monitoring` extra; without it tracing stays off
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the installed extra
    _OTEL_AVAILABLE = False

# Probes answer every few seconds forever; tracing them would flood the
# collector with spans that say nothing about a real request.
_EXCLUDED_URLS = "api/health,api/health/ready,api/metrics"


def setup_tracing(app) -> None:
    """Instrument the application when tracing is enabled. Never raises."""
    if not settings.OTEL_ENABLED:
        logger.debug("Distributed tracing disabled (OTEL_ENABLED=false)")
        return

    if not _OTEL_AVAILABLE:
        logger.warning(
            "OTEL_ENABLED is true but the OpenTelemetry packages are missing; "
            "run `uv sync --extra monitoring` to install them. Tracing stays off."
        )
        return

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": __version__,
            "deployment.environment": settings.ENV,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT))
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=_EXCLUDED_URLS)
    try:
        engine = get_engine()
    except RuntimeError:  # not initialized (or tests); queries stay uninstrumented
        engine = None
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)

    logger.info(
        "Distributed tracing enabled: service=%s, spans export to %s",
        settings.OTEL_SERVICE_NAME,
        settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )


def shutdown_tracing() -> None:
    """Flush whatever spans the batch processor still holds, best effort."""
    if not settings.OTEL_ENABLED or not _OTEL_AVAILABLE:
        return
    try:
        provider = trace.get_tracer_provider()
        shutdown = getattr(provider, "shutdown", None)
        if shutdown is not None:
            shutdown()
        logger.info("Distributed tracing shut down")
    except Exception as exc:  # pragma: no cover - shutdown is best effort
        logger.warning("Failed to shut down tracing cleanly: %s", exc)
