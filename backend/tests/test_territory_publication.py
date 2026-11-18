"""Real PostGIS transaction tests for disabled-by-default draft publication.

All territory/version/audit rows are synthetic and rolled back. No live
service-area or checkout state is modified.
"""
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.delivery_territories import (
    DeliveryTerritory, DeliveryTerritoryVersion, OperatingRegion,
    TerritoryChangeAudit, StoreDeliveryTerritory,
)
from app.services.territory_preview import match_active_store_territory
from app.services.territory_publication import PublicationRejected, publish_initial_draft
from tests import factories


def _draft(db, *, complete=True, status="draft"):
    region = OperatingRegion(
        name="Synthetic publication region",
        slug=f"publish-{uuid4().hex}",
        status="active",
    )
    db.add(region)
    db.flush()
    territory = DeliveryTerritory(
        operating_region_id=region.id,
        name="Synthetic draft",
        geometry_type="circle",
        center_latitude=0 if complete else None,
        center_longitude=0 if complete else None,
        radius_km=1 if complete else None,
        status=status,
    )
    actor = factories.make_user(db)
    db.add(territory)
    db.flush()
    return territory, actor


def _publish(db, territory, actor, *, expected=None):
    return publish_initial_draft(
        db, territory_id=territory.id, actor_id=actor.id,
        expected_published_version=expected,
        reason="Approved synthetic test publication",
    )


def test_first_draft_publication_creates_immutable_version_and_audit_without_activation():
    with factories.session() as db:
        territory, actor = _draft(db)
        result = _publish(db, territory, actor)
        assert result.published_version == 1
        assert result.status == "draft"
        assert territory.status == "draft"
        assert territory.published_version == 1
        version = db.scalar(select(DeliveryTerritoryVersion).where(
            DeliveryTerritoryVersion.territory_id == territory.id,
        ))
        audit = db.scalar(select(TerritoryChangeAudit).where(
            TerritoryChangeAudit.territory_id == territory.id,
        ))
        assert version.snapshot["snapshot_format"] == "delivery-geometry-v1"
        assert version.published_at is not None
        assert version.changed_by == actor.id
        assert audit.action == "published"
        assert audit.new_version == 1
        assert audit.details["activation"] is False
        store = factories.make_store(db)
        db.add(StoreDeliveryTerritory(
            store_id=store.id, territory_id=territory.id,
            status="active", delivery_enabled=True,
        ))
        db.flush()
        assert match_active_store_territory(db, store.id, 0, 0) is None
        db.rollback()


def test_second_publication_with_stale_expected_version_fails_closed():
    with factories.session() as db:
        territory, actor = _draft(db)
        _publish(db, territory, actor)
        with pytest.raises(PublicationRejected) as err:
            _publish(db, territory, actor, expected=None)
        assert err.value.code == "version_conflict"
        versions = db.scalars(select(DeliveryTerritoryVersion).where(
            DeliveryTerritoryVersion.territory_id == territory.id,
        )).all()
        assert len(versions) == 1
        db.rollback()


def test_incomplete_geometry_cannot_publish_or_write_audit():
    with factories.session() as db:
        territory, actor = _draft(db, complete=False)
        with pytest.raises(PublicationRejected) as err:
            _publish(db, territory, actor)
        assert err.value.code == "invalid_geometry"
        assert db.scalar(select(DeliveryTerritoryVersion.id).where(
            DeliveryTerritoryVersion.territory_id == territory.id,
        )) is None
        assert db.scalar(select(TerritoryChangeAudit.id).where(
            TerritoryChangeAudit.territory_id == territory.id,
        )) is None
        db.rollback()


def test_active_territory_cannot_use_initial_draft_publisher():
    with factories.session() as db:
        territory, actor = _draft(db, status="active")
        with pytest.raises(PublicationRejected) as err:
            _publish(db, territory, actor)
        assert err.value.code == "not_draft"
        assert territory.published_version is None
        db.rollback()


def test_unknown_territory_and_short_reason_are_rejected():
    with factories.session() as db:
        actor = factories.make_user(db)
        with pytest.raises(PublicationRejected) as err:
            publish_initial_draft(
                db, territory_id=uuid4(), actor_id=actor.id,
                expected_published_version=None,
                reason="Approved synthetic test publication",
            )
        assert err.value.code == "not_found"
        territory, actor = _draft(db)
        with pytest.raises(PublicationRejected) as err:
            publish_initial_draft(
                db, territory_id=territory.id, actor_id=actor.id,
                expected_published_version=None, reason="short",
            )
        assert err.value.code == "invalid_reason"
        db.rollback()
