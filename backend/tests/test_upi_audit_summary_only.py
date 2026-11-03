"""Aggregate-only reconciliation output must not leak per-order identifiers."""
import json
import sys

import pytest

from app.scripts import audit_upi_payments


@pytest.mark.parametrize("unpaid", [False, True])
@pytest.mark.parametrize(
    ("review", "truncated", "expected_exit"),
    [(0, False, None), (1, False, 2), (0, True, 4)],
)
def test_summary_only_preserves_gates_and_hides_findings(
    monkeypatch, capsys, unpaid, review, truncated, expected_exit
):
    report = {
        "scanned": 2,
        "truncated": truncated,
        "verified": 2 - review,
        "requires_review": review,
        "result_counts": {"verified_capture": 2 - review},
        "findings": [{"order_number": "PRIVATE-ORDER-123", "result": "capture_mismatch"}],
    }
    monkeypatch.setattr(
        audit_upi_payments,
        "audit_unpaid_upi" if unpaid else "audit_paid_upi",
        lambda *, limit, days: report,
    )
    argv = [
        "audit_upi_payments", "--summary-only", "--fail-on-review",
        "--fail-on-truncated", "--require-scanned",
    ]
    if unpaid:
        argv.append("--unpaid")
    monkeypatch.setattr(sys, "argv", argv)
    if expected_exit is None:
        audit_upi_payments.main()
    else:
        with pytest.raises(SystemExit) as exc:
            audit_upi_payments.main()
        assert exc.value.code == expected_exit
    output = capsys.readouterr().out
    assert "PRIVATE-ORDER-123" not in output
    parsed = json.loads(output)
    assert "findings" not in parsed
    assert parsed == {key: value for key, value in report.items() if key != "findings"}


@pytest.mark.parametrize("unpaid", [False, True])
def test_summary_only_empty_scope_still_exits_three(monkeypatch, capsys, unpaid):
    monkeypatch.setattr(
        audit_upi_payments,
        "audit_unpaid_upi" if unpaid else "audit_paid_upi",
        lambda *, limit, days: {
            "scanned": 0, "requires_review": 0, "truncated": False,
            "findings": [{"order_number": "PRIVATE-ORDER-123"}],
        },
    )
    argv = ["audit_upi_payments", "--summary-only", "--require-scanned"]
    if unpaid:
        argv.append("--unpaid")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        audit_upi_payments.main()
    assert exc.value.code == 3
    assert "PRIVATE-ORDER-123" not in capsys.readouterr().out
