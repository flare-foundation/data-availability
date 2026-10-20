import logging
import os
from datetime import UTC, datetime

from opentelemetry import trace
from pythonjsonlogger.json import JsonFormatter as BaseJsonFormatter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# app-level directories whose caller info is useful
_APP_DIRS = ("ftso", "fdc", "fsp", "processing", "configuration", "project")


class CallerFilter(logging.Filter):
    """injects timestamp, caller info, and OTel trace context into every record"""

    def filter(self, record):
        record.timestamp = record.created
        record.datetime = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        path = os.path.relpath(record.pathname, _ROOT)
        if path.startswith(_APP_DIRS):
            record.caller = f"{path}:{record.funcName}:{record.lineno}"
        else:
            record.caller = record.name

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None

        if ctx and ctx.is_valid:
            trace_id = trace.format_trace_id(ctx.trace_id)
            span_id = trace.format_span_id(ctx.span_id)
            record.trace_context = f"[trace_id={trace_id} span_id={span_id}] "
        else:
            record.trace_context = ""

        return True


class JsonFormatter(BaseJsonFormatter):
    def process_log_record(self, log_data):
        # Helper used by the non-json logging
        log_data.pop("trace_context", None)
        return log_data
