from app.main import app


def _first_endpoint_name(path: str, method: str) -> str | None:
    for route in app.routes:
        if getattr(route, "path", None) != path:
            continue
        methods = getattr(route, "methods", set()) or set()
        if method not in methods:
            continue
        endpoint = getattr(route, "endpoint", None)
        return getattr(endpoint, "__name__", None)
    return None


def test_nearby_store_route_prefers_indexed_postgis_handler() -> None:
    assert _first_endpoint_name("/api/v1/stores/nearby", "GET") == "nearby_stores_postgis"


def test_serviceability_route_uses_geography_handler() -> None:
    assert _first_endpoint_name("/api/v1/location/serviceability", "GET") == "location_serviceability"
