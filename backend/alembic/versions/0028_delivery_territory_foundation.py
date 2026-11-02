"""Add draft-only territory storage without changing existing delivery decisions.

Revision ID: 0028_delivery_territories
Revises: 0027_address_location_provenance

No legacy rows are modified. No territories are activated or assigned.
The existing PostGIS extension (installed by revision 0009) is required.
"""
from alembic import op

revision = "0028_delivery_territories"
down_revision = "0027_address_location_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE operating_regions (
            id uuid PRIMARY KEY, name varchar(160) NOT NULL,
            slug varchar(180) NOT NULL UNIQUE, state_code varchar(8),
            status varchar(16) NOT NULL DEFAULT 'draft',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_operating_regions_status CHECK (status IN ('draft', 'active', 'inactive'))
        )
        """,
        """
        CREATE TABLE delivery_hubs (
            id uuid PRIMARY KEY,
            operating_region_id uuid NOT NULL REFERENCES operating_regions(id),
            name varchar(160) NOT NULL,
            latitude numeric(9,6) NOT NULL,
            longitude numeric(9,6) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'draft',
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_delivery_hubs_latitude CHECK (latitude BETWEEN -90 AND 90),
            CONSTRAINT ck_delivery_hubs_longitude CHECK (longitude BETWEEN -180 AND 180),
            CONSTRAINT ck_delivery_hubs_status CHECK (status IN ('draft', 'active', 'inactive'))
        )
        """,
        "CREATE INDEX ix_delivery_hubs_operating_region_id ON delivery_hubs (operating_region_id)",
        """
        CREATE TABLE delivery_territories (
            id uuid PRIMARY KEY,
            operating_region_id uuid NOT NULL REFERENCES operating_regions(id),
            hub_id uuid REFERENCES delivery_hubs(id),
            legacy_service_area_id uuid UNIQUE REFERENCES service_areas(id),
            name varchar(160) NOT NULL,
            geometry_type varchar(16) NOT NULL,
            geometry geometry(MULTIPOLYGON,4326),
            center_latitude numeric(9,6),
            center_longitude numeric(9,6),
            radius_km numeric(10,3),
            status varchar(16) NOT NULL DEFAULT 'draft',
            priority integer NOT NULL DEFAULT 0,
            effective_from timestamptz,
            effective_until timestamptz,
            published_version integer,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_delivery_territories_type CHECK (geometry_type IN ('circle', 'polygon')),
            CONSTRAINT ck_delivery_territories_status CHECK (status IN ('draft', 'active', 'inactive')),
            CONSTRAINT ck_delivery_territories_latitude CHECK (center_latitude IS NULL OR center_latitude BETWEEN -90 AND 90),
            CONSTRAINT ck_delivery_territories_longitude CHECK (center_longitude IS NULL OR center_longitude BETWEEN -180 AND 180),
            CONSTRAINT ck_delivery_territories_center_pair CHECK ((center_latitude IS NULL) = (center_longitude IS NULL)),
            CONSTRAINT ck_delivery_territories_radius CHECK (radius_km IS NULL OR radius_km > 0),
            CONSTRAINT ck_delivery_territories_dates CHECK (effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from),
            CONSTRAINT ck_delivery_territories_valid_geom CHECK (geometry IS NULL OR ST_IsValid(geometry))
        )
        """,
        "CREATE INDEX ix_delivery_territories_operating_region_id ON delivery_territories (operating_region_id)",
        "CREATE INDEX ix_delivery_territories_hub_id ON delivery_territories (hub_id)",
        "CREATE INDEX ix_delivery_territories_geometry_gist ON delivery_territories USING gist (geometry)",
        """
        CREATE TABLE delivery_territory_exclusions (
            id uuid PRIMARY KEY,
            territory_id uuid NOT NULL REFERENCES delivery_territories(id),
            geometry geometry(MULTIPOLYGON,4326) NOT NULL,
            reason varchar(240),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_delivery_territory_exclusions_valid_geom CHECK (ST_IsValid(geometry))
        )
        """,
        "CREATE INDEX ix_delivery_territory_exclusions_territory_id ON delivery_territory_exclusions (territory_id)",
        "CREATE INDEX ix_delivery_territory_exclusions_geometry_gist ON delivery_territory_exclusions USING gist (geometry)",
        """
        CREATE TABLE store_delivery_territories (
            id uuid PRIMARY KEY,
            store_id uuid NOT NULL REFERENCES stores(id),
            territory_id uuid NOT NULL REFERENCES delivery_territories(id),
            status varchar(16) NOT NULL DEFAULT 'draft',
            delivery_enabled boolean NOT NULL DEFAULT true,
            priority integer NOT NULL DEFAULT 0,
            effective_from timestamptz,
            effective_until timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_store_delivery_territory UNIQUE (store_id, territory_id),
            CONSTRAINT ck_store_delivery_territories_status CHECK (status IN ('draft', 'active', 'inactive')),
            CONSTRAINT ck_store_delivery_territories_dates CHECK (effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from)
        )
        """,
        "CREATE INDEX ix_store_delivery_territories_store_id ON store_delivery_territories (store_id)",
        "CREATE INDEX ix_store_delivery_territories_territory_id ON store_delivery_territories (territory_id)",
        """
        CREATE TABLE delivery_territory_versions (
            id uuid PRIMARY KEY,
            territory_id uuid NOT NULL REFERENCES delivery_territories(id),
            version integer NOT NULL,
            snapshot jsonb NOT NULL,
            changed_by uuid NOT NULL REFERENCES users(id),
            change_reason text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            published_at timestamptz,
            CONSTRAINT uq_delivery_territory_version UNIQUE (territory_id, version),
            CONSTRAINT ck_delivery_territory_versions_positive CHECK (version > 0)
        )
        """,
        "CREATE INDEX ix_delivery_territory_versions_territory_id ON delivery_territory_versions (territory_id)",
        """
        CREATE TABLE territory_change_audit (
            id uuid PRIMARY KEY,
            territory_id uuid NOT NULL REFERENCES delivery_territories(id),
            actor_id uuid NOT NULL REFERENCES users(id),
            action varchar(32) NOT NULL,
            previous_version integer,
            new_version integer,
            change_reason text NOT NULL,
            details jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_territory_change_audit_action CHECK (
                action IN ('draft_created', 'draft_edited', 'published', 'rolled_back',
                           'store_assigned', 'store_unassigned')
            )
        )
        """,
        "CREATE INDEX ix_territory_change_audit_territory_id ON territory_change_audit (territory_id)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    # Safe only before territory adoption; never discard published audit history.
    for table in (
        "territory_change_audit", "delivery_territory_versions",
        "store_delivery_territories", "delivery_territory_exclusions",
        "delivery_territories", "delivery_hubs", "operating_regions",
    ):
        op.execute(f"DROP TABLE {table}")
