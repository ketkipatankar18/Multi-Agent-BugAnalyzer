"""
logger.py
---------
Structured logging for BugAnalyzer.

Every line carries a timestamp, level, module and the short request ID:
  2026-10-01 12:04:31 INFO    [a3f9c2d1] agents: [Severity] Done — severity=Critical

So `grep a3f9c2d1 logs/app.log` shows one request's full journey,
even when many requests run at the same time.

The request ID travels via contextvars: set once per request, readable from
any function handling that request — no need to pass it through every call.
"""

import os
import logging
import contextvars
from logging.handlers import RotatingFileHandler

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _ContextFilter(logging.Filter):
    """Adds the current request ID and a short module name to every record."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.module_short = record.name.removeprefix("buganalyzer.")
        return True


_configured = False

def _configure() -> None:
    global _configured
    if _configured:
        return

    base = logging.getLogger("buganalyzer")
    base.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    base.propagate = False   # keep library logs (httpx etc.) out of our output

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(request_id)s] %(module_short)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ctx = _ContextFilter()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(ctx)
    base.addHandler(console)

    log_path = os.environ.get("APP_LOG_PATH", "logs/app.log")
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(ctx)
    base.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Usage at the top of a module:  log = get_logger(__name__)"""
    _configure()
    return logging.getLogger(f"buganalyzer.{name.split('.')[-1]}")


def set_request_id(request_id: str) -> contextvars.Token:
    """Set the request ID for everything logged in the current context."""
    return request_id_var.set(request_id[:8] if request_id else "-")