"""Real PostGIS tests for the inactive-by-default territory preview engine.

All test rows are synthetic and rolled back. The checkout read path is untouched.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.delivery_territories import (
    DeliveryTerritory, DeliveryTerritoryVersion, OperatingRegion,
    StoreDeliveryTerritory,
)
from app.services.territory_preview import match_active_store_territory
from tests import factories


def _active_territory(db, store, *, kind="circle", priority=0, assignment_priority=0):
    region = OperatingRegion(
        name="Synthetic preview region",
        slug=f"preview-{uuid4().hex}",
        status="active",
    )
    db.add(region)
    db.flush()
    territory = DeliveryTerritory(
        operating_region_id=region.id,
        name="Synthetic preview territory",
        geometry_type=kind,
        status="active",
        center_latitude=0 if kind == "circle" else None,
        center_longitude=0 if kind == "circle" else None,
        radius_km=1 if kind == "circle" else None,
        priority=priority,
    )
    db.add(territory)
    db.flush()
    actor = factories.make_user(db)
    db.add(DeliveryTerritoryVersion(
        territory_id=territory.id,
        version=1,
        snapshot={"geometry_type": kind},
        changed_by=actor.id,
        change_reason="Synthetic published version",
        published_at=datetime.now(timezone.utc),
    ))
    territory.published_version = 1
    db.flush()
    assignment = StoreDeliveryTerritory(
        store_id=store.id,
        territory_id=territory.id,
        status="active",
        delivery_enabled=True,
        priority=assignment_priority,
    )
    db.add(assignment)
    db.flush()
    return region, territory, assignment


def test_circle_is_geodesic_and_boundary_does_not_expand():
    with factories.session() as db:
        store = factories.make_store(db)
        _, territory, _ = _active_territory(db, store)
        inside = match_active_store_territory(db, store.id, 0.0, 0.0089)
        assert inside is not None and inside.territory_id == territory.id
        assert match_active_store_territory(db, store.id, 0.0, 0.0091) is None
        db.rollback()


def test_polygon_includes_outer_boundary_but_excludes_holes_and_their_edges():
    with factories.session() as db:
        store = factories.make_store(db)
        _, territory, _ = _active_territory(db, store, kind="polygon")
        db.execute(
            text("""
                UPDATE delivery_territories
                SET geometry=ST_Multi(ST_GeomFromText(
                    'POLYGON((0 0,1 0,1 1,0 1,0 0))',4326))
                WHERE id=:id
            """),
            {"id": territory.id},
        )
        db.execute(
            text("""
                INSERT INTO delivery_territory_exclusions (id, territory_id, geometry)
                VALUES (:id, :territory_id, ST_Multi(ST_GeomFromText(
                    'POLYGON((0.4 0.4,0.6 0.4,0.6 0.6,0.4 0.6,0.4 0.4))',
                    4326)))
            """),
            {"id": uuid4(), "territory_id": territory.id},
        )
        assert match_active_store_territory(db, store.id, 0.0, 0.5) is not None
        assert match_active_store_territory(db, store.id, 0.5, 0.5) is None
        assert match_active_store_territory(db, store.id, 0.4, 0.5) is None
        assert match_active_store_territory(db, store.id, 2.0, 2.0) is None
        db.rollback()


def test_inactive_region_territory_assignment_and_expired_windows_are_ignored():
    with factories.session() as db:
        store = factories.make_store(db)
        region, territory, assignment = _active_territory(db, store)
        when = datetime(2026, 11, 2, tzinfo=timezone.utc)
        def matches():
            return match_active_store_territory(
                db, store.id, 0.0, 0.0, evaluated_at=when,
            ) is not None

        assert matches()
        territory.published_version = None
        db.flush()
        assert not matches()
        territory.published_version = 1
        region.status = "inactive"
        db.flush()
        assert not matches()
        region.status = "active"
        territory.status = "draft"
        db.flush()
        assert not matches()
        territory.status = "active"
        assignment.delivery_enabled = False
        db.flush()
        assert not matches()
        assignment.delivery_enabled = True
        assignment.effective_from = when + timedelta(seconds=1)
        db.flush()
        assert not matches()
        assignment.effective_from = when
        territory.effective_until = when
        db.flush()
        assert not matches()
        territory.effective_until = when + timedelta(seconds=1)
        db.flush()
        assert matches()
        db.rollback()


def test_overlaps_select_explicit_assignment_priority_then_territory_priority():
    with factories.session() as db:
        store = factories.make_store(db)
        _, low, low_assignment = _active_territory(
            db, store, priority=50, assignment_priority=0,
        )
        _, high, high_assignment = _active_territory(
            db, store, priority=0, assignment_priority=10,
        )
        assert match_active_store_territory(db, store.id, 0.0, 0.0).territory_id == high.id
        high_assignment.priority = 0
        low_assignment.priority = 0
        db.flush()
        assert match_active_store_territory(db, store.id, 0.0, 0.0).territory_id == low.id
        db.rollback()


def test_other_store_assignment_does_not_grant_coverage():
    with factories.session() as db:
        first = factories.make_store(db)
        other = factories.make_store(db)
        _active_territory(db, first)
        assert match_active_store_territory(db, other.id, 0.0, 0.0) is None
        db.rollback()


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(91, 0), (0, -181), (float("nan"), 0), (0, float("inf"))],
)
def test_invalid_coordinates_rejected_before_postgis(latitude, longitude):
    with factories.session() as db:
        with pytest.raises(ValueError, match="coordinates"):
            match_active_store_territory(db, uuid4(), latitude, longitude)


def test_naive_evaluation_time_rejected():
    with factories.session() as db:
        with pytest.raises(ValueError, match="timezone-aware"):
            match_active_store_territory(
                db, uuid4(), 0, 0, evaluated_at=datetime(2026, 11, 2),
            )
