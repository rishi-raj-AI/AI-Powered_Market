from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import require_roles
from app.core.config import settings
from app.models.user import User, UserRole
from app.services.rate_limit import RateLimitExceeded, RateLimitUnavailable, rate_limiter

router = APIRouter(prefix="/media", tags=["Media"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

#: The declared Content-Type is attacker-controlled, so the bytes have to agree
#: with it. These are the file signatures for the formats we accept.
MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}

UPLOAD_RATE_LIMIT = 30
UPLOAD_RATE_WINDOW_SECONDS = 3600


def _looks_like(content: bytes, content_type: str) -> bool:
    signatures = MAGIC_SIGNATURES.get(content_type, ())
    if not any(content.startswith(signature) for signature in signatures):
        return False
    if content_type == "image/webp":
        # RIFF is a container; only the WEBP form is an image.
        return len(content) >= 12 and content[8:12] == b"WEBP"
    return True


@router.post("/images", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
) -> dict[str, str | int]:
    # Uploads write to a shared volume, so an unbounded endpoint is a disk
    # exhaustion vector as much as an abuse one.
    try:
        rate_limiter.enforce(
            "media-upload",
            str(user.id),
            limit=UPLOAD_RATE_LIMIT,
            window_seconds=UPLOAD_RATE_WINDOW_SECONDS,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except RateLimitUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG and WebP images are supported")

    content = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image must be <= {settings.MAX_UPLOAD_MB} MB")
    if not _looks_like(content, content_type):
        raise HTTPException(
            status_code=415,
            detail="File contents do not match the declared image type",
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    destination = upload_dir / filename
    destination.write_bytes(content)

    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return {
        "url": f"{base}/media/{filename}",
        "filename": filename,
        "size": len(content),
    }
