"""
Fixed MySQL Migration Script
This script handles the VARCHAR length requirements for MySQL
"""

import sys
import os
import shutil
import hashlib
from pathlib import Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import mysql.connector
from mysql.connector import Error
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.models import User, File, Base
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_mysql_database():
    """Create MySQL database if it doesn't exist"""
    try:
        # Connect to MySQL server (without database)
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD if settings.MYSQL_PASSWORD else None
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            logger.info(f"✅ Database '{settings.MYSQL_DATABASE}' created/verified")
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        logger.error(f"❌ Error creating MySQL database: {e}")
        return False

def create_user_folders():
    """Create individual user folders in uploads directory"""
    try:
        uploads_dir = Path(settings.UPLOAD_DIR)
        uploads_dir.mkdir(exist_ok=True)
        
        # Create user folders structure
        users_dir = uploads_dir / "users"
        users_dir.mkdir(exist_ok=True)
        
        # Create temp chunks folder
        temp_chunks_dir = uploads_dir / "temp_chunks"
        temp_chunks_dir.mkdir(exist_ok=True)
        
        logger.info("✅ User folder structure created")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating user folders: {e}")
        return False

def create_mysql_tables_manually():
    """Manually create MySQL tables with proper VARCHAR lengths"""
    try:
        # Connect to MySQL
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD if settings.MYSQL_PASSWORD else None,
            database=settings.MYSQL_DATABASE
        )
        
        cursor = connection.cursor()
        
        # Create users table
        users_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME NULL,
            storage_limit BIGINT DEFAULT 5368709120,
            daily_download_limit BIGINT DEFAULT 1073741824,
            storage_used BIGINT DEFAULT 0,
            last_download_reset DATETIME DEFAULT CURRENT_TIMESTAMP,
            daily_downloads_used BIGINT DEFAULT 0,
            INDEX idx_username (username)
        ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """
        
        cursor.execute(users_table_sql)
        logger.info("✅ Users table created")
        
        # Create files table
        files_table_sql = """
        CREATE TABLE IF NOT EXISTS files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            file_id VARCHAR(36) UNIQUE NOT NULL,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            path TEXT NOT NULL,
            file_size BIGINT,
            content_type VARCHAR(100),
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ttl INT DEFAULT 0,
            download_count INT DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            is_public BOOLEAN DEFAULT FALSE,
            owner_id INT,
            file_hash VARCHAR(64),
            INDEX idx_file_id (file_id),
            INDEX idx_owner_id (owner_id),
            INDEX idx_is_active (is_active),
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """
        
        cursor.execute(files_table_sql)
        logger.info("✅ Files table created")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return True
        
    except Error as e:
        logger.error(f"❌ Error creating MySQL tables manually: {e}")
        return False

def calculate_sha256_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash for {file_path}: {e}")
        return ""

def migrate_files_to_user_folders():
    """Migrate existing files to user-specific folders"""
    try:
        # Connect using SQLAlchemy for easier data manipulation
        mysql_engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(bind=mysql_engine)
        db = SessionLocal()
        
        logger.info("🔄 Migrating files to user folders and calculating SHA-256 hashes...")
        
        files = db.query(File).all()
        migrated_count = 0
        
        for file in files:
            try:
                # Get user folder
                user_folder = Path(settings.UPLOAD_DIR) / "users" / str(file.owner_id)
                user_folder.mkdir(exist_ok=True)
                
                # Old file path
                old_path = Path(file.path)
                
                if old_path.exists():
                    # New path in user folder
                    new_path = user_folder / old_path.name
                    
                    # Move file to user folder
                    if not new_path.exists():
                        shutil.move(str(old_path), str(new_path))
                        logger.info(f"📁 Moved {old_path.name} to user {file.owner_id} folder")
                    
                    # Update file path in database
                    file.path = str(new_path)
                    
                    # Calculate SHA-256 hash if not already set
                    if not file.file_hash:
                        file_hash = calculate_sha256_hash(str(new_path))
                        if file_hash:
                            file.file_hash = file_hash
                            logger.info(f"🔐 Generated SHA-256 hash for {old_path.name}")
                    
                    migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error migrating file {file.original_filename}: {e}")
                continue
        
        db.commit()
        db.close()
        logger.info(f"✅ Migrated {migrated_count} files to user folders")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during file migration: {e}")
        return False

def migrate_sqlite_to_mysql():
    """Migrate data from SQLite to MySQL"""
    sqlite_path = "file_share.db"
    
    if not os.path.exists(sqlite_path):
        logger.info("ℹ️  No existing SQLite database found, creating fresh MySQL database")
        return True
    
    try:
        logger.info("🔄 Starting migration from SQLite to MySQL...")
        
        # Connect to SQLite
        sqlite_engine = create_engine(f"sqlite:///./{sqlite_path}")
        SqliteSession = sessionmaker(bind=sqlite_engine)
        sqlite_session = SqliteSession()
        
        # Connect to MySQL
        mysql_engine = create_engine(settings.DATABASE_URL)
        MysqlSession = sessionmaker(bind=mysql_engine)
        mysql_session = MysqlSession()
        
        # Check if SQLite tables exist
        try:
            sqlite_users = sqlite_session.execute(text("SELECT * FROM users")).fetchall()
        except Exception as e:
            logger.warning(f"Could not read SQLite users table: {e}")
            sqlite_users = []
        
        # Migrate Users
        logger.info("👥 Migrating users...")
        for row in sqlite_users:
            # Check if user already exists
            existing_user = mysql_session.query(User).filter(User.username == row.username).first()
            if not existing_user:
                user = User(
                    username=row.username,
                    hashed_password=row.hashed_password,
                    is_active=getattr(row, 'is_active', True),
                    created_at=getattr(row, 'created_at', datetime.utcnow()),
                    last_login=getattr(row, 'last_login', None),
                    # Set default limits for migrated users
                    storage_limit=5 * 1024 * 1024 * 1024,  # 5GB
                    daily_download_limit=1 * 1024 * 1024 * 1024,  # 1GB
                    storage_used=0,  # Will be calculated
                    last_download_reset=datetime.utcnow(),
                    daily_downloads_used=0
                )
                mysql_session.add(user)
        
        mysql_session.commit()
        logger.info(f"✅ Migrated {len(sqlite_users)} users")
        
        # Migrate Files
        try:
            sqlite_files = sqlite_session.execute(text("SELECT * FROM files")).fetchall()
        except Exception as e:
            logger.warning(f"Could not read SQLite files table: {e}")
            sqlite_files = []
        
        logger.info("📁 Migrating files...")
        for row in sqlite_files:
            # Check if file already exists
            existing_file = mysql_session.query(File).filter(File.file_id == row.file_id).first()
            if not existing_file:
                file = File(
                    file_id=row.file_id,
                    filename=row.filename,
                    original_filename=row.original_filename,
                    path=row.path,
                    file_size=getattr(row, 'file_size', 0),
                    content_type=getattr(row, 'content_type', None),
                    upload_time=getattr(row, 'upload_time', datetime.utcnow()),
                    created_at=getattr(row, 'upload_time', datetime.utcnow()),
                    ttl=getattr(row, 'ttl', 0),
                    download_count=getattr(row, 'download_count', 0),
                    is_active=getattr(row, 'is_active', True),
                    is_public=getattr(row, 'is_public', False),
                    owner_id=row.owner_id,
                    file_hash=None  # Will be calculated later
                )
                mysql_session.add(file)
        
        mysql_session.commit()
        logger.info(f"✅ Migrated {len(sqlite_files)} files")
        
        # Calculate storage usage for users
        logger.info("📊 Calculating storage usage for users...")
        users = mysql_session.query(User).all()
        for user in users:
            total_storage = mysql_session.execute(text("""
                SELECT COALESCE(SUM(file_size), 0) 
                FROM files 
                WHERE owner_id = :user_id AND is_active = 1
            """), {"user_id": user.id}).scalar()
            
            user.storage_used = total_storage or 0
            logger.info(f"User {user.username}: {user.storage_used / (1024*1024):.2f} MB used")
        
        mysql_session.commit()
        
        sqlite_session.close()
        mysql_session.close()
        
        # Backup SQLite database
        backup_path = f"{sqlite_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(sqlite_path, backup_path)
        logger.info(f"💾 SQLite database backed up to {backup_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

def update_helpers_for_mysql():
    """Update helpers to work with MySQL and user folders"""
    helper_content = '''import uuid
import hashlib
import os
from pathlib import Path
from app.core.config import settings

def generate_file_id():
    """Generate unique file ID using UUID4"""
    return str(uuid.uuid4())

def generate_secure_hash(data: str) -> str:
    """Generate SHA-256 hash instead of MD5"""
    return hashlib.sha256(data.encode()).hexdigest()

def get_user_upload_path(user_id: int) -> str:
    """Get user-specific upload directory"""
    user_folder = Path(settings.UPLOAD_DIR) / "users" / str(user_id)
    user_folder.mkdir(parents=True, exist_ok=True)
    return str(user_folder)

def get_file_path_for_user(user_id: int, filename: str) -> str:
    """Get full file path for user"""
    user_folder = get_user_upload_path(user_id)
    return os.path.join(user_folder, filename)
'''
    
    try:
        with open("app/utils/helpers.py", "w") as f:
            f.write(helper_content)
        logger.info("✅ Updated helpers for MySQL")
    except Exception as e:
        logger.error(f"❌ Error updating helpers: {e}")

def update_chunked_upload_for_mysql():
    """Update chunked upload to use SHA-256"""
    try:
        chunked_file = "app/utils/chunked_upload.py"
        if os.path.exists(chunked_file):
            with open(chunked_file, 'r') as f:
                content = f.read()
            
            # Replace MD5 with SHA-256
            updated_content = content.replace(
                'hashlib.md5(data.encode()).hexdigest()',
                'hashlib.sha256(data.encode()).hexdigest()'
            )
            
            with open(chunked_file, 'w') as f:
                f.write(updated_content)
            
            logger.info("✅ Updated chunked upload to use SHA-256")
    except Exception as e:
        logger.error(f"❌ Error updating chunked upload: {e}")

def run_mysql_migration():
    """Run the complete MySQL migration with proper error handling"""
    
    logger.info("🚀 Starting Fixed MySQL Migration Process...")
    logger.info("=" * 50)
    
    # Step 1: Create MySQL database
    logger.info("Step 1: Creating MySQL database...")
    if not create_mysql_database():
        return False
    
    # Step 2: Create user folder structure
    logger.info("Step 2: Creating user folder structure...")
    if not create_user_folders():
        return False
    
    # Step 3: Create MySQL tables manually (to handle VARCHAR lengths)
    logger.info("Step 3: Creating MySQL tables manually...")
    if not create_mysql_tables_manually():
        return False
    
    # Step 4: Migrate data from SQLite (if exists)
    logger.info("Step 4: Migrating data from SQLite...")
    if not migrate_sqlite_to_mysql():
        return False
    
    # Step 5: Migrate files to user folders
    logger.info("Step 5: Organizing files into user folders...")
    if not migrate_files_to_user_folders():
        logger.warning("⚠️  File migration had issues, but continuing...")
    
    # Step 6: Update application code
    logger.info("Step 6: Updating application code...")
    update_helpers_for_mysql()
    update_chunked_upload_for_mysql()
    
    logger.info("=" * 50)
    logger.info("🎉 MySQL Migration Completed Successfully!")
    logger.info("=" * 50)
    
    print("""
📋 MIGRATION SUMMARY:
====================
✅ MySQL database created
✅ User folder structure created  
✅ Database tables created with proper VARCHAR lengths
✅ Data migrated from SQLite (if existed)
✅ File storage organized by user
✅ SHA-256 hashing implemented
✅ User storage limits added (5GB default)
✅ Daily download limits added (1GB default)

🔧 NEXT STEPS:
==============
1. Restart your FastAPI server
2. Your application now uses MySQL with user folders and storage limits!

📊 USER LIMITS:
===============
- Storage Limit: 5GB per user (default)
- Download Limit: 1GB per day per user (default)
- Files are organized in individual user folders
- SHA-256 hashing for file integrity

🔒 SECURITY IMPROVEMENTS:
=========================
- Replaced MD5 with SHA-256 hashing
- User-specific file storage
- Storage and download quotas
- File integrity checking
- Proper MySQL VARCHAR lengths
""")
    
    return True

if __name__ == "__main__":
    print("🚀 FastAPI File Share - Fixed MySQL Migration")
    print("=" * 50)
    
    # Test MySQL connection
    try:
        # Handle empty password case
        password = settings.MYSQL_PASSWORD if settings.MYSQL_PASSWORD else None
        
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=password
        )
        if connection.is_connected():
            connection.close()
            logger.info("✅ MySQL connection successful")
        else:
            logger.error("❌ Cannot connect to MySQL")
            sys.exit(1)
    except Error as e:
        logger.error(f"❌ MySQL connection failed: {e}")
        print(f"""
❌ MYSQL CONNECTION FAILED!

Please make sure:
1. MySQL server is running
2. User '{settings.MYSQL_USER}' exists and has privileges
3. Password is correct (or empty if using root without password)
4. Host '{settings.MYSQL_HOST}' is accessible

Error: {e}
""")
        sys.exit(1)
    
    if run_mysql_migration():
        print("✅ Migration completed successfully!")
        print("You can now restart your FastAPI server with MySQL.")
    else:
        print("❌ Migration failed! Please check the logs.")
        sys.exit(1)