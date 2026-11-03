"""CLI contract for read-only payment reconciliation gating."""
import json
import sys

import pytest

from app.scripts import audit_upi_payments


@pytest.mark.parametrize(
    ("unpaid", "review_count", "expected_exit"),
    [
        (False, 0, None),
        (False, 2, 2),
        (True, 0, None),
        (True, 1, 2),
    ],
)
def test_fail_on_review_exit_status(monkeypatch, capsys, unpaid, review_count, expected_exit):
    report = {"scanned": 3, "requires_review": review_count, "findings": []}
    def fake_audit(*, limit, days):
        assert limit == 7
        assert days == 14
        return report

    monkeypatch.setattr(
        audit_upi_payments,
        "audit_unpaid_upi" if unpaid else "audit_paid_upi",
        fake_audit,
    )
    argv = ["audit_upi_payments", "--limit", "7", "--days", "14", "--fail-on-review"]
    if unpaid:
        argv.append("--unpaid")
    monkeypatch.setattr(sys, "argv", argv)
    if expected_exit is None:
        audit_upi_payments.main()
    else:
        with pytest.raises(SystemExit) as exc:
            audit_upi_payments.main()
        assert exc.value.code == expected_exit
    assert json.loads(capsys.readouterr().out) == report


def test_without_strict_flag_review_is_report_only(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["audit_upi_payments"])
    monkeypatch.setattr(
        audit_upi_payments,
        "audit_paid_upi",
        lambda *, limit, days: {"scanned": 1, "requires_review": 1, "findings": []},
    )
    audit_upi_payments.main()
    assert json.loads(capsys.readouterr().out)["requires_review"] == 1
