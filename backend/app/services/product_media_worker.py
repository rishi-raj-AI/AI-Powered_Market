"""Bounded media queue processing for local development and tests.

Production storage is deliberately unsupported until an authenticated
private/public object-store adapter is configured and validated.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.product_media import ProductMediaAsset, ProductMediaJob
from app.services.product_media import claim_due_media_job, complete_media_job
from app.services.product_media_processing import MediaScanUnavailable
from app.services.product_media_publication import process_quarantined_asset
from app.services.product_media_storage import HttpContentScanner, LocalObjectStorage


def process_due_media_jobs(*, limit: int = 10) -> dict[str, int]:
    if not settings.PRODUCT_MEDIA_ENABLED:
        return {"considered": 0}
    if settings.MEDIA_STORAGE_BACKEND != "local" or settings.APP_ENV not in {"development", "test"}:
        raise RuntimeError("Production media storage adapter is not configured")
    if settings.MEDIA_SCAN_PROVIDER != "http":
        raise RuntimeError("A mandatory HTTP scanner is required")
    storage = LocalObjectStorage(Path("data/media/quarantine"), Path("data/media/public"))
    scanner = HttpContentScanner(settings.MEDIA_SCAN_ENDPOINT_URL, settings.MEDIA_SCAN_AUTH_TOKEN)
    counts = {"considered": 0, "approved": 0, "rejected": 0, "retried": 0}
    for _ in range(max(0, min(limit, settings.MEDIA_JOB_BATCH))):
        with SessionLocal() as db:
            job = claim_due_media_job(db)
            if job is None:
                break
            job_id = job.id
            asset_id = job.asset_id
            db.commit()
        counts["considered"] += 1
        with SessionLocal() as db:
            job = db.get(ProductMediaJob, job_id, with_for_update=True)
            asset = db.get(ProductMediaAsset, asset_id, with_for_update=True)
            if job is None or job.state != "processing":
                continue
            if job.lease_expires_at is None or job.lease_expires_at <= datetime.now(timezone.utc):
                # An expired claim must never publish an image.
                continue
            if asset is None:
                complete_media_job(job, outcome="rejected", failure_code="asset_missing")
                db.commit()
                counts["rejected"] += 1
                continue
            try:
                result = process_quarantined_asset(
                    db, asset=asset, storage=storage, scanner=scanner,
                    request_id=f"media-job-{job_id}",
                )
                outcome = result.state if result.state in {"approved", "rejected"} else "retry"
                complete_media_job(job, outcome=outcome, failure_code=result.reason)
                counts["retried" if outcome == "retry" else outcome] += 1
            except MediaScanUnavailable:
                db.rollback()
                with SessionLocal() as retry_db:
                    retry_job = retry_db.get(ProductMediaJob, job_id, with_for_update=True)
                    if retry_job is not None and retry_job.state == "processing":
                        complete_media_job(retry_job, outcome="retry", failure_code="scanner_unavailable")
                        retry_db.commit()
                        counts["retried"] += 1
                continue
            except Exception:
                # Roll back any partial asset changes, then record a durable retry.
                db.rollback()
                with SessionLocal() as retry_db:
                    retry_job = retry_db.get(ProductMediaJob, job_id, with_for_update=True)
                    if retry_job is not None and retry_job.state == "processing":
                        complete_media_job(retry_job, outcome="retry", failure_code="processing_error")
                        retry_db.commit()
                        counts["retried"] += 1
                continue
            db.commit()
    return counts
