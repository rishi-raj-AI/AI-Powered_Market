"""Fail-closed product-photo inspection and safe derivative generation.

No original bytes are published. A mandatory scanner must explicitly return
"clean" before image decoding or derivative creation is attempted.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.product_media_storage import ContentScanner, StoredMediaObject

SUPPORTED = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class MediaRejected(ValueError):
    """A permanent unsafe or unsupported media input."""


class MediaScanUnavailable(RuntimeError):
    """Transient scanner failure; the caller must retry, never approve."""


@dataclass(frozen=True)
class SafeDerivative:
    content: bytes
    content_type: str
    width: int
    height: int


def inspect_and_render(
    *,
    source: bytes,
    original: StoredMediaObject,
    scanner: ContentScanner,
    max_bytes: int,
    max_width: int,
    max_height: int,
    max_pixels: int,
    output_edge: int = 1280,
) -> SafeDerivative:
    """Scan, validate, orient and re-encode into metadata-free WebP.

    The scanner must inspect the *actual source bytes*, not merely the object
    metadata. Legacy metadata-only scanner adapters fail closed.
    """
    if not source or len(source) > max_bytes or original.byte_size != len(source):
        raise MediaRejected("invalid_size")
    import hashlib
    if hashlib.sha256(source).hexdigest() != original.sha256:
        raise MediaRejected("source_hash_mismatch")
    scan_bytes = getattr(scanner, "scan_bytes", None)
    if not callable(scan_bytes):
        raise MediaScanUnavailable("scanner_cannot_inspect_bytes")
    try:
        verdict = scan_bytes(original, source)
    except Exception as exc:
        raise MediaScanUnavailable("scanner_unavailable") from exc
    if verdict.verdict == "unavailable":
        raise MediaScanUnavailable("scanner_unavailable")
    if verdict.verdict != "clean":
        raise MediaRejected("scan_rejected")
    try:
        with Image.open(BytesIO(source)) as probe:
            if probe.format not in SUPPORTED or SUPPORTED[probe.format] != original.content_type:
                raise MediaRejected("unsupported_or_mismatched_format")
            width, height = probe.size
            if (width <= 0 or height <= 0 or width > max_width
                    or height > max_height or width * height > max_pixels):
                raise MediaRejected("image_dimensions_exceeded")
            probe.verify()
        with Image.open(BytesIO(source)) as decoded:
            image = ImageOps.exif_transpose(decoded)
            image.load()
            image = image.convert("RGB")
            image.thumbnail((output_edge, output_edge), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="WEBP", quality=82, method=4)
            return SafeDerivative(output.getvalue(), "image/webp", image.width, image.height)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        if isinstance(exc, MediaRejected):
            raise
        raise MediaRejected("image_decode_failed") from exc
