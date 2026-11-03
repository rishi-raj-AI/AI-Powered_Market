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


@pytest.mark.parametrize("unpaid", [False, True])
@pytest.mark.parametrize(
    ("scanned", "requires_review", "expected_exit"),
    [
        (0, 0, 3),
        (2, 0, None),
        (2, 1, 2),
    ],
)
def test_strict_audit_requires_nonempty_scope(
    monkeypatch, capsys, unpaid, scanned, requires_review, expected_exit
):
    """A zero-row staging audit is not evidence of payment integrity."""
    report = {
        "scanned": scanned,
        "requires_review": requires_review,
        "findings": [],
    }
    monkeypatch.setattr(
        audit_upi_payments,
        "audit_unpaid_upi" if unpaid else "audit_paid_upi",
        lambda *, limit, days: report,
    )
    argv = ["audit_upi_payments", "--require-scanned", "--fail-on-review"]
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


def test_empty_scope_remains_report_only_without_require_scanned(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["audit_upi_payments", "--fail-on-review"])
    monkeypatch.setattr(
        audit_upi_payments,
        "audit_paid_upi",
        lambda *, limit, days: {"scanned": 0, "requires_review": 0, "findings": []},
    )
    audit_upi_payments.main()
    assert json.loads(capsys.readouterr().out)["scanned"] == 0


@pytest.mark.parametrize("unpaid", [False, True])
@pytest.mark.parametrize(("truncated", "expected_exit"), [(True, 4), (False, None)])
def test_strict_audit_rejects_truncated_scope(monkeypatch, capsys, unpaid, truncated, expected_exit):
    report = {"scanned": 7, "requires_review": 0, "truncated": truncated, "findings": []}
    monkeypatch.setattr(
        audit_upi_payments,
        "audit_unpaid_upi" if unpaid else "audit_paid_upi",
        lambda *, limit, days: report,
    )
    argv = ["audit_upi_payments", "--limit", "7", "--fail-on-truncated"]
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


@pytest.mark.parametrize("unpaid", [False, True])
@pytest.mark.parametrize(
    ("scanned", "review", "truncated", "expected_exit"),
    [
        (2, 0, False, None),
        (0, 0, False, 3),
        (2, 1, False, 2),
        (2, 0, True, 4),
        (2, 1, True, 2),
    ],
)
def test_strict_combines_all_staging_release_gates(
    monkeypatch, capsys, unpaid, scanned, review, truncated, expected_exit
):
    report = {
        "scanned": scanned,
        "requires_review": review,
        "truncated": truncated,
        "findings": [{"order_number": "private-order", "result": "capture_mismatch"}] if review else [],
    }
    monkeypatch.setattr(
        audit_upi_payments,
        "audit_unpaid_upi" if unpaid else "audit_paid_upi",
        lambda *, limit, days: report,
    )
    argv = ["audit_upi_payments", "--strict", "--summary-only"]
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
    assert "private-order" not in output
    assert json.loads(output) == {
        "scanned": scanned, "requires_review": review, "truncated": truncated
    }


@pytest.mark.parametrize(
    ("paid_scanned", "unpaid_scanned", "review", "truncated", "expected_exit"),
    [
        (2, 3, 0, False, None),
        (0, 3, 0, False, 3),
        (2, 0, 0, False, 3),
        (2, 3, 1, False, 2),
        (2, 3, 0, True, 4),
    ],
)
def test_both_cohorts_strict_and_private(
    monkeypatch, capsys, paid_scanned, unpaid_scanned, review, truncated, expected_exit
):
    def paid(*, limit, days):
        assert (limit, days) == (9, 12)
        return {
            "scanned": paid_scanned,
            "requires_review": review,
            "truncated": False,
            "result_counts": {"verified_capture": paid_scanned},
            "findings": [{"order_number": "paid-private", "result": "verified_capture"}],
        }

    def unpaid(*, limit, days):
        assert (limit, days) == (9, 12)
        return {
            "scanned": unpaid_scanned,
            "requires_review": 0,
            "truncated": truncated,
            "result_counts": {"no_capture_found": unpaid_scanned},
            "findings": [{"order_number": "unpaid-private", "result": "no_capture_found"}],
        }

    monkeypatch.setattr(audit_upi_payments, "audit_paid_upi", paid)
    monkeypatch.setattr(audit_upi_payments, "audit_unpaid_upi", unpaid)
    monkeypatch.setattr(sys, "argv", [
        "audit_upi_payments", "--both", "--strict", "--summary-only",
        "--limit", "9", "--days", "12",
    ])
    if expected_exit is None:
        audit_upi_payments.main()
    else:
        with pytest.raises(SystemExit) as exc:
            audit_upi_payments.main()
        assert exc.value.code == expected_exit
    output = capsys.readouterr().out
    assert "paid-private" not in output
    assert "unpaid-private" not in output
    data = json.loads(output)
    assert data["scanned"] == paid_scanned + unpaid_scanned
    assert data["result_counts"] == {
        "paid": {"verified_capture": paid_scanned},
        "unpaid": {"no_capture_found": unpaid_scanned},
    }
    assert data["cohorts"]["paid"]["scanned"] == paid_scanned
    assert data["cohorts"]["unpaid"]["scanned"] == unpaid_scanned
    assert "findings" not in data["cohorts"]["paid"]
    assert "findings" not in data["cohorts"]["unpaid"]


def test_both_and_unpaid_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["audit_upi_payments", "--both", "--unpaid"])
    with pytest.raises(SystemExit) as exc:
        audit_upi_payments.main()
    assert exc.value.code == 2
