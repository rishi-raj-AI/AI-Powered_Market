"""Provider-neutral product-media boundaries.

Only explicit test/development adapters exist in B1.  Production S3/R2 and
scan implementations are intentionally deferred until their credentials and
operational dependencies are provisioned; settings reject enabling them early.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol


@dataclass(frozen=True)
class StoredMediaObject:
    key: str
    content_type: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class ScanResult:
    verdict: str
    reason_code: str | None = None


class ObjectStorage(Protocol):
    def put_quarantine(self, key: str, content: bytes, content_type: str) -> StoredMediaObject: ...

    def read_quarantine(self, key: str) -> bytes: ...

    def put_public_derivative(self, key: str, content: bytes, content_type: str) -> StoredMediaObject: ...

    def delete_quarantine(self, key: str) -> None: ...

    def delete_public_derivative(self, key: str) -> None: ...


class ContentScanner(Protocol):
    def scan(self, item: StoredMediaObject) -> ScanResult: ...


def _safe_path(root: Path, key: str) -> Path:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts:
        raise ValueError("Object keys must be relative opaque paths")
    destination = root.joinpath(*path.parts)
    resolved_root, resolved_destination = root.resolve(), destination.resolve()
    if resolved_root != resolved_destination and resolved_root not in resolved_destination.parents:
        raise ValueError("Object key escapes its configured storage root")
    return destination


class LocalObjectStorage:
    """Development/test adapter with separate private and public roots."""

    def __init__(self, quarantine_root: Path, public_root: Path):
        self.quarantine_root = quarantine_root
        self.public_root = public_root

    @staticmethod
    def _stored(key: str, content: bytes, content_type: str) -> StoredMediaObject:
        return StoredMediaObject(
            key=key,
            content_type=content_type,
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    @staticmethod
    def _put(root: Path, key: str, content: bytes, content_type: str) -> StoredMediaObject:
        destination = _safe_path(root, key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return LocalObjectStorage._stored(key, content, content_type)

    def put_quarantine(self, key: str, content: bytes, content_type: str) -> StoredMediaObject:
        return self._put(self.quarantine_root, key, content, content_type)

    def read_quarantine(self, key: str) -> bytes:
        return _safe_path(self.quarantine_root, key).read_bytes()

    def put_public_derivative(self, key: str, content: bytes, content_type: str) -> StoredMediaObject:
        return self._put(self.public_root, key, content, content_type)

    def delete_quarantine(self, key: str) -> None:
        _safe_path(self.quarantine_root, key).unlink(missing_ok=True)

    def delete_public_derivative(self, key: str) -> None:
        _safe_path(self.public_root, key).unlink(missing_ok=True)


class FakeObjectStorage:
    """In-memory adapter for deterministic unit tests."""

    def __init__(self):
        self.quarantine: dict[str, bytes] = {}
        self.public: dict[str, bytes] = {}

    @staticmethod
    def _stored(key: str, content: bytes, content_type: str) -> StoredMediaObject:
        return StoredMediaObject(key, content_type, len(content), hashlib.sha256(content).hexdigest())

    def put_quarantine(self, key: str, content: bytes, content_type: str) -> StoredMediaObject:
        self.quarantine[key] = content
        return self._stored(key, content, content_type)

    def read_quarantine(self, key: str) -> bytes:
        return self.quarantine[key]

    def put_public_derivative(self, key: str, content: bytes, content_type: str) -> StoredMediaObject:
        self.public[key] = content
        return self._stored(key, content, content_type)

    def delete_quarantine(self, key: str) -> None:
        self.quarantine.pop(key, None)

    def delete_public_derivative(self, key: str) -> None:
        self.public.pop(key, None)


class FakeContentScanner:
    def __init__(self, result: ScanResult):
        self.result = result
        self.seen: list[StoredMediaObject] = []

    def scan(self, item: StoredMediaObject) -> ScanResult:
        self.seen.append(item)
        return self.result


class FailClosedScanner:
    """The only safe non-production default: unavailable is never approval."""

    def scan(self, item: StoredMediaObject) -> ScanResult:
        del item
        return ScanResult(verdict="unavailable", reason_code="scanner_not_configured")
