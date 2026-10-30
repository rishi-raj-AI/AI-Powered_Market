"""Feature-gate checks for the product media worker."""
from unittest.mock import patch

from app.services.product_media_worker import process_due_media_jobs


def test_disabled_media_queue_does_not_access_database(monkeypatch):
    from app.services import product_media_worker
    monkeypatch.setattr(product_media_worker.settings, "PRODUCT_MEDIA_ENABLED", False)
    with patch.object(product_media_worker, "SessionLocal") as sessions:
        assert process_due_media_jobs(limit=10) == {"considered": 0}
        sessions.assert_not_called()


def test_production_without_storage_adapter_fails_closed(monkeypatch):
    import pytest
    from app.services import product_media_worker
    monkeypatch.setattr(product_media_worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(product_media_worker.settings, "APP_ENV", "production")
    monkeypatch.setattr(product_media_worker.settings, "MEDIA_STORAGE_BACKEND", "s3")
    with pytest.raises(RuntimeError, match="not configured"):
        process_due_media_jobs(limit=10)


def test_worker_claim_process_and_complete(monkeypatch):
    """One eligible claim results in a completed job and an approved counter."""
    import uuid
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import product_media_worker as worker

    monkeypatch.setattr(worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(worker.settings, "APP_ENV", "test")
    monkeypatch.setattr(worker.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_PROVIDER", "http")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_ENDPOINT_URL", "https://scanner.example.test/scan")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_AUTH_TOKEN", "test-token")
    asset_id, job_id = uuid.uuid4(), uuid.uuid4()
    job = SimpleNamespace(
        id=job_id, asset_id=asset_id, attempt_count=1, state="processing",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        next_attempt_at=None, failure_code=None,
    )
    asset = SimpleNamespace(
        id=asset_id, state="approved", public_object_key="public/ok.webp",
        derivative_sha256="a" * 64,
    )
    sessions = [MagicMock() for _ in range(3)]
    for session in sessions:
        session.__enter__.return_value = session
    sessions[2].get.side_effect = [job, asset]
    claims = iter([job, None])
    monkeypatch.setattr(worker, "SessionLocal", lambda: sessions.pop(0))
    monkeypatch.setattr(worker, "expire_exhausted_media_jobs", lambda db, limit: 0)
    monkeypatch.setattr(worker, "claim_due_media_job", lambda db: next(claims))
    monkeypatch.setattr(worker, "process_quarantined_asset", lambda *a, **kw: SimpleNamespace(state="approved", reason=None))
    monkeypatch.setattr(worker, "LocalObjectStorage", lambda *a: object())
    monkeypatch.setattr(worker, "HttpContentScanner", lambda *a: object())
    monkeypatch.setattr(worker, "complete_media_job", lambda job, **kw: setattr(job, "state", "completed"))
    result = worker.process_due_media_jobs(limit=1)
    assert result["considered"] == 1
    assert result["approved"] == 1
    assert job.state == "completed"


def test_publication_without_derivative_does_not_complete_job(monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import product_media_worker as worker

    monkeypatch.setattr(worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(worker.settings, "APP_ENV", "test")
    monkeypatch.setattr(worker.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_PROVIDER", "http")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_ENDPOINT_URL", "https://scanner.example.test/scan")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_AUTH_TOKEN", "test-token")
    asset_id, job_id = uuid.uuid4(), uuid.uuid4()
    job = SimpleNamespace(
        id=job_id, asset_id=asset_id, attempt_count=1, state="processing",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    asset = SimpleNamespace(id=asset_id, state="approved", public_object_key=None, derivative_sha256=None)
    sessions = [MagicMock() for _ in range(4)]
    for session in sessions:
        session.__enter__.return_value = session
    sessions[2].get.side_effect = [job, asset]
    sessions[3].get.return_value = job
    monkeypatch.setattr(worker, "SessionLocal", lambda: sessions.pop(0))
    monkeypatch.setattr(worker, "expire_exhausted_media_jobs", lambda db, limit: 0)
    monkeypatch.setattr(worker, "claim_due_media_job", lambda db: job)
    monkeypatch.setattr(worker, "process_quarantined_asset", lambda *a, **kw: SimpleNamespace(state="approved", reason=None))
    monkeypatch.setattr(worker, "LocalObjectStorage", lambda *a: object())
    monkeypatch.setattr(worker, "HttpContentScanner", lambda *a: object())
    outcomes = []
    monkeypatch.setattr(worker, "complete_media_job", lambda job, **kw: outcomes.append(kw["outcome"]))
    result = worker.process_due_media_jobs(limit=1)
    assert result["approved"] == 0 and result["retried"] == 1
    assert outcomes == ["retry"]


def test_worker_reconciles_already_approved_asset_without_republishing(monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import product_media_worker as worker

    monkeypatch.setattr(worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(worker.settings, "APP_ENV", "test")
    monkeypatch.setattr(worker.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_PROVIDER", "http")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_ENDPOINT_URL", "https://scanner.example.test/scan")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_AUTH_TOKEN", "test-token")
    asset_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(), asset_id=asset_id, attempt_count=2, state="processing",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    asset = SimpleNamespace(
        id=asset_id, state="approved", public_object_key="public/listings/ok.webp",
        derivative_sha256="a" * 64, retired_at=None,
    )
    sessions = [MagicMock() for _ in range(3)]
    for db in sessions:
        db.__enter__.return_value = db
    sessions[2].get.side_effect = [job, asset]
    monkeypatch.setattr(worker, "SessionLocal", lambda: sessions.pop(0))
    monkeypatch.setattr(worker, "expire_exhausted_media_jobs", lambda *a, **kw: 0)
    monkeypatch.setattr(worker, "claim_due_media_job", lambda db: job)
    monkeypatch.setattr(worker, "LocalObjectStorage", lambda *a: object())
    monkeypatch.setattr(worker, "HttpContentScanner", lambda *a: object())
    publication = MagicMock(side_effect=AssertionError("must not republish"))
    monkeypatch.setattr(worker, "process_quarantined_asset", publication)
    outcomes = []
    monkeypatch.setattr(worker, "complete_media_job", lambda job, **kw: outcomes.append(kw["outcome"]))
    counts = worker.process_due_media_jobs(limit=1)
    assert counts["approved"] == 1 and outcomes == ["approved"]
    publication.assert_not_called()


def test_expired_retry_lease_does_not_modify_job(monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import product_media_worker as worker

    monkeypatch.setattr(worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(worker.settings, "APP_ENV", "test")
    monkeypatch.setattr(worker.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_PROVIDER", "http")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_ENDPOINT_URL", "https://scanner.example.test/scan")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_AUTH_TOKEN", "test-token")
    asset_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(), asset_id=asset_id, attempt_count=1, state="processing",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    asset = SimpleNamespace(id=asset_id, state="quarantined", retired_at=None)
    sessions = [MagicMock() for _ in range(4)]
    for db in sessions:
        db.__enter__.return_value = db
    sessions[2].get.side_effect = [job, asset]
    sessions[3].get.return_value = SimpleNamespace(
        state="processing", attempt_count=1,
        lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    monkeypatch.setattr(worker, "SessionLocal", lambda: sessions.pop(0))
    monkeypatch.setattr(worker, "expire_exhausted_media_jobs", lambda *a, **kw: 0)
    monkeypatch.setattr(worker, "claim_due_media_job", lambda db: job)
    monkeypatch.setattr(worker, "LocalObjectStorage", lambda *a: object())
    monkeypatch.setattr(worker, "HttpContentScanner", lambda *a: object())
    monkeypatch.setattr(worker, "process_quarantined_asset", MagicMock(side_effect=RuntimeError("scanner failed")))
    completed = MagicMock()
    monkeypatch.setattr(worker, "complete_media_job", completed)
    counts = worker.process_due_media_jobs(limit=1)
    assert counts["considered"] == 1 and counts["retried"] == 0
    completed.assert_not_called()


def test_retired_approved_asset_is_not_reconciled_as_approved(monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import product_media_worker as worker

    monkeypatch.setattr(worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(worker.settings, "APP_ENV", "test")
    monkeypatch.setattr(worker.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_PROVIDER", "http")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_ENDPOINT_URL", "https://scanner.example.test/scan")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_AUTH_TOKEN", "test-token")
    asset_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(), asset_id=asset_id, attempt_count=1, state="processing",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    asset = SimpleNamespace(
        id=asset_id, state="approved", public_object_key="public/listings/a.webp",
        derivative_sha256="a" * 64, retired_at=datetime.now(timezone.utc),
    )
    sessions = [MagicMock() for _ in range(3)]
    for db in sessions:
        db.__enter__.return_value = db
    sessions[2].get.side_effect = [job, asset]
    monkeypatch.setattr(worker, "SessionLocal", lambda: sessions.pop(0))
    monkeypatch.setattr(worker, "expire_exhausted_media_jobs", lambda *a, **kw: 0)
    monkeypatch.setattr(worker, "claim_due_media_job", lambda db: job)
    monkeypatch.setattr(worker, "LocalObjectStorage", lambda *a: object())
    monkeypatch.setattr(worker, "HttpContentScanner", lambda *a: object())
    monkeypatch.setattr(worker, "process_quarantined_asset", MagicMock(side_effect=AssertionError("unexpected publication")))
    outcomes = []
    monkeypatch.setattr(worker, "complete_media_job", lambda job, **kw: outcomes.append(kw["outcome"]))
    counts = worker.process_due_media_jobs(limit=1)
    assert counts["approved"] == 0 and counts["rejected"] == 1
    assert outcomes == ["rejected"]


def test_public_derivative_is_deleted_when_database_commit_fails(monkeypatch):
    """A successful object-store write must not survive a failed SQL approval."""
    import uuid
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import product_media_worker as worker

    monkeypatch.setattr(worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(worker.settings, "APP_ENV", "test")
    monkeypatch.setattr(worker.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_PROVIDER", "http")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_ENDPOINT_URL", "https://scanner.example.test/scan")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_AUTH_TOKEN", "test-token")
    asset_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(), asset_id=asset_id, attempt_count=1, state="processing",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    asset = SimpleNamespace(
        id=asset_id, state="quarantined", public_object_key=None,
        derivative_sha256=None, retired_at=None,
    )
    sessions = [MagicMock() for _ in range(4)]
    for db in sessions:
        db.__enter__.return_value = db
    sessions[2].get.side_effect = [job, asset]
    sessions[2].commit.side_effect = RuntimeError("commit failed")
    sessions[3].get.return_value = job
    monkeypatch.setattr(worker, "SessionLocal", lambda: sessions.pop(0))
    monkeypatch.setattr(worker, "expire_exhausted_media_jobs", lambda *a, **kw: 0)
    monkeypatch.setattr(worker, "claim_due_media_job", lambda db: job)
    storage = MagicMock()
    monkeypatch.setattr(worker, "LocalObjectStorage", lambda *a: storage)
    monkeypatch.setattr(worker, "HttpContentScanner", lambda *a: object())

    def publish(*args, **kwargs):
        asset.public_object_key = "public/listings/derivative.webp"
        asset.derivative_sha256 = "a" * 64
        asset.state = "approved"
        return SimpleNamespace(state="approved", reason=None)

    monkeypatch.setattr(worker, "process_quarantined_asset", publish)
    outcomes = []
    monkeypatch.setattr(worker, "complete_media_job", lambda job, **kw: outcomes.append(kw["outcome"]))
    result = worker.process_due_media_jobs(limit=1)
    assert result["approved"] == 0 and result["retried"] == 1
    assert outcomes == ["approved", "retry"]
    storage.delete_public_derivative.assert_called_once_with("public/listings/derivative.webp")


def test_expired_lease_after_publication_deletes_derivative(monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import product_media_worker as worker

    monkeypatch.setattr(worker.settings, "PRODUCT_MEDIA_ENABLED", True)
    monkeypatch.setattr(worker.settings, "APP_ENV", "test")
    monkeypatch.setattr(worker.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_PROVIDER", "http")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_ENDPOINT_URL", "https://scanner.example.test/scan")
    monkeypatch.setattr(worker.settings, "MEDIA_SCAN_AUTH_TOKEN", "test-token")
    asset_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(), asset_id=asset_id, attempt_count=1, state="processing",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    asset = SimpleNamespace(
        id=asset_id, state="quarantined", public_object_key=None,
        derivative_sha256=None, retired_at=None,
    )
    sessions = [MagicMock() for _ in range(3)]
    for db in sessions:
        db.__enter__.return_value = db
    sessions[2].get.side_effect = [job, asset]
    monkeypatch.setattr(worker, "SessionLocal", lambda: sessions.pop(0))
    monkeypatch.setattr(worker, "expire_exhausted_media_jobs", lambda *a, **kw: 0)
    monkeypatch.setattr(worker, "claim_due_media_job", lambda db: job)
    storage = MagicMock()
    monkeypatch.setattr(worker, "LocalObjectStorage", lambda *a: storage)
    monkeypatch.setattr(worker, "HttpContentScanner", lambda *a: object())

    def publish(*args, **kwargs):
        asset.public_object_key = "public/listings/expired.webp"
        asset.derivative_sha256 = "b" * 64
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        return SimpleNamespace(state="approved", reason=None)

    monkeypatch.setattr(worker, "process_quarantined_asset", publish)
    complete = MagicMock()
    monkeypatch.setattr(worker, "complete_media_job", complete)
    result = worker.process_due_media_jobs(limit=1)
    assert result["approved"] == 0 and result["retried"] == 0
    storage.delete_public_derivative.assert_called_once_with("public/listings/expired.webp")
    complete.assert_not_called()
