"""PostGIS-backed acceptance for additive draft territory storage.

These tests require the real CI PostgreSQL/PostGIS database and migration 0028.
No checkout feature flag is enabled and no existing service-area row is edited.
"""
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.session import SessionLocal
from app.models.delivery_territories import (
    DeliveryTerritory, DeliveryTerritoryVersion, OperatingRegion, TerritoryChangeAudit,
)
from app.services.spatial import serviceability_for_point
from tests import factories


def _draft(db, *, geometry_type="circle", radius_km=1):
    region = OperatingRegion(name="Synthetic test region", slug=f"test-{uuid4().hex}")
    db.add(region)
    db.flush()
    territory = DeliveryTerritory(
        operating_region_id=region.id,
        name="Synthetic draft",
        geometry_type=geometry_type,
        center_latitude=0 if geometry_type == "circle" else None,
        center_longitude=0 if geometry_type == "circle" else None,
        radius_km=radius_km if geometry_type == "circle" else None,
    )
    db.add(territory)
    db.flush()
    return territory


def test_draft_territory_never_changes_legacy_serviceability():
    with SessionLocal() as db:
        try:
            before = serviceability_for_point(db, 0.0, 0.0)
            territory = _draft(db)
            assert territory.status == "draft" or territory.status is None
            after = serviceability_for_point(db, 0.0, 0.0)
            assert after == before
        finally:
            db.rollback()


def test_polygon_exclusion_and_spatial_index_are_available():
    with SessionLocal() as db:
        try:
            territory = _draft(db, geometry_type="polygon")
            db.execute(
                text("""
                    UPDATE delivery_territories
                    SET geometry = ST_Multi(ST_GeomFromText(
                        'POLYGON((0 0,1 0,1 1,0 1,0 0))', 4326))
                    WHERE id = :id
                """),
                {"id": territory.id},
            )
            exclusion_id = uuid4()
            db.execute(
                text("""
                    INSERT INTO delivery_territory_exclusions
                        (id, territory_id, geometry, reason)
                    VALUES (
                        :id, :territory_id,
                        ST_Multi(ST_GeomFromText(
                            'POLYGON((0.4 0.4,0.6 0.4,0.6 0.6,0.4 0.6,0.4 0.4))',
                            4326)),
                        'Synthetic exclusion'
                    )
                """),
                {"id": exclusion_id, "territory_id": territory.id},
            )
            row = db.execute(
                text("""
                    SELECT
                        ST_Covers(t.geometry, ST_SetSRID(ST_MakePoint(0.5,0.5),4326))
                            AS inside,
                        ST_Covers(t.geometry, ST_SetSRID(ST_MakePoint(2,2),4326))
                            AS outside,
                        ST_Covers(e.geometry, ST_SetSRID(ST_MakePoint(0.5,0.5),4326))
                            AS excluded,
                        ST_SRID(t.geometry) AS srid
                    FROM delivery_territories t
                    JOIN delivery_territory_exclusions e ON e.territory_id=t.id
                    WHERE t.id=:id
                """),
                {"id": territory.id},
            ).one()
            assert (row.inside, row.outside, row.excluded, row.srid) == (
                True, False, True, 4326
            )
            indexes = db.scalars(
                text("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname=current_schema()
                      AND tablename IN (
                        'delivery_territories', 'delivery_territory_exclusions')
                      AND indexdef ILIKE '%USING gist%'
                """)
            ).all()
            assert "ix_delivery_territories_geometry_gist" in indexes
            assert "ix_delivery_territory_exclusions_geometry_gist" in indexes
        finally:
            db.rollback()


def test_invalid_radius_rejected_by_database():
    with SessionLocal() as db:
        try:
            with pytest.raises(IntegrityError):
                _draft(db, radius_km=-1)
        finally:
            db.rollback()


def test_invalid_multipolygon_rejected_by_database():
    with SessionLocal() as db:
        try:
            territory = _draft(db, geometry_type="polygon")
            with pytest.raises(IntegrityError):
                db.execute(
                    text("""
                        UPDATE delivery_territories
                        SET geometry=ST_Multi(ST_GeomFromText(
                            'POLYGON((0 0,1 1,1 0,0 1,0 0))',4326))
                        WHERE id=:id
                    """),
                    {"id": territory.id},
                )
        finally:
            db.rollback()


def test_published_version_history_cannot_be_rewritten():
    with SessionLocal() as db:
        try:
            territory = _draft(db)
            actor = factories.make_user(db)
            version = DeliveryTerritoryVersion(
                territory_id=territory.id, version=1,
                snapshot={"geometry_type": "circle", "radius_km": 1},
                changed_by=actor.id, change_reason="Synthetic version",
            )
            db.add(version)
            db.flush()
            with pytest.raises(DBAPIError, match="append-only"):
                db.execute(
                    text("UPDATE delivery_territory_versions SET change_reason='tampered' WHERE id=:id"),
                    {"id": version.id},
                )
        finally:
            db.rollback()


def test_territory_audit_cannot_be_deleted():
    with SessionLocal() as db:
        try:
            territory = _draft(db)
            actor = factories.make_user(db)
            event = TerritoryChangeAudit(
                territory_id=territory.id, actor_id=actor.id,
                action="draft_created", change_reason="Synthetic audit",
            )
            db.add(event)
            db.flush()
            with pytest.raises(DBAPIError, match="append-only"):
                db.execute(
                    text("DELETE FROM territory_change_audit WHERE id=:id"),
                    {"id": event.id},
                )
        finally:
            db.rollback()
