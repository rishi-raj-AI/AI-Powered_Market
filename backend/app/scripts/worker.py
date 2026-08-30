"""GaonOne background worker.

Drains the two queues that carry obligations out of the request path: the
notification outbox and owed customer refunds. Runs as a long-lived process so
neither queue depends on someone remembering to press a button.

Restart-safe: every unit of work is claimed under a row lock and is idempotent,
so a worker killed mid-tick loses nothing and a second worker duplicates
nothing.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

from app.db.session import SessionLocal
from app.services.fcm import flush_pending
from app.services.refunds import dispatch_due_refunds

logging.basicConfig(
    level=os.environ.get("WORKER_LOG_LEVEL", "INFO"),
    format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger("gaonone.worker")

POLL_SECONDS = int(os.environ.get("WORKER_POLL_SECONDS", "20"))
NOTIFICATION_BATCH = int(os.environ.get("WORKER_NOTIFICATION_BATCH", "100"))
REFUND_BATCH = int(os.environ.get("WORKER_REFUND_BATCH", "25"))

_running = True


def _stop(signum, _frame) -> None:
    global _running
    logger.info("Worker received signal %s; finishing current tick", signum)
    _running = False


def tick() -> dict[str, dict]:
    """One pass over both queues. Each is isolated so one cannot stall the other."""
    result: dict[str, dict] = {}
    try:
        with SessionLocal() as db:
            result["notifications"] = flush_pending(db, limit=NOTIFICATION_BATCH)
    except Exception:
        logger.exception("Notification flush failed")
        result["notifications"] = {"error": 1}
    try:
        with SessionLocal() as db:
            result["refunds"] = dispatch_due_refunds(db, limit=REFUND_BATCH)
    except Exception:
        logger.exception("Refund dispatch failed")
        result["refunds"] = {"error": 1}
    return result


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("Worker started poll_seconds=%s", POLL_SECONDS)
    while _running:
        outcome = tick()
        notifications = outcome.get("notifications", {})
        refunds = outcome.get("refunds", {})
        if notifications.get("events") or refunds.get("considered"):
            logger.info("Worker tick notifications=%s refunds=%s", notifications, refunds)
        for _ in range(POLL_SECONDS):
            if not _running:
                break
            time.sleep(1)
    logger.info("Worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
