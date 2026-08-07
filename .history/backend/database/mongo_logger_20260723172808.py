"""
Flow logging helper for PostgreSQL-backed flow records.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

COLLECTION = "flow_logs"


def log_flow_summary(
    flow_id: Optional[int],
    flow_stats: dict,
    features: dict,
) -> None:
    """Insert a flow summary document into MongoDB flow_logs collection.

    Silently skips if MongoDB is unavailable (non-blocking for the pipeline).
    """
    try:
        from backend.database.connection import get_mongo_db

        db = get_mongo_db()
        doc = {
            "flow_id": flow_id,
            "src_ip": flow_stats.get("src_ip"),
            "dst_ip": flow_stats.get("dst_ip"),
            "src_port": flow_stats.get("src_port"),
            "dst_port": flow_stats.get("dst_port"),
            "protocol": flow_stats.get("protocol"),
            "timestamp": datetime.now(timezone.utc),
            "features": features,
        }
        db[COLLECTION].insert_one(doc)
        logger.debug("Flow summary logged to MongoDB: flow_id=%s", flow_id)
    except Exception as exc:
        logger.warning("MongoDB flow log skipped: %s", exc)
