"""
scripts/test_redis_connection.py
Verify Redis connectivity: set → get → delete a test key.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database.connection import get_redis_client

KEY = "ids:healthcheck"
VALUE = "ok"


def main():
    try:
        r = get_redis_client()

        r.set(KEY, VALUE, ex=30)

        val = r.get(KEY)
        assert val == VALUE, f"Expected '{VALUE}', got '{val}'"

        r.delete(KEY)
        assert r.get(KEY) is None, "Key not deleted"

        print(f"[PASS] Redis: set/get/delete OK (key={KEY})")
        sys.exit(0)
    except Exception as exc:
        print(f"[FAIL] Redis: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
