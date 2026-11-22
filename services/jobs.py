# """
# jobs.py
# -------
# Background job execution + per-job event log, powering real-time progress (SSE).

# Flow:
#   POST /analyze          → create_job(), submit() to the worker pool, return job_id (~ms)
#   worker thread          → runs the LangGraph pipeline; agents call emit() as they progress
#   GET /jobs/{id}/stream  → replays all past events, then streams new ones as they arrive

# Design notes:
#   - Events are appended to an in-memory, per-job list. Late or reconnecting
#     subscribers replay from any event id (SSE Last-Event-ID), so a dropped
#     connection or a page refresh never loses progress.
#   - A bounded worker pool runs the blocking pipeline off the web server's threads.
#   - Backpressure: pending_count() lets the API refuse new work when the queue is full.
#   - Finished jobs are kept for JOB_TTL_SECS, then cleaned up.
#   - Single-process by design. Scaling to multiple server processes means moving
#     this event log to Redis pub/sub — the emit()/events_since() interface stays the same.
# """

# import os
# import time
# import threading
# from dataclasses import dataclass, field
# from concurrent.futures import ThreadPoolExecutor

# from logger import get_logger

# log = get_logger(__name__)

# JOB_WORKERS     = int(os.environ.get("JOB_WORKERS", "8"))
# JOB_MAX_PENDING = int(os.environ.get("JOB_MAX_PENDING", "50"))
# JOB_TTL_SECS    = int(os.environ.get("JOB_TTL_SECS", "3600"))

# _executor = ThreadPoolExecutor(max_workers=JOB_WORKERS, thread_name_prefix="analysis")


# @dataclass
# class Job:
#     id         : str
#     status     : str = "queued"            # queued → running → done | failed
#     created_at : float = field(default_factory=time.time)
#     finished_at: float | None = None
#     events     : list = field(default_factory=list)
#     lock       : threading.Lock = field(default_factory=threading.Lock, repr=False)


# _jobs: dict[str, Job] = {}
# _registry_lock = threading.Lock()


# def _cleanup_expired() -> None:
#     cutoff = time.time() - JOB_TTL_SECS
#     with _registry_lock:
#         expired = [jid for jid, j in _jobs.items() if j.finished_at and j.finished_at < cutoff]
#         for jid in expired:
#             del _jobs[jid]


# def create_job(job_id: str) -> Job:
#     _cleanup_expired()
#     job = Job(id=job_id)
#     with _registry_lock:
#         _jobs[job_id] = job
#     emit(job_id, "queued", {})
#     return job


# def get_job(job_id: str) -> Job | None:
#     with _registry_lock:
#         return _jobs.get(job_id)


# def pending_count() -> int:
#     with _registry_lock:
#         return sum(1 for j in _jobs.values() if j.status in ("queued", "running"))


# def emit(job_id: str, event: str, data: dict | None = None) -> None:
#     """Append an event to a job's log. No-op if the job doesn't exist (e.g. CLI tests)."""
#     if not job_id:
#         return
#     job = get_job(job_id)
#     if job is None:
#         return
#     with job.lock:
#         job.events.append({"id": len(job.events), "event": event, "data": data or {}})


# def events_since(job: Job, index: int) -> list[dict]:
#     with job.lock:
#         return job.events[index:]


# def submit(job_id: str, fn, *args) -> None:
#     """Run fn(*args) on the worker pool. fn returns True on success, False on handled failure."""
#     job = get_job(job_id)

#     def run():
#         job.status = "running"
#         try:
#             ok = fn(*args)
#             job.status = "done" if ok else "failed"
#         except Exception as e:
#             log.exception(f"[Jobs] {job_id[:8]} crashed: {e}")
#             emit(job_id, "error", {"detail": "Analysis failed unexpectedly. Please try again."})
#             job.status = "failed"
#         finally:
#             job.finished_at = time.time()

#     _executor.submit(run)


# def shutdown() -> None:
#     _executor.shutdown(wait=False, cancel_futures=True)

"""
services/jobs.py — Redis-backed job queue (replaces in-memory dict)

Public API is identical to the original so app.py and agents.py need no changes.

Redis key layout
----------------
  job:{id}:meta    HASH   status, created_at, finished_at
  job:{id}:events  LIST   JSON-encoded {event, data} entries

Env vars
--------
REDIS_URL       redis://[:password@]host:port/db   (default redis://localhost:6379/0)
JOB_WORKERS     ThreadPoolExecutor workers          (default 8)
JOB_MAX_PENDING backpressure limit (queued+running) (default 50)
JOB_TTL_SECS    expire keys after N seconds         (default 3600)
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import redis

from logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JOB_WORKERS     = int(os.environ.get("JOB_WORKERS",     "8"))
JOB_MAX_PENDING = int(os.environ.get("JOB_MAX_PENDING", "50"))
JOB_TTL_SECS    = int(os.environ.get("JOB_TTL_SECS",   "3600"))
REDIS_URL        = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Redis client (module-level singleton, thread-safe)
# ---------------------------------------------------------------------------

_redis: redis.Redis | None = None


def _r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            REDIS_URL,
            decode_responses=True,   # all keys/values come back as str
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        _redis.ping()   # fail fast on misconfiguration
        log.info(f"[Jobs] Redis connected: {REDIS_URL}")
    return _redis


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

def _meta_key(job_id: str) -> str:
    return f"job:{job_id}:meta"


def _events_key(job_id: str) -> str:
    return f"job:{job_id}:events"


def _set_ttl(job_id: str) -> None:
    """Refresh TTL on both keys (called when job reaches a terminal state)."""
    r = _r()
    r.expire(_meta_key(job_id),   JOB_TTL_SECS)
    r.expire(_events_key(job_id), JOB_TTL_SECS)


# ---------------------------------------------------------------------------
# RedisJob — thin proxy so callers can do `job.status`, `job.id`
# ---------------------------------------------------------------------------

class RedisJob:
    """
    Mimics the original Job dataclass interface.
    `.status`  → reads/writes the 'status' field in the Redis hash.
    `.id`      → the job UUID string.

    `events_since()` reads the Redis list directly, so the `.events` list
    attribute from the old in-memory Job is NOT needed here.
    """

    __slots__ = ("id",)

    def __init__(self, job_id: str) -> None:
        self.id = job_id

    # -- status property --------------------------------------------------- #

    @property
    def status(self) -> str:
        val = _r().hget(_meta_key(self.id), "status")
        return val if val is not None else "unknown"

    @status.setter
    def status(self, value: str) -> None:
        r = _r()
        r.hset(_meta_key(self.id), "status", value)
        if value in ("done", "failed"):
            r.hset(_meta_key(self.id), "finished_at", str(time.time()))
            _set_ttl(self.id)

    # -- convenience ------------------------------------------------------- #

    def exists(self) -> bool:
        return bool(_r().exists(_meta_key(self.id)))

    def __repr__(self) -> str:
        return f"<RedisJob id={self.id[:8]}… status={self.status}>"


# ---------------------------------------------------------------------------
# Thread pool (unchanged from original — Redis replaces storage, not workers)
# ---------------------------------------------------------------------------

_executor = ThreadPoolExecutor(
    max_workers=JOB_WORKERS, thread_name_prefix="analysis"
)

# ---------------------------------------------------------------------------
# Public API — signatures identical to the original jobs.py
# ---------------------------------------------------------------------------


def create_job(job_id: str) -> RedisJob:
    """Register a new job in Redis and emit the initial 'queued' event."""
    r = _r()
    pipe = r.pipeline()
    pipe.hset(_meta_key(job_id), mapping={
        "status"    : "queued",
        "created_at": str(time.time()),
    })
    pipe.expire(_meta_key(job_id), JOB_TTL_SECS)
    # push the initial queued event into the list atomically
    pipe.rpush(_events_key(job_id), json.dumps({"event": "queued", "data": {}}))
    pipe.expire(_events_key(job_id), JOB_TTL_SECS)
    pipe.execute()
    return RedisJob(job_id)


def get_job(job_id: str) -> RedisJob | None:
    """Return a RedisJob proxy, or None if the key does not exist / has expired."""
    if not _r().exists(_meta_key(job_id)):
        return None
    return RedisJob(job_id)


def pending_count() -> int:
    """
    Count jobs whose status is 'queued' or 'running'.

    Uses SCAN so it never blocks the Redis event loop; acceptable at our
    scale (≤ JOB_MAX_PENDING ≈ 50 live keys at any moment).
    """
    r   = _r()
    cnt = 0
    for key in r.scan_iter("job:*:meta", count=100):
        status = r.hget(key, "status")
        if status in ("queued", "running"):
            cnt += 1
    return cnt


def emit(job_id: str, event: str, data: dict | None = None) -> None:
    """
    Append one SSE event to the job's Redis list.

    RPUSH is atomic; no lock needed.  Silently no-ops if the job is gone
    (expired or never created) so callers don't need to guard.
    """
    if not job_id:
        return
    r = _r()
    if not r.exists(_meta_key(job_id)):
        return
    r.rpush(_events_key(job_id), json.dumps({"event": event, "data": data or {}}))


def events_since(job: RedisJob, index: int) -> list[dict]:
    """
    Return all events from `index` onward (0-based).

    The returned dicts include an `id` field equal to the event's absolute
    list index, which the SSE stream uses as the Last-Event-ID.
    """
    raw = _r().lrange(_events_key(job.id), index, -1)
    result = []
    for i, item in enumerate(raw):
        ev = json.loads(item)
        ev["id"] = index + i      # absolute list position = SSE id
        result.append(ev)
    return result


def submit(job_id: str, fn, *args) -> None:
    """
    Submit `fn(*args)` to the thread pool.

    Mirrors the original: sets status→running before the call, then
    done/failed after.  The fn itself calls `emit()` for progress events;
    terminal status transitions trigger TTL refresh via the status setter.
    """
    def _run() -> None:
        job = get_job(job_id)
        if job is None:
            log.warning(f"[Jobs] submit: job {job_id[:8]}… not found in Redis")
            return
        job.status = "running"
        try:
            ok = fn(*args)
            job.status = "done" if ok else "failed"
        except Exception as exc:
            log.exception(f"[Jobs] {job_id[:8]}… crashed: {exc}")
            emit(job_id, "error", {"detail": "Analysis failed unexpectedly. Please try again."})
            job.status = "failed"

    _executor.submit(_run)


def shutdown() -> None:
    """Graceful shutdown — mirrors original behaviour."""
    _executor.shutdown(wait=False, cancel_futures=True)
    log.info("[Jobs] Executor shut down")