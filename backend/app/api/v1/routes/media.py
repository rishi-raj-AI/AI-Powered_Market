from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import require_roles
from app.core.config import settings
from app.models.user import User, UserRole

router = APIRouter(prefix="/media", tags=["Media"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.post("/images", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    _: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
) -> dict[str, str | int]:
    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG and WebP images are supported")

    content = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image must be <= {settings.MAX_UPLOAD_MB} MB")

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
