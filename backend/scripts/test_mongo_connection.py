"""
scripts/test_postgres_connection.py
Verify PostgreSQL connectivity by opening a session and running a simple query.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database.connection import SessionLocal


def main():
    try:
        db = SessionLocal()
        try:
            result = db.execute("SELECT 1").scalar()
            assert result == 1, f"Unexpected SQL result: {result}"
        finally:
            db.close()

        print("[PASS] PostgreSQL connection OK")
        sys.exit(0)
    except Exception as exc:
        print(f"[FAIL] PostgreSQL connection: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
