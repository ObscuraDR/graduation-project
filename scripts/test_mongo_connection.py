"""
scripts/test_mongo_connection.py
Verify MongoDB connectivity: insert → read → delete a test document.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from backend.database.connection import get_mongo_client, _mongo_dbname

COLLECTION = "ids_healthcheck"


def main():
    try:
        client = get_mongo_client()
        db = client[_mongo_dbname()]
        col = db[COLLECTION]

        doc = {"test": "healthcheck", "ts": datetime.now(timezone.utc)}
        result = col.insert_one(doc)
        inserted_id = result.inserted_id

        found = col.find_one({"_id": inserted_id})
        assert found is not None, "Document not found after insert"

        col.delete_one({"_id": inserted_id})
        assert col.find_one({"_id": inserted_id}) is None, "Document not deleted"

        print(f"[PASS] MongoDB: insert/read/delete OK (db={_mongo_dbname()}, collection={COLLECTION})")
        sys.exit(0)
    except Exception as exc:
        print(f"[FAIL] MongoDB: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
