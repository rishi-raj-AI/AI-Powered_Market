import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.routes.media import list_merchant_listing_images
from app.models.user import UserRole


def test_missing_listing_returns_404():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        list_merchant_listing_images(uuid.uuid4(), db=db, user=SimpleNamespace(id=uuid.uuid4(), role=UserRole.MERCHANT))
    assert exc.value.status_code == 404


def test_other_merchant_cannot_read_private_images():
    listing_id, store_id, merchant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(id=listing_id, store_id=store_id),
        SimpleNamespace(id=store_id, merchant_id=merchant_id),
        SimpleNamespace(id=merchant_id, owner_user_id=uuid.uuid4()),
    ]
    with pytest.raises(HTTPException) as exc:
        list_merchant_listing_images(listing_id, db=db, user=SimpleNamespace(id=uuid.uuid4(), role=UserRole.MERCHANT))
    assert exc.value.status_code == 403
    db.scalars.assert_not_called()


def test_owner_gets_only_safe_metadata():
    listing_id, store_id, merchant_id, owner_id = (uuid.uuid4() for _ in range(4))
    from datetime import datetime, timezone
    asset = SimpleNamespace(
        id=uuid.uuid4(), state="quarantined", alt_text="Rice bag", position=0,
        is_primary=False, created_at=datetime.now(timezone.utc),
        source_object_key="private/secret-key", public_object_key="private/other-key",
    )
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(id=listing_id, store_id=store_id),
        SimpleNamespace(id=store_id, merchant_id=merchant_id),
        SimpleNamespace(id=merchant_id, owner_user_id=owner_id),
    ]
    db.scalars.return_value.all.return_value = [asset]
    result = list_merchant_listing_images(listing_id, db=db, user=SimpleNamespace(id=owner_id, role=UserRole.MERCHANT))
    assert len(result) == 1
    assert result[0]["state"] == "quarantined"
    assert "source_object_key" not in result[0]
    assert "public_object_key" not in result[0]


def test_public_images_require_available_listing():
    from app.api.v1.routes.media import public_approved_listing_images
    db = MagicMock()
    db.get.return_value = SimpleNamespace(is_available=False, stock_quantity=0)
    with pytest.raises(HTTPException) as exc:
        public_approved_listing_images(uuid.uuid4(), db=db)
    assert exc.value.status_code == 404
    db.scalars.assert_not_called()


def test_public_images_require_active_approved_merchant():
    from app.api.v1.routes.media import public_approved_listing_images
    listing_id, store_id, merchant_id = (uuid.uuid4() for _ in range(3))
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(is_available=True, stock_quantity=4, store_id=store_id),
        SimpleNamespace(is_active=True, merchant_id=merchant_id),
        SimpleNamespace(status=SimpleNamespace(value="pending")),
    ]
    with pytest.raises(HTTPException) as exc:
        public_approved_listing_images(listing_id, db=db)
    assert exc.value.status_code == 404
    db.scalars.assert_not_called()


def test_public_store_images_rejects_inactive_store():
    from app.api.v1.routes.media import public_store_approved_images
    db = MagicMock()
    db.get.return_value = SimpleNamespace(is_active=False, merchant_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        public_store_approved_images(uuid.uuid4(), limit=100, db=db)
    assert exc.value.status_code == 404
    db.scalars.assert_not_called()


def test_public_store_images_rejects_unapproved_merchant():
    from app.api.v1.routes.media import public_store_approved_images
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(is_active=True, merchant_id=uuid.uuid4()),
        SimpleNamespace(status=SimpleNamespace(value="pending")),
    ]
    with pytest.raises(HTTPException) as exc:
        public_store_approved_images(uuid.uuid4(), limit=100, db=db)
    assert exc.value.status_code == 404
    db.scalars.assert_not_called()


def test_media_job_claim_leases_one_due_job(monkeypatch):
    from datetime import datetime, timezone
    from app.services.product_media import claim_due_media_job
    from app.services import product_media
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    job = SimpleNamespace(state="queued", attempt_count=0, lease_expires_at=None, next_attempt_at=None)
    db = MagicMock()
    db.scalar.return_value = job
    monkeypatch.setattr(product_media.settings, "MEDIA_JOB_LEASE_SECONDS", 120)
    assert claim_due_media_job(db, now=now) is job
    assert job.state == "processing"
    assert job.attempt_count == 1
    assert job.lease_expires_at > now


def test_media_job_retry_exhaustion_and_completion(monkeypatch):
    from datetime import datetime, timezone
    from app.services.product_media import complete_media_job
    from app.services import product_media
    monkeypatch.setattr(product_media.settings, "MEDIA_JOB_MAX_ATTEMPTS", 3)
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    job = SimpleNamespace(state="processing", attempt_count=1, failure_code=None, next_attempt_at=None, lease_expires_at=now)
    complete_media_job(job, outcome="retry", now=now)
    assert job.state == "queued" and job.next_attempt_at > now
    assert job.lease_expires_at is None
    job.attempt_count = 3
    complete_media_job(job, outcome="retry", now=now)
    assert job.state == "failed" and job.failure_code == "max_attempts_exceeded"
    complete_media_job(job, outcome="approved", now=now)
    assert job.state == "completed" and job.failure_code is None
