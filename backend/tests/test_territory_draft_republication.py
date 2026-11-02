"""Real PostGIS tests for immutable *draft-only* territory revisions.

All rows are synthetic. No legacy service areas or checkout paths are changed.
"""
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.models.delivery_territories import (
    DeliveryTerritory, DeliveryTerritoryVersion, OperatingRegion,
    TerritoryChangeAudit, StoreDeliveryTerritory,
)
from app.services.territory_preview import match_active_store_territory
from app.services.territory_publication import (
    PublicationRejected, publish_initial_draft, publish_revised_draft,
)
from tests import factories


def _staged(db):
    region = OperatingRegion(
        name="Synthetic draft revision region",
        slug=f"draft-revision-{uuid4().hex}",
        status="active",
    )
    db.add(region)
    db.flush()
    territory = DeliveryTerritory(
        operating_region_id=region.id,
        name="Synthetic draft territory",
        geometry_type="circle",
        center_latitude=0,
        center_longitude=0,
        radius_km=1,
        status="draft",
    )
    actor = factories.make_user(db)
    db.add(territory)
    db.flush()
    publish_initial_draft(
        db, territory_id=territory.id, actor_id=actor.id,
        expected_published_version=None,
        reason="Initial approved synthetic snapshot",
    )
    return territory, actor


def _revise(db, territory, actor, *, expected=1):
    return publish_revised_draft(
        db, territory_id=territory.id, actor_id=actor.id,
        expected_published_version=expected,
        reason="Reviewed synthetic draft geometry revision",
    )


def test_changed_circle_creates_compensating_version_and_audit_without_activation():
    with factories.session() as db:
        territory, actor = _staged(db)
        store = factories.make_store(db)
        db.add(StoreDeliveryTerritory(
            store_id=store.id, territory_id=territory.id,
            status="active", delivery_enabled=True,
        ))
        territory.radius_km = 2
        db.flush()
        result = _revise(db, territory, actor)
        assert result.published_version == 2
        assert result.status == "draft"
        assert territory.published_version == 2
        versions = db.scalars(select(DeliveryTerritoryVersion).where(
            DeliveryTerritoryVersion.territory_id == territory.id,
        ).order_by(DeliveryTerritoryVersion.version)).all()
        assert [v.version for v in versions] == [1, 2]
        assert versions[0].snapshot["radius_km"] == "1.000"
        assert versions[1].snapshot["radius_km"] == "2.000"
        assert versions[0].published_at is not None
        audits = db.scalars(select(TerritoryChangeAudit).where(
            TerritoryChangeAudit.territory_id == territory.id,
        ).order_by(TerritoryChangeAudit.created_at, TerritoryChangeAudit.id)).all()
        revised = next(a for a in audits if a.new_version == 2)
        assert revised.action == "published"
        assert revised.previous_version == 1
        assert revised.details["activation"] is False
        assert revised.details["revision"] is True
        assert match_active_store_territory(db, store.id, 0, 0) is None
        db.rollback()


def test_exclusion_change_is_versioned_and_does_not_activate():
    with factories.session() as db:
        territory, actor = _staged(db)
        db.execute(text("""
            INSERT INTO delivery_territory_exclusions (id, territory_id, geometry)
            VALUES (:id, :territory_id,
                ST_Multi(ST_GeomFromText(
                    'POLYGON((0 0,0.01 0,0.01 0.01,0 0.01,0 0))',4326)))
        """), {"id": uuid4(), "territory_id": territory.id})
        _revise(db, territory, actor)
        snapshot = db.scalar(select(DeliveryTerritoryVersion.snapshot).where(
            DeliveryTerritoryVersion.territory_id == territory.id,
            DeliveryTerritoryVersion.version == 2,
        ))
        assert len(snapshot["exclusion_hex"]) == 1
        assert territory.status == "draft"
        db.rollback()


def test_unchanged_geometry_cannot_create_duplicate_publication():
    with factories.session() as db:
        territory, actor = _staged(db)
        with pytest.raises(PublicationRejected) as err:
            _revise(db, territory, actor)
        assert err.value.code == "unchanged_geometry"
        assert db.scalar(select(DeliveryTerritoryVersion.version).where(
            DeliveryTerritoryVersion.territory_id == territory.id,
            DeliveryTerritoryVersion.version == 2,
        )) is None
        db.rollback()


def test_stale_expected_version_and_inconsistent_history_fail_closed():
    with factories.session() as db:
        territory, actor = _staged(db)
        territory.radius_km = 2
        db.flush()
        with pytest.raises(PublicationRejected) as err:
            _revise(db, territory, actor, expected=2)
        assert err.value.code == "version_conflict"
        territory.published_version = 5
        db.flush()
        with pytest.raises(PublicationRejected) as err:
            _revise(db, territory, actor, expected=5)
        assert err.value.code == "version_conflict"
        db.rollback()


def test_invalid_geometry_and_active_territory_are_rejected():
    with factories.session() as db:
        territory, actor = _staged(db)
        territory.radius_km = None
        db.flush()
        with pytest.raises(PublicationRejected) as err:
            _revise(db, territory, actor)
        assert err.value.code == "invalid_geometry"
        territory.radius_km = 2
        territory.status = "active"
        db.flush()
        with pytest.raises(PublicationRejected) as err:
            _revise(db, territory, actor)
        assert err.value.code == "not_draft"
        db.rollback()


def test_missing_territory_and_invalid_reason_rejected():
    with factories.session() as db:
        actor = factories.make_user(db)
        with pytest.raises(PublicationRejected) as err:
            publish_revised_draft(
                db, territory_id=uuid4(), actor_id=actor.id,
                expected_published_version=1,
                reason="Reviewed synthetic draft revision",
            )
        assert err.value.code == "not_found"
        territory, actor = _staged(db)
        with pytest.raises(PublicationRejected) as err:
            publish_revised_draft(
                db, territory_id=territory.id, actor_id=actor.id,
                expected_published_version=1, reason="too short",
            )
        assert err.value.code == "invalid_reason"
        db.rollback()
