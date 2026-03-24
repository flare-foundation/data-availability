import logging
import os
from datetime import UTC, datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# app-level directories whose caller info is useful
_APP_DIRS = ("ftso", "fdc", "fsp", "processing", "configuration", "project")


class CallerFilter(logging.Filter):
    """injects timestamp and caller info into every record"""

    def filter(self, record):
        record.timestamp = record.created
        record.datetime = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        path = os.path.relpath(record.pathname, _ROOT)
        if path.startswith(_APP_DIRS):
            record.caller = f"{path}:{record.funcName}:{record.lineno}"
        else:
            record.caller = record.name
        return True
