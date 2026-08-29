from app.core.config import settings
from app.services import maps


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "routes": [
                {
                    "distanceMeters": 2450,
                    "duration": "612.4s",
                    "polyline": {"encodedPolyline": "abc123"},
                }
            ]
        }


class _FakeClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json, headers):
        type(self).calls += 1
        assert url == maps.ROUTES_URL
        assert headers["X-Goog-FieldMask"] == maps.FIELD_MASK
        assert json["travelMode"] == "TWO_WHEELER"
        assert json["routingPreference"] == "TRAFFIC_AWARE"
        return _FakeResponse()


def _clear_cache():
    with maps._route_cache_lock:
        maps._route_cache.clear()
    _FakeClient.calls = 0


def test_maps_service_is_disabled_without_provider(monkeypatch):
    _clear_cache()
    monkeypatch.setattr(settings, "MAPS_PROVIDER", "none")
    monkeypatch.setattr(settings, "MAPS_API_KEY", None)
    assert maps.maps_enabled() is False
    assert maps.compute_route(20.0, 73.0, 20.1, 73.1) is None


def test_google_route_is_parsed_with_minimal_field_mask(monkeypatch):
    _clear_cache()
    monkeypatch.setattr(settings, "MAPS_PROVIDER", "google")
    monkeypatch.setattr(settings, "MAPS_API_KEY", "test-key")
    monkeypatch.setattr(maps.httpx, "Client", _FakeClient)
    result = maps.compute_route(20.0, 73.0, 20.1, 73.1)
    assert result is not None
    assert result.distance_meters == 2450
    assert result.duration_seconds == 612
    assert result.encoded_polyline == "abc123"


def test_near_identical_route_requests_reuse_short_lived_cache(monkeypatch):
    _clear_cache()
    monkeypatch.setattr(settings, "MAPS_PROVIDER", "google")
    monkeypatch.setattr(settings, "MAPS_API_KEY", "test-key")
    monkeypatch.setattr(maps.httpx, "Client", _FakeClient)

    first = maps.compute_route(20.00001, 73.00001, 20.10001, 73.10001)
    second = maps.compute_route(20.00002, 73.00002, 20.10002, 73.10002)

    assert first == second
    assert _FakeClient.calls == 1
