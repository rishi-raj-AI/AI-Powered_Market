from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.commerce import Merchant, Store, StoreProduct
from app.models.product_media import ProductMediaAsset
from app.services.product_media import approved_listing_media

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.deps import ensure_capability, require_roles
from app.core.capabilities import Capability
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
    if user.role == UserRole.ADMIN:
        ensure_capability(user, Capability.MEDIA_MODERATE)
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


@router.get("/store-products/{listing_id}/images")
def list_merchant_listing_images(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
) -> list[dict]:
    """Private listing-image status; never expose quarantine object keys or raw uploads."""
    listing = db.get(StoreProduct, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    store = db.get(Store, listing.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if user.role == UserRole.ADMIN:
        ensure_capability(user, Capability.MEDIA_MODERATE)
    elif merchant is None or merchant.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this listing")
    assets = db.scalars(
        select(ProductMediaAsset)
        .where(ProductMediaAsset.store_product_id == listing_id)
        .order_by(ProductMediaAsset.position, ProductMediaAsset.created_at)
        .limit(50)
    ).all()
    return [
        {
            "id": str(asset.id),
            "state": asset.state,
            "alt_text": asset.alt_text,
            "position": asset.position,
            "is_primary": asset.is_primary,
            "created_at": asset.created_at.isoformat(),
        }
        for asset in assets
    ]


@router.get("/store-products/{listing_id}/approved-images")
def public_approved_listing_images(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return only approved derivative descriptors for a publicly available listing."""
    listing = db.get(StoreProduct, listing_id)
    if listing is None or not listing.is_available or listing.stock_quantity <= 0:
        raise HTTPException(status_code=404, detail="Listing not available")
    store = db.get(Store, listing.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status.value != "approved":
        raise HTTPException(status_code=404, detail="Listing not available")
    return approved_listing_media(db, [listing_id]).get(listing_id, [])


@router.get("/stores/{store_id}/approved-images")
def public_store_approved_images(
    store_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]]:
    """Batch public-approved images for a storefront, without per-product requests."""
    store = db.get(Store, store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if store is None or not store.is_active or merchant is None or merchant.status.value != "approved":
        raise HTTPException(status_code=404, detail="Store not found")
    listing_ids = list(db.scalars(
        select(StoreProduct.id).where(
            StoreProduct.store_id == store_id,
            StoreProduct.is_available.is_(True),
            StoreProduct.stock_quantity > 0,
        ).order_by(StoreProduct.updated_at.desc()).limit(limit)
    ).all())
    return {str(key): value for key, value in approved_listing_media(db, listing_ids).items()}
