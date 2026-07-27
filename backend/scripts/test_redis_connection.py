"""
scripts/test_cache_connection.py
Verify the in-memory cache is available.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.cache.redis_cache import get_cache

KEY = "ids:healthcheck"
VALUE = "ok"


def main():
    try:
        cache = get_cache()
        cache.set(KEY, VALUE, ttl=30)
        val = cache.get(KEY)
        assert val == VALUE, f"Expected '{VALUE}', got '{val}'"
        cache.delete(KEY)
        print("[PASS] In-memory cache OK")
        sys.exit(0)
    except Exception as exc:
        print(f"[FAIL] Cache check: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
