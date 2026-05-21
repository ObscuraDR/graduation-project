"""
Database Initialization Script
Initialize PostgreSQL database with tables and seed data
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.connection import init_db, SessionLocal
from backend.database.models import (
    User, TrafficFlow, FlowFeature, AttackAlert, 
    AttackHistory, Model, Whitelist, Metric
)
from backend.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_data():
    """Seed database with initial data"""
    db = SessionLocal()
    
    try:
        # Create default admin user
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            admin_user = User(
                username="admin",
                email="admin@ids-system.com",
                password_hash=pwd_context.hash("admin123"),
                role="admin"
            )
            db.add(admin_user)
            logger.info("Created default admin user (username: admin, password: admin123)")
        
        # Add default whitelist entries
        default_whitelist = [
            {"ip_address": "127.0.0.1", "port": None, "protocol": None, "reason": "Localhost"},
            {"ip_address": "::1", "port": None, "protocol": None, "reason": "Localhost IPv6"},
        ]
        
        for entry in default_whitelist:
            existing = db.query(Whitelist).filter(
                Whititelist.ip_address == entry["ip_address"],
                Whitelist.port == entry["port"],
                Whitelist.protocol == entry["protocol"]
            ).first()
            
            if not existing:
                whitelist_item = Whitelist(**entry)
                db.add(whitelist_item)
                logger.info(f"Added whitelist entry: {entry['ip_address']}")
        
        db.commit()
        logger.info("Database seeded successfully")
        
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main initialization function"""
    logger.info("Initializing database...")
    
    # Create tables
    init_db()
    logger.info("Database tables created")
    
    # Seed data
    seed_data()
    
    logger.info("Database initialization completed")


if __name__ == "__main__":
    main()
