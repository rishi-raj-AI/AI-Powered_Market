"""Idempotently provision Washi as an additional production service area.

Run explicitly inside the backend container after deploying the code:
    python -m app.scripts.provision_washi

This script never changes or deactivates existing villages/service areas. If an
existing Washi record conflicts with the intended configuration, it aborts.
The coordinates are an approximate Washi town-centre point; verify them before
using this service area for real customer serviceability decisions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.geography import ServiceArea, Village
from app.models.governance import AdministrativeAuditEvent
from app.models.user import User, UserRole


VILLAGE_NAME = "Washi"
TALUKA = "Washi"
DISTRICT = "Dharashiv"
STATE = "Maharashtra"
PINCODE = "413503"
# Approximate town-centre coordinates; confirm on the ground before relying on
# the radius for live customer serviceability.
LATITUDE = 18.5422
LONGITUDE = 75.7789
SERVICE_AREA_NAME = "Washi Pilot Cluster"
RADIUS_KM = 12.0


def main() -> None:
    if settings.APP_ENV != "production":
        raise RuntimeError("This provisioning script is intended for production only.")

    created_village = False
    created_area = False
    village_id: uuid.UUID
    area_id: uuid.UUID
    request_id = f"script:washi-provisioning:{uuid.uuid4()}"

    # One transaction ensures that village, service area, and audit events
    # commit together or not at all.
    with SessionLocal.begin() as db:
        admin = db.scalar(
            select(User).where(
                User.role == UserRole.ADMIN,
                User.is_super_admin.is_(True),
                User.is_active.is_(True),
                User.is_verified.is_(True),
            )
        )
        if admin is None:
            raise RuntimeError(
                "No active, verified super-admin exists; refusing to provision."
            )

        village = db.scalar(
            select(Village).where(
                Village.name == VILLAGE_NAME,
                Village.district == DISTRICT,
                Village.state == STATE,
            )
        )
        if village is None:
            village = Village(
                name=VILLAGE_NAME,
                taluka=TALUKA,
                district=DISTRICT,
                state=STATE,
                pincode=PINCODE,
                latitude=LATITUDE,
                longitude=LONGITUDE,
                is_active=True,
            )
            db.add(village)
            db.flush()
            created_village = True
            db.add(
                AdministrativeAuditEvent(
                    actor_user_id=admin.id,
                    action="geography.locality_created",
                    capability="geography.manage",
                    resource_type="village",
                    resource_id=str(village.id),
                    previous_state={},
                    resulting_state={
                        "name": VILLAGE_NAME,
                        "taluka": TALUKA,
                        "district": DISTRICT,
                        "state": STATE,
                        "pincode": PINCODE,
                        "latitude": LATITUDE,
                        "longitude": LONGITUDE,
                    },
                    reason="one_time_washi_service_area_provisioning",
                    request_id=request_id,
                )
            )
        else:
            expected = {
                "taluka": TALUKA,
                "pincode": PINCODE,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "is_active": True,
            }
            mismatches = {
                key: (getattr(village, key), value)
                for key, value in expected.items()
                if getattr(village, key) != value
            }
            if mismatches:
                raise RuntimeError(
                    f"Existing Washi village conflicts with expected values: {mismatches}. "
                    "No records were changed."
                )

        village_id = village.id

        # Do not accidentally attach a similarly named area to another village.
        named_areas = db.scalars(
            select(ServiceArea).where(ServiceArea.name == SERVICE_AREA_NAME)
        ).all()
        conflicting_area = next(
            (item for item in named_areas if item.hub_village_id != village_id),
            None,
        )
        if conflicting_area is not None:
            raise RuntimeError(
                f"Service area '{SERVICE_AREA_NAME}' already belongs to another village. "
                "No records were changed."
            )

        area = next(
            (item for item in named_areas if item.hub_village_id == village_id),
            None,
        )
        if area is None:
            area = ServiceArea(
                name=SERVICE_AREA_NAME,
                hub_village_id=village_id,
                radius_km=RADIUS_KM,
                is_active=True,
            )
            db.add(area)
            db.flush()
            created_area = True
            db.add(
                AdministrativeAuditEvent(
                    actor_user_id=admin.id,
                    action="geography.service_area_created",
                    capability="geography.manage",
                    resource_type="service_area",
                    resource_id=str(area.id),
                    previous_state={},
                    resulting_state={
                        "name": SERVICE_AREA_NAME,
                        "hub_village_id": str(village_id),
                        "radius_km": RADIUS_KM,
                        "is_active": True,
                    },
                    reason="one_time_washi_service_area_provisioning",
                    request_id=request_id,
                )
            )
        elif area.radius_km != RADIUS_KM or not area.is_active:
            raise RuntimeError(
                "An existing Washi service area has a different radius or is inactive. "
                "No records were changed; review it manually rather than overwriting it."
            )

        area_id = area.id

    print("Washi provisioning completed successfully.")
    print(f"Village ID: {village_id} ({'created' if created_village else 'already existed'})")
    print(f"Service area ID: {area_id} ({'created' if created_area else 'already existed'})")
    print(f"Service area: {SERVICE_AREA_NAME}; radius: {RADIUS_KM:g} km")
    print("Existing service areas were not modified.")
    print(
        "NOTE: village coordinates are approximate; verify the hub point before "
        "relying on live serviceability results."
    )


if __name__ == "__main__":
    main()
