"""Combined UPI reconciliation must preserve evidence without leaking it in CI mode."""
import json
import sys

import pytest

from app.scripts import audit_upi_payments


@pytest.mark.parametrize("summary_only", [False, True])
def test_combined_audit_findings_preserved_or_redacted(monkeypatch, capsys, summary_only):
    paid = {
        "scanned": 1, "requires_review": 1, "truncated": False,
        "result_counts": {"capture_mismatch": 1},
        "findings": [{"order_number": "PRIVATE-PAID", "result": "capture_mismatch"}],
    }
    unpaid = {
        "scanned": 1, "requires_review": 0, "truncated": False,
        "result_counts": {"no_capture_found": 1},
        "findings": [{"order_number": "PRIVATE-UNPAID", "result": "no_capture_found"}],
    }
    monkeypatch.setattr(audit_upi_payments, "audit_paid_upi", lambda *, limit, days: paid)
    monkeypatch.setattr(audit_upi_payments, "audit_unpaid_upi", lambda *, limit, days: unpaid)
    argv = ["audit_upi_payments", "--both"]
    if summary_only:
        argv.append("--summary-only")
    monkeypatch.setattr(sys, "argv", argv)
    audit_upi_payments.main()
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["scanned"] == 2
    assert report["requires_review"] == 1
    if summary_only:
        assert "PRIVATE-PAID" not in output
        assert "PRIVATE-UNPAID" not in output
        assert "findings" not in report
        assert all("findings" not in cohort for cohort in report["cohorts"].values())
    else:
        assert report["findings"] == [
            {"cohort": "paid", **paid["findings"][0]},
            {"cohort": "unpaid", **unpaid["findings"][0]},
        ]
        assert report["cohorts"]["paid"]["findings"] == paid["findings"]
        assert report["cohorts"]["unpaid"]["findings"] == unpaid["findings"]
