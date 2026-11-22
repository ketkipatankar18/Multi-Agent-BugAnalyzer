"""
resilience.py
-------------
Single retry policy for every LLM / API call.

- Retries only TRANSIENT failures: rate limits (429), overload (529),
  server errors (5xx), timeouts, dropped connections.
- Never retries permanent failures (400 bad request, 401 bad key) —
  they won't fix themselves, so retrying only wastes time.
- Exponential backoff with full jitter: waits are randomized so many
  clients hitting a rate limit together don't retry in lockstep
  (thundering-herd prevention).
- SDK built-in retries are disabled (max_retries=0), so this is the only
  retry loop: bounded, consistent across providers, and logged.
"""

from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from logger import get_logger

log = get_logger(__name__)

MAX_ATTEMPTS      = 3
TRANSIENT_STATUS  = {408, 409, 429, 500, 502, 503, 504, 529}
TRANSIENT_NAMES   = ("timeout", "connection", "ratelimit", "overloaded", "unavailable", "internalserver")
TRANSIENT_MARKERS = ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "OVERLOADED", " 429", " 503")


def _status_of(exc: BaseException) -> int | None:
    """HTTP status from the various SDK exception shapes, if present."""
    for attr in ("status_code", "code", "http_status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    value = getattr(getattr(exc, "response", None), "status_code", None)
    return value if isinstance(value, int) else None


def is_transient(exc: BaseException) -> bool:
    status = _status_of(exc)
    if status is not None:
        return status in TRANSIENT_STATUS
    name = type(exc).__name__.lower()
    if any(n in name for n in TRANSIENT_NAMES):
        return True
    text = str(exc).upper()
    return any(m in text for m in TRANSIENT_MARKERS)


def _log_before_retry(label: str):
    def before_sleep(state):
        exc = state.outcome.exception()
        log.warning(
            f"[Retry] {label} attempt {state.attempt_number}/{MAX_ATTEMPTS} failed "
            f"({type(exc).__name__}: {str(exc)[:120]}) — retrying in {state.next_action.sleep:.1f}s"
        )
    return before_sleep


def with_retry(label: str, fn, *args, **kwargs):
    """
    Call fn(*args, **kwargs), retrying transient failures.
    Usage: with_retry("claude.draft", client.messages.create, model=..., messages=...)
    """
    for attempt in Retrying(
        stop         = stop_after_attempt(MAX_ATTEMPTS),
        wait         = wait_random_exponential(multiplier=1, max=20),
        retry        = retry_if_exception(is_transient),
        before_sleep = _log_before_retry(label),
        reraise      = True,
    ):
        with attempt:
            return fn(*args, **kwargs)