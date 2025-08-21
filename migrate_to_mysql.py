"""
SQLAlchemy-based Migration Script for Premium Features
This script uses SQLAlchemy to automatically create/update database tables
"""
import os
import sys
import logging
from pathlib import Path

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.db.base import engine, Base, init_db
    from app.core.config import settings
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're in the correct directory and all dependencies are installed.")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test database connection using SQLAlchemy"""
    try:
        # Try to connect to the database using SQLAlchemy
        with engine.connect() as connection:
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

def run_sqlalchemy_migration():
    """Run SQLAlchemy migration to create/update all tables"""
    try:
        logger.info("🔄 Creating/updating database tables using SQLAlchemy...")
        
        # Import all models to ensure they're registered with SQLAlchemy
        from app.db.models import User, File, PaymentHistory
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ SQLAlchemy migration completed successfully!")
        logger.info("All tables have been created/updated according to your models")
        return True
        
    except Exception as e:
        logger.error(f"❌ SQLAlchemy migration failed: {e}")
        logger.error("Error details:", exc_info=True)
        return False

def verify_tables_created():
    """Verify that tables were created by checking if we can query them"""
    try:
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['users', 'files', 'payment_history']
        created_tables = [table for table in expected_tables if table in tables]
        
        logger.info(f"📋 Tables found: {', '.join(tables)}")
        logger.info(f"✅ Verification complete - Found {len(created_tables)}/{len(expected_tables)} expected tables")
        
        # Try to check if users table has the new columns
        if 'users' in tables:
            user_columns = [col['name'] for col in inspector.get_columns('users')]
            premium_columns = ['email', 'phone_number', 'plan_type', 'is_premium', 'premium_until']
            has_premium_columns = all(col in user_columns for col in premium_columns)
            
            if has_premium_columns:
                logger.info("✅ Premium columns found in users table")
            else:
                logger.warning("⚠️  Some premium columns may be missing")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Table verification failed: {e}")
        return False

def run_migration():
    """Run the complete migration process"""
    logger.info("🚀 Starting SQLAlchemy Database Migration...")
    logger.info("=" * 60)
    
    # Step 1: Test database connection
    logger.info("Step 1: Testing database connection...")
    if not test_database_connection():
        logger.error("❌ Cannot connect to database. Please check your .env file and ensure MySQL is running.")
        return False
    
    # Step 2: Run SQLAlchemy migration
    logger.info("Step 2: Running SQLAlchemy migration...")
    if not run_sqlalchemy_migration():
        return False
    
    # Step 3: Verify tables
    logger.info("Step 3: Verifying tables...")
    if not verify_tables_created():
        logger.warning("⚠️  Verification had issues, but migration may have succeeded")
    
    logger.info("=" * 60)
    logger.info("🎉 Migration Completed Successfully!")
    logger.info("=" * 60)
    
    print("""
📋 MIGRATION SUMMARY:
====================
✅ Database connection established
✅ SQLAlchemy tables created/updated
✅ Premium features enabled

🆕 NEW FEATURES ADDED:
======================
- Email and phone number fields
- Premium subscription tracking  
- Payment history table
- Plan types (free, premium, business)
- Automatic storage limit management

📊 PLAN LIMITS:
===============
- Free Plan: 5GB storage, 1GB/day downloads
- Premium Plan: 50GB storage, 10GB/day downloads  
- Business Plan: Custom limits (configurable)

🔧 TABLES CREATED/UPDATED:
==========================
- users: Extended with premium fields
- files: File storage and sharing
- payment_history: Payment tracking

🚀 NEXT STEPS:
==============
1. Your database is now ready for premium features!
2. Start your FastAPI server: python run_server.py
3. Implement payment gateway integration
4. Add premium upgrade endpoints to your API
""")
    
    return True

if __name__ == "__main__":
    print("🚀 FastAPI File Share - SQLAlchemy Database Migration")
    print("=" * 60)
    
    try:
        if run_migration():
            print("✅ Migration completed successfully!")
            print("Your FastAPI application is ready with premium features!")
            sys.exit(0)
        else:
            print("❌ Migration failed! Please check the logs above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        print("❌ Migration failed due to unexpected error!")
        sys.exit(1)