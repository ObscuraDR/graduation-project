"""
Database Connection
PostgreSQL and MongoDB connection management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from pymongo import MongoClient
from redis import Redis
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
    echo=False
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
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# MongoDB connection
_mongo_client: Optional[MongoClient] = None
_mongo_db = None


def _mongo_uri() -> str:
    """Return connection URI, preferring MONGO_URI env override."""
    if settings.mongo_uri:
        return settings.mongo_uri
    return f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}/"


def _mongo_dbname() -> str:
    return settings.mongo_db or settings.mongodb_db


def get_mongo_client() -> MongoClient:
    """Get MongoDB client"""
    global _mongo_client, _mongo_db
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(_mongo_uri(), serverSelectionTimeoutMS=5000)
            _mongo_db = _mongo_client[_mongo_dbname()]
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise
    return _mongo_client


def get_mongo_db():
    """Get MongoDB database"""
    get_mongo_client()
    return _mongo_db


# Redis connection
_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get Redis client"""
    global _redis_client
    if _redis_client is None:
        try:
            if settings.redis_url:
                _redis_client = Redis.from_url(
                    settings.redis_url, decode_responses=True
                )
            else:
                _redis_client = Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    decode_responses=True,
                )
            _redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Error connecting to Redis: {e}")
            raise
    return _redis_client


def close_connections():
    """Close all database connections"""
    global _mongo_client, _redis_client
    
    if _mongo_client:
        _mongo_client.close()
        logger.info("MongoDB connection closed")
    
    if _redis_client:
        _redis_client.close()
        logger.info("Redis connection closed")
    
    engine.dispose()
    logger.info("PostgreSQL connection closed")
