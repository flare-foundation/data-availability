import logging
import os

logger = logging.getLogger(__name__)
_initialized = False


def setup_telemetry() -> None:
    global _initialized
    if _initialized:
        return

    if os.environ.get("OTEL_ENABLED", "false").lower() == "true":
        try:
            from opentelemetry.instrumentation.auto_instrumentation import initialize

            initialize()
            _initialized = True
            logger.info(
                "OpenTelemetry programmatic auto-instrumentation initialized successfully."
            )
        except Exception:
            logger.exception("Failed to initialize OpenTelemetry auto-instrumentation.")
