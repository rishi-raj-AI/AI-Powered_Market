"""Regression coverage for non-identifying reconciliation summary counts."""
from app.scripts.audit_upi_payments import _result_counts


def test_result_counts_empty():
    assert _result_counts([]) == {}


def test_result_counts_groups_and_sorts_without_order_identifiers():
    findings = [
        {"order_number": "SENSITIVE-1", "result": "provider_unavailable"},
        {"order_number": "SENSITIVE-2", "result": "verified_capture"},
        {"order_number": "SENSITIVE-3", "result": "provider_unavailable"},
        {"order_number": "SENSITIVE-4", "result": "capture_mismatch"},
    ]
    assert _result_counts(findings) == {
        "capture_mismatch": 1,
        "provider_unavailable": 2,
        "verified_capture": 1,
    }
    assert "SENSITIVE" not in str(_result_counts(findings))
