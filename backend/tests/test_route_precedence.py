"""Every shared public path must resolve to its hardened handler.

Several endpoints exist twice: a hardened implementation and an older one on
the same path, with the hardened router registered first so it wins at runtime.
That ordering is the only thing standing between a request and the unhardened
handler, and it is invisible in the file the legacy code lives in — reordering
`api_router.include_router(...)` calls, or moving a route between modules,
silently disarms the guarantee with no other symptom.

This asserts the resolution the application actually performs, by walking the
built route table rather than reading include order.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.main import app

#: (method, path) -> module.function that MUST handle it at runtime.
EXPECTED_WINNERS: dict[tuple[str, str], str] = {
    # Indexed PostGIS discovery, not the in-Python Haversine loop over every store.
    ("GET", "/api/v1/stores/nearby"): "store_discovery.nearby_stores_postgis",
    # Concurrency-safe checkout: row-locked cart, locked listings, idempotency.
    ("POST", "/api/v1/orders/checkout"): "checkout.safe_checkout",
    # Cancellation that restores stock exactly once and opens a refund obligation.
    ("POST", "/api/v1/orders/{order_id}/cancel"): "order_mutations.cancel_my_order_safely",
    # Merchant status updates restricted to merchant-assignable statuses.
    (
        "PATCH",
        "/api/v1/merchant/orders/{order_id}/status",
    ): "order_mutations.update_order_status_safely",
    # Completion requiring verified proof, a COD collection, and settlement.
    (
        "POST",
        "/api/v1/delivery/{delivery_id}/complete",
    ): "delivery_financials.complete_delivery_with_financials",
    # Location writes with accuracy, speed and physical-plausibility checks.
    (
        "POST",
        "/api/v1/delivery/{delivery_id}/location",
    ): "tracking_hardening.hardened_record_delivery_location",
    # Payment verification under row locks with settlement eligibility rules.
    ("POST", "/api/v1/payments/verify"): "payment_hardening.hardened_verify_payment",
    # Webhook with replay protection and refund reconciliation.
    ("POST", "/api/v1/payments/webhook"): "payment_hardening.hardened_razorpay_webhook",
}


def _resolved_routes() -> dict[tuple[str, str], list[str]]:
    """The route table as the application resolves it, in precedence order.

    FastAPI builds included routers lazily, so `app.routes` alone does not show
    the flattened table; the effective contexts are what requests match against.
    """
    included = [route for route in app.router.routes if type(route).__name__ == "_IncludedRouter"]
    table: dict[tuple[str, str], list[str]] = {}
    if included:
        for context in included[0].effective_route_contexts():
            label = f"{context.endpoint.__module__.split('.')[-1]}.{context.endpoint.__name__}"
            for method in context.methods:
                table.setdefault((method, context.path), []).append(label)
        return table
    # Older FastAPI: routes are flattened onto the app directly.
    for route in app.router.routes:
        if isinstance(route, APIRoute):
            label = f"{route.endpoint.__module__.split('.')[-1]}.{route.endpoint.__name__}"
            for method in route.methods:
                table.setdefault((method, route.path), []).append(label)
    return table


@pytest.fixture(scope="module")
def routes() -> dict[tuple[str, str], list[str]]:
    return _resolved_routes()


def test_the_route_table_is_readable(routes) -> None:
    """Guards the test itself: an empty table would make every case vacuous."""
    assert len(routes) > 50, "route table looks empty; the resolution walk is wrong"


@pytest.mark.parametrize(("key", "expected"), sorted(EXPECTED_WINNERS.items()))
def test_hardened_handler_wins(routes, key, expected) -> None:
    method, path = key
    handlers = routes.get(key)
    assert handlers, f"{method} {path} is not registered at all"
    assert handlers[0] == expected, (
        f"{method} {path} resolves to {handlers[0]}, expected the hardened "
        f"{expected}. Registration order in app/api/v1/router.py is what "
        f"decides this. Full chain: {handlers}"
    )


def test_every_shared_path_is_accounted_for(routes) -> None:
    """A new duplicate path must be a deliberate, reviewed decision.

    If two handlers start sharing a path without an entry here, this fails and
    forces someone to state which one is supposed to win.
    """
    shared = {key: handlers for key, handlers in routes.items() if len(handlers) > 1}
    unexpected = set(shared) - set(EXPECTED_WINNERS)
    assert not unexpected, (
        "new shared-path routes with no declared winner: "
        + ", ".join(f"{m} {p} -> {shared[(m, p)]}" for m, p in sorted(unexpected))
    )


def test_declared_expectations_still_describe_real_duplicates(routes) -> None:
    """Keeps this file honest when a legacy handler is finally deleted."""
    for key in EXPECTED_WINNERS:
        assert key in routes, f"{key[0]} {key[1]} no longer exists; update EXPECTED_WINNERS"


def test_delivery_completion_is_only_reachable_through_the_hardened_route(routes) -> None:
    """The specific bypass the audit was most concerned about."""
    status_handlers = routes.get(("PATCH", "/api/v1/delivery/{delivery_id}/status"))
    assert status_handlers == ["orders.update_delivery_status"]

    import inspect

    from app.api.v1.routes import orders as legacy_orders

    source = inspect.getsource(legacy_orders.update_delivery_status)
    # This handler must not be able to complete a delivery or move money, no
    # matter what a future schema change allows through validation.
    assert "PaymentStatus" not in source
    assert "OrderStatus.DELIVERED" not in source
    assert "ensure_settlement_entry" not in source
