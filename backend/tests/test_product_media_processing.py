"""Scanner and derivative regression tests; no production credentials needed."""
from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.services.product_media_processing import (
    MediaRejected, MediaScanUnavailable, inspect_and_render,
)
from app.services.product_media_storage import (
    FakeObjectStorage, HttpContentScanner, ScanResult,
)


class ByteScanner:
    def __init__(self, verdict="clean"):
        self.verdict = verdict
        self.seen = []

    def scan_bytes(self, item, content):
        self.seen.append(content)
        return ScanResult(self.verdict)


def source_image(width=80, height=60):
    output = BytesIO()
    Image.new("RGB", (width, height), (120, 30, 60)).save(output, format="PNG")
    return output.getvalue()


def render(content, scanner=None, **limits):
    store = FakeObjectStorage()
    obj = store.put_quarantine("private/original", content, "image/png")
    return inspect_and_render(
        source=content, original=obj, scanner=scanner or ByteScanner(),
        max_bytes=limits.get("max_bytes", 1000000),
        max_width=limits.get("max_width", 4096),
        max_height=limits.get("max_height", 4096),
        max_pixels=limits.get("max_pixels", 16000000),
    )


def test_clean_image_is_reencoded_without_source_format_or_metadata():
    scanner = ByteScanner()
    result = render(source_image(), scanner)
    assert scanner.seen and scanner.seen[0].startswith(b"\\x89PNG")
    assert result.content_type == "image/webp"
    assert (result.width, result.height) == (80, 60)
    with Image.open(BytesIO(result.content)) as image:
        assert image.format == "WEBP"
        assert not image.getexif()


@pytest.mark.parametrize("verdict", ["infected", "rejected", "unknown"])
def test_non_clean_verdict_never_publishes(verdict):
    with pytest.raises(MediaRejected):
        render(source_image(), ByteScanner(verdict))


def test_scanner_without_byte_inspection_fails_closed():
    from app.services.product_media_storage import FailClosedScanner
    with pytest.raises(MediaScanUnavailable):
        render(source_image(), FailClosedScanner())


def test_dimension_and_size_limits_fail_before_publication():
    with pytest.raises(MediaRejected):
        render(source_image(120, 60), max_width=100)
    with pytest.raises(MediaRejected):
        render(source_image(), max_bytes=12)


def test_corrupt_image_fails_after_scanning():
    with pytest.raises(MediaRejected):
        render(b"not-an-image")


def test_http_scanner_rejects_insecure_configuration():
    with pytest.raises(ValueError):
        HttpContentScanner("http://scanner.invalid/scan", "token")
    with pytest.raises(ValueError):
        HttpContentScanner("https://scanner.invalid/scan", "")


def test_http_scanner_fails_closed_on_malformed_reply(monkeypatch):
    import httpx
    scanner = HttpContentScanner("https://scanner.invalid/scan", "token")
    def mock_post(*args, **kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["content"] == b"source"
        return httpx.Response(200, json={"verdict": "not-sure"}, request=httpx.Request("POST", args[0]))
    monkeypatch.setattr(httpx, "post", mock_post)
    item = FakeObjectStorage().put_quarantine("private/a", b"source", "image/png")
    assert scanner.scan_bytes(item, b"source").verdict == "unavailable"


def test_http_scanner_sends_source_bytes_and_accepts_explicit_clean(monkeypatch):
    import httpx
    scanner = HttpContentScanner("https://scanner.invalid/scan", "test-token")
    source = source_image()
    item = FakeObjectStorage().put_quarantine("private/a", source, "image/png")

    def mock_post(*args, **kwargs):
        assert kwargs["content"] == source
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"
        assert kwargs["headers"]["X-Media-Sha256"] == item.sha256
        assert kwargs["follow_redirects"] is False
        return httpx.Response(200, json={"verdict": "clean"}, request=httpx.Request("POST", args[0]))

    monkeypatch.setattr(httpx, "post", mock_post)
    assert scanner.scan_bytes(item, source).verdict == "clean"


def test_http_scanner_network_errors_are_unavailable(monkeypatch):
    import httpx
    scanner = HttpContentScanner("https://scanner.invalid/scan", "test-token")
    item = FakeObjectStorage().put_quarantine("private/a", b"source", "image/png")

    def mock_post(*args, **kwargs):
        raise httpx.ConnectError("scanner offline")

    monkeypatch.setattr(httpx, "post", mock_post)
    assert scanner.scan_bytes(item, b"source").verdict == "unavailable"
