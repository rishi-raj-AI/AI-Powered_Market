"""Bounded media queue processing with leased jobs and configured storage.

Production activation requires validated private/public object storage,
scanner credentials, and operational cleanup for abandoned objects.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.product_media import ProductMediaAsset, ProductMediaJob
from app.services.product_media import claim_due_media_job, complete_media_job, expire_exhausted_media_jobs
from app.services.product_media_processing import MediaScanUnavailable
from app.services.product_media_publication import process_quarantined_asset
from app.services.product_media_storage import HttpContentScanner, configured_media_storage


def process_due_media_jobs(*, limit: int = 10) -> dict[str, int]:
    if not settings.PRODUCT_MEDIA_ENABLED:
        return {"considered": 0}
    if settings.MEDIA_STORAGE_BACKEND == "local" and settings.APP_ENV not in {"development", "test"}:
        raise RuntimeError("Local media storage is development-only")
    if settings.MEDIA_SCAN_PROVIDER != "http":
        raise RuntimeError("A mandatory HTTP scanner is required")
    storage = configured_media_storage()
    scanner = HttpContentScanner(settings.MEDIA_SCAN_ENDPOINT_URL, settings.MEDIA_SCAN_AUTH_TOKEN)
    counts = {"considered": 0, "approved": 0, "rejected": 0, "retried": 0, "expired": 0}
    with SessionLocal() as db:
        counts["expired"] = expire_exhausted_media_jobs(db, limit=max(1, limit))
        db.commit()
    for _ in range(max(0, min(limit, settings.MEDIA_JOB_BATCH))):
        with SessionLocal() as db:
            job = claim_due_media_job(db)
            if job is None:
                break
            job_id = job.id
            asset_id = job.asset_id
            claim_attempt = job.attempt_count
            db.commit()
        counts["considered"] += 1
        with SessionLocal() as db:
            job = db.get(ProductMediaJob, job_id, with_for_update=True)
            asset = db.get(ProductMediaAsset, asset_id, with_for_update=True)
            if job is None or job.state != "processing" or job.attempt_count != claim_attempt:
                continue
            if job.lease_expires_at is None or job.lease_expires_at <= datetime.now(timezone.utc):
                # An expired claim must never publish an image.
                continue
            if asset is None:
                complete_media_job(job, outcome="rejected", failure_code="asset_missing")
                db.commit()
                counts["rejected"] += 1
                continue
            # Recover a committed publication if the worker crashed before
            # committing the corresponding job completion.
            if (asset.state == "approved" and asset.public_object_key
                    and asset.derivative_sha256 and getattr(asset, "retired_at", None) is None):
                complete_media_job(job, outcome="approved")
                db.commit()
                counts["approved"] += 1
                continue
            if asset.state in {"rejected", "retired"} or getattr(asset, "retired_at", None) is not None:
                complete_media_job(job, outcome="rejected", failure_code="asset_not_eligible")
                db.commit()
                counts["rejected"] += 1
                continue
            # The public object store is not part of the SQL transaction.
            # Track newly written objects so a rollback cannot leave an
            # unaudited, externally readable derivative behind.
            published_key = None
            try:
                result = process_quarantined_asset(
                    db, asset=asset, storage=storage, scanner=scanner,
                    request_id=f"media-job-{job_id}",
                )
                published_key = asset.public_object_key
                outcome = result.state if result.state in {"approved", "rejected"} else "retry"
                if outcome == "approved" and (not published_key or not asset.derivative_sha256):
                    raise RuntimeError("Approved asset has no verified public derivative")
                if job.lease_expires_at is None or job.lease_expires_at <= datetime.now(timezone.utc):
                    db.rollback()
                    if published_key:
                        try:
                            storage.delete_public_derivative(published_key)
                        except Exception:
                            # Preserve the original lease-expiry outcome.
                            # A durable orphan sweeper is still required.
                            pass
                    continue
                complete_media_job(job, outcome=outcome, failure_code=result.reason)
                db.commit()
                counts["retried" if outcome == "retry" else outcome] += 1
            except Exception as exc:
                db.rollback()
                if published_key:
                    try:
                        storage.delete_public_derivative(published_key)
                    except Exception:
                        # Cleanup must not mask the original error; a storage
                        # lifecycle sweeper is still needed for hard crashes.
                        pass
                with SessionLocal() as retry_db:
                    retry_job = retry_db.get(ProductMediaJob, job_id, with_for_update=True)
                    if (retry_job is not None and retry_job.state == "processing"
                            and retry_job.attempt_count == claim_attempt
                            and retry_job.lease_expires_at is not None
                            and retry_job.lease_expires_at > datetime.now(timezone.utc)):
                        failure_code = "scanner_unavailable" if isinstance(exc, MediaScanUnavailable) else "processing_error"
                        complete_media_job(retry_job, outcome="retry", failure_code=failure_code)
                        retry_db.commit()
                        counts["retried"] += 1
                continue
    return counts
