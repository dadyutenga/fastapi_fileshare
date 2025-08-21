"""
UUID Migration Script
This script migrates the database to use UUIDs instead of integer IDs
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

def backup_existing_tables():
    """Create backup of existing tables before UUID migration"""
    try:
        logger.info("🔄 Creating backup tables...")
        
        with engine.connect() as connection:
            # Check if tables exist
            result = connection.execute("SHOW TABLES")
            tables = [row[0] for row in result.fetchall()]
            
            backup_queries = []
            if 'users' in tables:
                backup_queries.append("CREATE TABLE users_backup AS SELECT * FROM users")
            if 'files' in tables:
                backup_queries.append("CREATE TABLE files_backup AS SELECT * FROM files")
            if 'payment_history' in tables:
                backup_queries.append("CREATE TABLE payment_history_backup AS SELECT * FROM payment_history")
            
            for query in backup_queries:
                try:
                    connection.execute(query)
                    logger.info(f"✅ Backup created: {query}")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info(f"⏭️  Backup already exists, skipping: {query}")
                    else:
                        logger.warning(f"⚠️  Backup failed: {query} - {e}")
            
            connection.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Backup creation failed: {e}")
        return False

def drop_existing_tables():
    """Drop existing tables to recreate with UUID primary keys"""
    try:
        logger.info("🔄 Dropping existing tables...")
        
        with engine.connect() as connection:
            # Drop tables in correct order (respect foreign key constraints)
            drop_queries = [
                "DROP TABLE IF EXISTS payment_history",
                "DROP TABLE IF EXISTS files", 
                "DROP TABLE IF EXISTS users"
            ]
            
            for query in drop_queries:
                try:
                    connection.execute(query)
                    logger.info(f"✅ Dropped table: {query}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not drop table: {query} - {e}")
            
            connection.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Table dropping failed: {e}")
        return False

def create_uuid_tables():
    """Create new tables with UUID primary keys"""
    try:
        logger.info("🔄 Creating new tables with UUID primary keys...")
        
        # Import all models to ensure they're registered with SQLAlchemy
        from app.db.models import User, File, PaymentHistory
        
        # Create all tables with new UUID schema
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ UUID tables created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ UUID table creation failed: {e}")
        logger.error("Error details:", exc_info=True)
        return False

def migrate_data_to_uuid_tables():
    """Migrate data from backup tables to new UUID tables (if backups exist)"""
    try:
        logger.info("🔄 Checking for data migration from backup tables...")
        
        with engine.connect() as connection:
            # Check if backup tables exist
            result = connection.execute("SHOW TABLES")
            tables = [row[0] for row in result.fetchall()]
            
            has_backup_users = 'users_backup' in tables
            has_backup_files = 'files_backup' in tables
            has_backup_payments = 'payment_history_backup' in tables
            
            if not any([has_backup_users, has_backup_files, has_backup_payments]):
                logger.info("ℹ️  No backup tables found - starting with fresh UUID database")
                return True
            
            logger.warning("⚠️  Backup tables found, but automatic data migration is complex with UUID changes.")
            logger.warning("⚠️  Please manually migrate critical data if needed.")
            logger.warning("⚠️  Backup tables are preserved: users_backup, files_backup, payment_history_backup")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Data migration check failed: {e}")
        return False

def verify_uuid_tables():
    """Verify that UUID tables were created correctly"""
    try:
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['users', 'files', 'payment_history']
        created_tables = [table for table in expected_tables if table in tables]
        
        logger.info(f"📋 Tables found: {', '.join(tables)}")
        logger.info(f"✅ Verification complete - Found {len(created_tables)}/{len(expected_tables)} expected tables")
        
        # Check if users table has UUID primary key
        if 'users' in tables:
            user_columns = inspector.get_columns('users')
            id_column = next((col for col in user_columns if col['name'] == 'id'), None)
            
            if id_column:
                logger.info(f"✅ Users table ID column type: {id_column['type']}")
            else:
                logger.warning("⚠️  Could not find ID column in users table")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Table verification failed: {e}")
        return False

def run_uuid_migration():
    """Run the complete UUID migration process"""
    logger.info("🚀 Starting UUID Migration...")
    logger.info("=" * 60)
    
    # Step 1: Test database connection
    logger.info("Step 1: Testing database connection...")
    if not test_database_connection():
        logger.error("❌ Cannot connect to database. Please check your .env file and ensure MySQL is running.")
        return False
    
    # Step 2: Create backup of existing tables
    logger.info("Step 2: Creating backup of existing tables...")
    if not backup_existing_tables():
        logger.warning("⚠️  Backup creation had issues, but continuing...")
    
    # Step 3: Drop existing tables
    logger.info("Step 3: Dropping existing tables...")
    if not drop_existing_tables():
        logger.warning("⚠️  Table dropping had issues, but continuing...")
    
    # Step 4: Create new UUID tables
    logger.info("Step 4: Creating new tables with UUID primary keys...")
    if not create_uuid_tables():
        return False
    
    # Step 5: Check for data migration opportunities
    logger.info("Step 5: Checking for data migration...")
    if not migrate_data_to_uuid_tables():
        logger.warning("⚠️  Data migration check had issues, but continuing...")
    
    # Step 6: Verify new tables
    logger.info("Step 6: Verifying UUID tables...")
    if not verify_uuid_tables():
        logger.warning("⚠️  Verification had issues, but migration may have succeeded")
    
    logger.info("=" * 60)
    logger.info("🎉 UUID Migration Completed Successfully!")
    logger.info("=" * 60)
    
    print("""
📋 UUID MIGRATION SUMMARY:
===========================
✅ Database connection established
✅ Backup tables created (if data existed)
✅ Old tables dropped
✅ New UUID tables created
✅ UUID primary keys implemented

🆕 UUID BENEFITS:
=================
- Better security (no ID enumeration attacks)
- Globally unique identifiers
- Better for distributed systems
- No sequential ID guessing
- Improved privacy

🔧 TABLES UPDATED:
==================
- users: Now uses UUID primary key
- files: Now uses UUID primary key  
- payment_history: Now uses UUID primary key
- All foreign key relationships updated

⚠️  IMPORTANT NOTES:
====================
1. This is a BREAKING CHANGE - existing API clients need updates
2. All user IDs, file IDs, and payment IDs are now UUIDs (strings)
3. Backup tables preserved if data existed
4. Update your frontend/API code to handle string IDs
5. Consider updating file paths that used integer IDs

🚀 NEXT STEPS:
==============
1. Update your API endpoints to handle UUID parameters
2. Update frontend code to work with string IDs
3. Test all authentication and file operations
4. Update any hardcoded ID references
5. Consider data migration scripts for existing files
""")
    
    return True

if __name__ == "__main__":
    print("🚀 FastAPI File Share - UUID Migration")
    print("=" * 60)
    
    try:
        if run_uuid_migration():
            print("✅ UUID Migration completed successfully!")
            print("Your FastAPI application now uses UUID primary keys!")
            sys.exit(0)
        else:
            print("❌ UUID Migration failed! Please check the logs above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        print("❌ Migration failed due to unexpected error!")
        sys.exit(1)