from app.db.session import SessionLocal
from app.services.fcm import flush_pending


def main() -> None:
    with SessionLocal() as db:
        result = flush_pending(db, limit=250)
        print(f"Notification dispatch: {result['events']} events, {result['pushes']} pushes")


if __name__ == "__main__":
    main()
