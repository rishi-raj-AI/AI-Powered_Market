"""Drain owed refunds to the payment provider.

Run continuously by the production worker service. Safe to run concurrently
with itself and with admin-triggered retries: every refund is claimed under a
row lock before any provider call, and the provider request carries an
idempotency key.
"""

from app.db.session import SessionLocal
from app.services.refunds import dispatch_due_refunds


def main() -> None:
    with SessionLocal() as db:
        result = dispatch_due_refunds(db, limit=50)
        print(
            "Refund dispatch: "
            f"{result['considered']} considered, {result['succeeded']} succeeded, "
            f"{result['processing']} processing, {result['failed']} failed"
        )


if __name__ == "__main__":
    main()
