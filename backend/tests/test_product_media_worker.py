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
