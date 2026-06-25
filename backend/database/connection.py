"""
Database Connection
PostgreSQL and MongoDB connection management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging
from typing import Optional

from backend.config import settings
from backend.database.models import Base

logger = logging.getLogger(__name__)


# PostgreSQL connection
engine = create_engine(
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}",
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
    connect_args={
        "connect_timeout": 10,
        "options": "-c timezone=UTC"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def get_db() -> Session:
    """Get database session (FastAPI dependency)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_mongo_db():
    """
    Return a MongoDB database handle.
    Returns None silently if pymongo is not installed or MongoDB is unreachable.
    """
    try:
        import pymongo
        mongo_uri = getattr(settings, 'mongo_uri', None) or (
            f"mongodb://{getattr(settings, 'mongodb_host', 'localhost')}:"
            f"{getattr(settings, 'mongodb_port', 27017)}/"
        )
        mongo_db_name = getattr(settings, 'mongo_db', None) or getattr(settings, 'mongodb_db', 'ids_logs')
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        return client[mongo_db_name]
    except Exception as e:
        logger.debug("MongoDB unavailable: %s", e)
        return None


def close_connections():
    """Close all database connections"""
    engine.dispose()
    logger.info("PostgreSQL connection closed")
