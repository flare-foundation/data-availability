import logging
import os
from datetime import UTC, datetime

from opentelemetry import trace
from pythonjsonlogger.json import JsonFormatter as BaseJsonFormatter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# app-level directories whose caller info is useful
_APP_DIRS = ("ftso", "fdc", "fsp", "processing", "configuration", "project")


class CallerFilter(logging.Filter):
    """injects caller info into every record"""

    def filter(self, record):
        path = os.path.relpath(record.pathname, _ROOT)
        if path.startswith(_APP_DIRS):
            record.caller = f"{path}:{record.funcName}:{record.lineno}"
        else:
            record.caller = record.name
        return True


class _ConsoleFields:
    """Adds console-only fields to a copy of the record.

    The OTLP log handler sees the same record and has these natively.
    """

    def format(self, record):
        record = logging.makeLogRecord(record.__dict__)
        record.timestamp = record.created
        record.datetime = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            # separate fields for the JSON format, which emits extra record attributes
            record.trace_id = trace.format_trace_id(ctx.trace_id)
            record.span_id = trace.format_span_id(ctx.span_id)
            record.trace_context = (
                f"[trace_id={record.trace_id} span_id={record.span_id}] "
            )
        else:
            record.trace_context = ""
        return super().format(record)


class TextFormatter(_ConsoleFields, logging.Formatter):
    pass


class JsonFormatter(_ConsoleFields, BaseJsonFormatter):
    def process_log_record(self, log_data):
        # only the text format uses it
        log_data.pop("trace_context", None)
        return log_data
