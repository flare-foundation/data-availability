import json
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from project.logging import CallerFilter, JsonFormatter, TextFormatter


def _record():
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "hello", None, None, func="f"
    )
    CallerFilter().filter(record)
    return record


def test_console_fields_stay_off_the_record():
    record = _record()
    formatter = TextFormatter(
        fmt="[{datetime}] {trace_context}{caller}: {message}", style="{"
    )

    with TracerProvider().get_tracer(__name__).start_as_current_span("span") as span:
        line = formatter.format(record)

    trace_id = trace.format_trace_id(span.get_span_context().trace_id)
    assert f"[trace_id={trace_id} " in line
    assert line.endswith("project/tests/test_logging.py:f:1: hello")
    # the OTLP handler exports leftover record attributes
    for field in ("timestamp", "datetime", "trace_context", "trace_id", "span_id"):
        assert not hasattr(record, field)


def test_json_formatter_has_trace_ids_as_fields():
    formatter = JsonFormatter(fmt="%(timestamp)s %(datetime)s %(message)s")

    with TracerProvider().get_tracer(__name__).start_as_current_span("span") as span:
        data = json.loads(formatter.format(_record()))

    ctx = span.get_span_context()
    assert data["trace_id"] == trace.format_trace_id(ctx.trace_id)
    assert data["span_id"] == trace.format_span_id(ctx.span_id)
    assert data["datetime"]
    assert "trace_context" not in data


def test_json_formatter_without_span_has_no_trace_ids():
    data = json.loads(
        JsonFormatter(fmt="%(timestamp)s %(datetime)s %(message)s").format(_record())
    )

    assert "trace_id" not in data
    assert "trace_context" not in data
