"""
Migration script to add user storage/download limits and file hash fields
Run this to upgrade your existing database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.models import User, File
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the database migration"""
    
    # Create engine and session
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        logger.info("Starting database migration for user limits and file hash...")
        
        # Add new columns to users table
        user_migrations = [
            "ALTER TABLE users ADD COLUMN storage_limit BIGINT DEFAULT 5368709120",  # 5GB
            "ALTER TABLE users ADD COLUMN daily_download_limit BIGINT DEFAULT 1073741824",  # 1GB
            "ALTER TABLE users ADD COLUMN storage_used BIGINT DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_download_reset DATETIME DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE users ADD COLUMN daily_downloads_used BIGINT DEFAULT 0"
        ]
        
        # Add new columns to files table
        file_migrations = [
            "ALTER TABLE files ADD COLUMN file_hash VARCHAR(64)",  # SHA-256 hash
            "ALTER TABLE files ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ]
        
        # Execute user table migrations
        for migration in user_migrations:
            try:
                db.execute(text(migration))
                logger.info(f"✅ Executed: {migration}")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    logger.info(f"⚠️  Column already exists, skipping: {migration}")
                else:
                    logger.error(f"❌ Failed: {migration} - {e}")
                    raise e
        
        # Execute file table migrations
        for migration in file_migrations:
            try:
                db.execute(text(migration))
                logger.info(f"✅ Executed: {migration}")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    logger.info(f"⚠️  Column already exists, skipping: {migration}")
                else:
                    logger.error(f"❌ Failed: {migration} - {e}")
                    raise e
        
        # Update existing users' storage_used based on their current files
        logger.info("Calculating storage usage for existing users...")
        
        users = db.query(User).all()
        for user in users:
            total_storage = db.execute(text("""
                SELECT COALESCE(SUM(file_size), 0) 
                FROM files 
                WHERE owner_id = :user_id AND is_active = 1
            """), {"user_id": user.id}).scalar()
            
            user.storage_used = total_storage or 0
            logger.info(f"User {user.username}: {user.storage_used / (1024*1024):.2f} MB used")
        
        # Set created_at for existing files if not set
        db.execute(text("""
            UPDATE files 
            SET created_at = upload_time 
            WHERE created_at IS NULL
        """))
        
        # Commit all changes
        db.commit()
        logger.info("✅ Migration completed successfully!")
        
        # Display summary
        logger.info("\n📊 MIGRATION SUMMARY:")
        logger.info("=====================================")
        logger.info("✅ Added user storage limits (5GB default)")
        logger.info("✅ Added daily download limits (1GB default)")
        logger.info("✅ Added storage usage tracking")
        logger.info("✅ Added file hash field for SHA-256")
        logger.info("✅ Updated existing user storage calculations")
        logger.info("=====================================")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting database migration...")
    if run_migration():
        print("✅ Migration completed successfully!")
        print("You can now restart your FastAPI server.")
    else:
        print("❌ Migration failed! Please check the logs.")
        sys.exit(1)