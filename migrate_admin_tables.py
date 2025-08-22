"""
Migration script to add admin tables to the database
This script adds the new admin authentication system tables
"""
import os
import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from app.db.base import engine, Base, SessionLocal
    from app.core.config import settings
    from app.db.admin_models import Admin, AdminLog, SystemSettings, AdminRole
    from app.schemas.admin import AdminCreate
    from app.services.admin_auth_service import AdminAuthService
    from sqlalchemy import text, inspect
    from sqlalchemy.exc import OperationalError
    import uuid
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

def test_database_connection():
    """Test database connection"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

def check_admin_tables_exist():
    """Check if admin tables already exist"""
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        admin_tables = ['admins', 'admin_logs', 'system_settings']
        existing_admin_tables = [table for table in admin_tables if table in existing_tables]
        
        if existing_admin_tables:
            logger.info(f"📋 Found existing admin tables: {existing_admin_tables}")
            return True
        else:
            logger.info("📋 No admin tables found, will create new ones")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error checking existing tables: {e}")
        return False

def create_admin_tables():
    """Create admin tables"""
    try:
        logger.info("🔨 Creating admin tables...")
        
        # Import admin models to register them with SQLAlchemy
        from app.db import admin_models
        
        # Create only admin tables
        admin_tables = [
            Admin.__table__,
            AdminLog.__table__,
            SystemSettings.__table__
        ]
        
        # Create tables
        for table in admin_tables:
            logger.info(f"Creating table: {table.name}")
            table.create(engine, checkfirst=True)
            
        logger.info("✅ Admin tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating admin tables: {e}")
        return False

def create_initial_super_admin():
    """Create initial super admin if none exists"""
    try:
        db = SessionLocal()
        
        # Check if any super admin exists
        existing_super_admin = db.query(Admin).filter(Admin.is_super_admin == True).first()
        
        if existing_super_admin:
            logger.info(f"✅ Super admin already exists: {existing_super_admin.admin_username}")
            return True
        
        logger.info("🔧 No super admin found, creating default super admin...")
        
        # Create default super admin
        admin_data = AdminCreate(
            admin_username="superadmin",
            admin_email="admin@fileshare.local",
            full_name="Super Administrator",
            password="admin123",  # Change this in production!
            role=AdminRole.SUPER_ADMIN
        )
        
        admin = AdminAuthService.create_admin(db, admin_data)
        admin.is_super_admin = True
        db.commit()
        
        logger.info("✅ Default super admin created successfully!")
        logger.info("📋 Default credentials:")
        logger.info(f"   Username: dady89")
        logger.info(f"   Email: dadynasser@fileshare.local")
        logger.info(f"   Password: admin123")
        logger.info("⚠️  IMPORTANT: Change the default password after first login!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating super admin: {e}")
        if 'db' in locals():
            db.rollback()
        return False
    finally:
        if 'db' in locals():
            db.close()

def add_initial_system_settings():
    """Add initial system settings"""
    try:
        db = SessionLocal()
        
        # Check if settings already exist
        existing_settings = db.query(SystemSettings).first()
        if existing_settings:
            logger.info("✅ System settings already exist")
            return True
        
        logger.info("🔧 Adding initial system settings...")
        
        initial_settings = [
            {
                "setting_key": "max_file_size",
                "setting_value": "524288000",  # 500MB in bytes
                "setting_type": "integer",
                "description": "Maximum file size allowed for upload in bytes"
            },
            {
                "setting_key": "maintenance_mode",
                "setting_value": "false",
                "setting_type": "boolean",
                "description": "Enable maintenance mode to restrict access"
            },
            {
                "setting_key": "allow_registration",
                "setting_value": "true",
                "setting_type": "boolean",
                "description": "Allow new user registration"
            },
            {
                "setting_key": "default_file_ttl",
                "setting_value": "30",
                "setting_type": "integer",
                "description": "Default file time-to-live in days"
            }
        ]
        
        for setting_data in initial_settings:
            setting = SystemSettings(
                id=str(uuid.uuid4()),
                **setting_data
            )
            db.add(setting)
        
        db.commit()
        logger.info("✅ Initial system settings added successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding system settings: {e}")
        if 'db' in locals():
            db.rollback()
        return False
    finally:
        if 'db' in locals():
            db.close()

def verify_admin_system():
    """Verify that the admin system is working"""
    try:
        db = SessionLocal()
        
        # Check admin count
        admin_count = db.query(Admin).count()
        super_admin_count = db.query(Admin).filter(Admin.is_super_admin == True).count()
        settings_count = db.query(SystemSettings).count()
        
        logger.info("🔍 Admin system verification:")
        logger.info(f"   Total admins: {admin_count}")
        logger.info(f"   Super admins: {super_admin_count}")
        logger.info(f"   System settings: {settings_count}")
        
        if super_admin_count > 0:
            logger.info("✅ Admin system verification successful")
            return True
        else:
            logger.error("❌ No super admin found after migration")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error verifying admin system: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

def main():
    """Main migration function"""
    logger.info("🚀 Starting admin tables migration...")
    logger.info("=" * 50)
    
    # Step 1: Test database connection
    logger.info("Step 1: Testing database connection...")
    if not test_database_connection():
        logger.error("❌ Migration failed: Cannot connect to database")
        return False
    
    # Step 2: Check existing admin tables
    logger.info("\nStep 2: Checking existing admin tables...")
    tables_exist = check_admin_tables_exist()
    
    # Step 3: Create admin tables if they don't exist
    if not tables_exist:
        logger.info("\nStep 3: Creating admin tables...")
        if not create_admin_tables():
            logger.error("❌ Migration failed: Could not create admin tables")
            return False
    else:
        logger.info("\nStep 3: Admin tables already exist, skipping creation...")
    
    # Step 4: Create initial super admin
    logger.info("\nStep 4: Creating initial super admin...")
    if not create_initial_super_admin():
        logger.error("❌ Migration failed: Could not create super admin")
        return False
    
    # Step 5: Add initial system settings
    logger.info("\nStep 5: Adding initial system settings...")
    if not add_initial_system_settings():
        logger.error("❌ Migration failed: Could not add system settings")
        return False
    
    # Step 6: Verify admin system
    logger.info("\nStep 6: Verifying admin system...")
    if not verify_admin_system():
        logger.error("❌ Migration failed: Admin system verification failed")
        return False
    
    logger.info("\n" + "=" * 50)
    logger.info("🎉 Admin tables migration completed successfully!")
    logger.info("=" * 50)
    logger.info("\n📋 Next steps:")
    logger.info("1. Start your FastAPI server")
    logger.info("2. Go to http://localhost:8000/admin/login")
    logger.info("3. Login with the default credentials shown above")
    logger.info("4. Change the default password immediately!")
    logger.info("5. Create additional admin accounts as needed")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            logger.info("\n✅ Migration completed successfully!")
            sys.exit(0)
        else:
            logger.error("\n❌ Migration failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error during migration: {e}")
        sys.exit(1)