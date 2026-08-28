from __future__ import annotations

import os

from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.commerce import Merchant, Store
from app.models.user import User, UserRole


def _normalise_phone(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if raw.strip().startswith("+") and digits:
        return f"+{digits}"
    raise RuntimeError(f"Unsupported pilot phone format: {raw!r}")


def main() -> None:
    if settings.APP_ENV != "production":
        raise RuntimeError("Pilot reset is production-only")

    raw = os.getenv("PILOT_RESET_PHONES", "").strip()
    if not raw:
        raise RuntimeError("Set PILOT_RESET_PHONES to a comma-separated list of test phone numbers")

    phones = list(dict.fromkeys(_normalise_phone(item) for item in raw.split(",") if item.strip()))
    if not phones:
        raise RuntimeError("No valid pilot test phone numbers supplied")

    db = SessionLocal()
    try:
        users = list(db.scalars(select(User).where(User.phone.in_(phones))))
        found = {user.phone: user for user in users}

        for phone in phones:
            user = found.get(phone)
            if user is None:
                print(f"SKIP {phone}: no GaonOne user exists yet")
                continue
            if user.role == UserRole.ADMIN:
                raise RuntimeError(f"REFUSING to reset admin user {phone}")

            merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
            if merchant is not None:
                store_count = db.scalar(select(func.count(Store.id)).where(Store.merchant_id == merchant.id)) or 0
                if store_count:
                    raise RuntimeError(
                        f"REFUSING to reset {phone}: merchant has {store_count} store(s). "
                        "Pilot commerce data must be cleared deliberately before resetting this account."
                    )
                db.delete(merchant)

            user.role = UserRole.CUSTOMER
            user.is_active = True
            user.is_verified = True
            user.full_name = None
            print(f"RESET {phone}: customer / active / verified; merchant application removed if present")

        db.commit()
        print("Pilot test-user reset complete. Existing admin and all store/order data were left untouched.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
