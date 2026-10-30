"""S3-compatible object storage with explicit AWS SigV4 path-style requests.

Supports S3 and Cloudflare R2 endpoints without adding an unpinned SDK.
No source objects are exposed through the public derivative bucket.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import httpx

from app.services.product_media_storage import StoredMediaObject


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


class S3ObjectStorage:
    def __init__(
        self, *, endpoint: str, region: str, quarantine_bucket: str,
        public_bucket: str, access_key_id: str, secret_access_key: str,
        timeout_seconds: float = 20.0,
    ):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
                or not region or not access_key_id or not secret_access_key):
            raise ValueError("S3 requires a credentialed HTTPS origin and region")
        for bucket in (quarantine_bucket, public_bucket):
            if (not bucket or bucket in {".", ".."} or "/" in bucket
                    or "\\" in bucket or "%" in bucket or "?" in bucket or "#" in bucket):
                raise ValueError("Invalid S3 bucket")
        if quarantine_bucket == public_bucket:
            raise ValueError("Quarantine and public buckets must be separate")
        self.endpoint = endpoint.rstrip("/")
        self.host = parsed.netloc
        self.region = region
        self.quarantine_bucket = quarantine_bucket
        self.public_bucket = public_bucket
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _path(bucket: str, key: str) -> str:
        from app.services.product_media_storage import _safe_path
        from pathlib import Path
        _safe_path(Path("/s3-object-key-validation"), key)
        return "/" + quote(bucket, safe="-_.~") + "/" + "/".join(
            quote(part, safe="-_.~") for part in key.split("/")
        )

    def _request(self, method: str, bucket: str, key: str, *,
                 content: bytes = b"", content_type: str | None = None) -> bytes:
        path = self._path(bucket, key)
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        day = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(content).hexdigest()
        headers = {
            "host": self.host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": timestamp,
        }
        if content_type is not None:
            headers["content-type"] = content_type
        names = sorted(headers)
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in names)
        signed_headers = ";".join(names)
        canonical = "\n".join([
            method, path, "", canonical_headers, signed_headers, payload_hash,
        ])
        scope = f"{day}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256", timestamp, scope,
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        ])
        signing_key = _sign(
            _sign(_sign(_sign(("AWS4" + self.secret_access_key).encode(), day),
                        self.region), "s3"), "aws4_request",
        )
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key_id}/{scope},"
            f"SignedHeaders={signed_headers},Signature={signature}"
        )
        response = httpx.request(
            method, self.endpoint + path, headers=headers, content=content,
            timeout=self.timeout_seconds, follow_redirects=False,
        )
        if method == "GET" and response.status_code == 404:
            raise FileNotFoundError("Quarantined media object is missing")
        response.raise_for_status()
        return response.content

    def put_quarantine(self, key: str, content: bytes, content_type: str) -> StoredMediaObject:
        if not key.startswith("quarantine/listings/") or content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Only listing image sources may enter quarantine")
        self._request("PUT", self.quarantine_bucket, key, content=content, content_type=content_type)
        return StoredMediaObject(key, content_type, len(content), hashlib.sha256(content).hexdigest())

    def read_quarantine(self, key: str) -> bytes:
        return self._request("GET", self.quarantine_bucket, key)

    def put_public_derivative(self, key: str, content: bytes, content_type: str) -> StoredMediaObject:
        if (content_type != "image/webp" or not key.startswith("public/listings/")
                or not key.endswith(".webp") or not content):
            raise ValueError("Only safe listing WebP derivatives may be published")
        self._request("PUT", self.public_bucket, key, content=content, content_type=content_type)
        return StoredMediaObject(key, content_type, len(content), hashlib.sha256(content).hexdigest())

    def delete_quarantine(self, key: str) -> None:
        self._request("DELETE", self.quarantine_bucket, key)

    def delete_public_derivative(self, key: str) -> None:
        self._request("DELETE", self.public_bucket, key)
