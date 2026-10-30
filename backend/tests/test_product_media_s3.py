"""No-network S3/R2 adapter contract and signing tests."""
from __future__ import annotations

import hashlib

import httpx
import pytest

from app.services.product_media_s3 import S3ObjectStorage


@pytest.fixture
def adapter():
    return S3ObjectStorage(
        endpoint="https://objects.example.test", region="auto",
        quarantine_bucket="media-private", public_bucket="media-public",
        access_key_id="test-id", secret_access_key="test-secret",
    )


def test_s3_requires_https_distinct_buckets_and_credentials():
    options = dict(
        endpoint="https://objects.example.test", region="auto",
        quarantine_bucket="private", public_bucket="public",
        access_key_id="id", secret_access_key="secret",
    )
    for changes in (
        {"endpoint": "http://objects.example.test"},
        {"endpoint": "https://objects.example.test/evil"},
        {"endpoint": "https://user:pass@objects.example.test"},
        {"public_bucket": "private"},
        {"quarantine_bucket": "../escape"},
        {"secret_access_key": ""},
    ):
        with pytest.raises(ValueError):
            S3ObjectStorage(**(options | changes))


def test_s3_put_get_delete_use_separate_signed_buckets(monkeypatch, adapter):
    calls = []
    payload = b"private-image-bytes"

    def fake_request(method, url, *, headers, content, timeout, follow_redirects):
        assert follow_redirects is False
        assert timeout == 20.0
        assert headers["host"] == "objects.example.test"
        assert headers["x-amz-content-sha256"] == hashlib.sha256(content).hexdigest()
        assert headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=test-id/")
        assert "SignedHeaders=" in headers["authorization"]
        calls.append((method, url))
        return httpx.Response(
            200, content=(b"RIFFwebp" if "media-public" in url else payload) if method == "GET" else b"",
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx, "request", fake_request)
    source = adapter.put_quarantine("quarantine/listings/1/source", payload, "image/png")
    assert source.sha256 == hashlib.sha256(payload).hexdigest()
    assert adapter.read_quarantine(source.key) == payload
    public = adapter.put_public_derivative("public/listings/1/derivative.webp", b"RIFFwebp", "image/webp")
    assert public.content_type == "image/webp"
    adapter.delete_quarantine(source.key)
    adapter.delete_public_derivative(public.key)
    assert calls == [
        ("PUT", "https://objects.example.test/media-private/quarantine/listings/1/source"),
        ("GET", "https://objects.example.test/media-private/quarantine/listings/1/source"),
        ("PUT", "https://objects.example.test/media-public/public/listings/1/derivative.webp"),
        ("GET", "https://objects.example.test/media-public/public/listings/1/derivative.webp"),
        ("DELETE", "https://objects.example.test/media-private/quarantine/listings/1/source"),
        ("DELETE", "https://objects.example.test/media-public/public/listings/1/derivative.webp"),
    ]


def test_s3_public_bucket_never_accepts_untrusted_keys(adapter, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("invalid key must not make network request")

    monkeypatch.setattr(httpx, "request", unexpected)
    for key in ("../escape", "/absolute", "public//listings/a.webp", "quarantine/source.webp",
                "public/listings/source.png", "public/listings/%2e%2e/a.webp"):
        with pytest.raises(ValueError):
            adapter.put_public_derivative(key, b"source", "image/webp")


def test_s3_missing_quarantine_object_is_file_not_found(adapter, monkeypatch):
    def missing(method, url, **kwargs):
        return httpx.Response(404, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", missing)
    with pytest.raises(FileNotFoundError):
        adapter.read_quarantine("quarantine/listings/missing")


def test_s3_private_upload_rejects_nonlisting_sources(adapter, monkeypatch):
    monkeypatch.setattr(httpx, "request", lambda *a, **kw: pytest.fail("unexpected network request"))
    for key, mime in (
        ("public/listings/a.webp", "image/webp"),
        ("quarantine/listings/a", "application/octet-stream"),
        ("quarantine/listings/../escape", "image/png"),
    ):
        with pytest.raises(ValueError):
            adapter.put_quarantine(key, b"image", mime)


def test_s3_http_failure_never_returns_successful_storage_metadata(adapter, monkeypatch):
    def denied(method, url, **kwargs):
        return httpx.Response(403, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", denied)
    with pytest.raises(httpx.HTTPStatusError):
        adapter.put_quarantine("quarantine/listings/1/source", b"image", "image/png")
    with pytest.raises(httpx.HTTPStatusError):
        adapter.put_public_derivative("public/listings/1/a.webp", b"webp", "image/webp")


def test_s3_corrupt_public_readback_is_deleted_and_never_approved(adapter, monkeypatch):
    calls = []

    def corrupt(method, url, **kwargs):
        calls.append(method)
        return httpx.Response(
            200, content=b"corrupted" if method == "GET" else b"",
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx, "request", corrupt)
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        adapter.put_public_derivative("public/listings/1/a.webp", b"RIFFwebp", "image/webp")
    assert calls == ["PUT", "GET", "DELETE"]


def test_s3_public_readback_network_error_attempts_cleanup(adapter, monkeypatch):
    calls = []

    def unavailable(method, url, **kwargs):
        calls.append(method)
        if method == "GET":
            raise httpx.ConnectError("unavailable")
        return httpx.Response(200, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", unavailable)
    with pytest.raises(httpx.ConnectError):
        adapter.put_public_derivative("public/listings/1/a.webp", b"RIFFwebp", "image/webp")
    assert calls == ["PUT", "GET", "DELETE"]
