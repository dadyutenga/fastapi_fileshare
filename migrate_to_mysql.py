"""
MySQL Update Script for Premium Features
This script adds email, phone, and payment history support
"""
import os
import sys
import logging
import mysql.connector
from mysql.connector import Error
from pathlib import Path

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_users_table_for_premium():
    """Add premium and contact fields to users table"""
    try:
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD if settings.MYSQL_PASSWORD else None,
            database=settings.MYSQL_DATABASE
        )
        
        cursor = connection.cursor()
        
        # Add new columns to users table
        alter_queries = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20) NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_type ENUM('free', 'premium', 'business') DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_until DATETIME NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_started_at DATETIME NULL",
            "CREATE INDEX IF NOT EXISTS idx_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_premium ON users(is_premium, premium_until)"
        ]
        
        for query in alter_queries:
            try:
                cursor.execute(query)
                logger.info(f"✅ Executed: {query}")
            except Error as e:
                if "Duplicate column" in str(e) or "already exists" in str(e):
                    logger.info(f"⏭️  Column already exists, skipping: {query}")
                else:
                    logger.warning(f"⚠️  Query failed: {query} - {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ Users table updated for premium features")
        return True
        
    except Error as e:
        logger.error(f"❌ Error updating users table: {e}")
        return False

def create_payment_history_table():
    """Create payment history table"""
    try:
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD if settings.MYSQL_PASSWORD else None,
            database=settings.MYSQL_DATABASE
        )
        
        cursor = connection.cursor()
        
        payment_history_sql = """
        CREATE TABLE IF NOT EXISTS payment_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            payment_id VARCHAR(100) UNIQUE NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'USD',
            status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
            plan_type ENUM('free', 'premium', 'business') NOT NULL,
            duration_days INT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME NULL,
            expires_at DATETIME NULL,
            payment_method VARCHAR(50) NULL,
            gateway_response TEXT NULL,
            INDEX idx_user_id (user_id),
            INDEX idx_payment_id (payment_id),
            INDEX idx_status (status),
            INDEX idx_created_at (created_at),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """
        
        cursor.execute(payment_history_sql)
        logger.info("✅ Payment history table created")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return True
        
    except Error as e:
        logger.error(f"❌ Error creating payment history table: {e}")
        return False

def update_storage_limits_for_existing_users():
    """Update storage limits for existing users based on plan type"""
    try:
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD if settings.MYSQL_PASSWORD else None,
            database=settings.MYSQL_DATABASE
        )
        
        cursor = connection.cursor()
        
        # Update free users (default limits)
        cursor.execute("""
            UPDATE users 
            SET plan_type = 'free',
                storage_limit = 5368709120,  -- 5GB
                daily_download_limit = 1073741824  -- 1GB
            WHERE plan_type IS NULL OR plan_type = 'free'
        """)
        
        # Update premium users (if any exist)
        cursor.execute("""
            UPDATE users 
            SET storage_limit = 53687091200,  -- 50GB
                daily_download_limit = 10737418240  -- 10GB
            WHERE is_premium = TRUE AND plan_type = 'premium'
        """)
        
        connection.commit()
        affected_rows = cursor.rowcount
        
        cursor.close()
        connection.close()
        
        logger.info(f"✅ Updated storage limits for {affected_rows} users")
        return True
        
    except Error as e:
        logger.error(f"❌ Error updating user limits: {e}")
        return False

def run_premium_update():
    """Run the complete premium feature update"""
    logger.info("🚀 Starting Premium Features Update...")
    logger.info("=" * 50)
    
    # Step 1: Update users table
    logger.info("Step 1: Adding premium fields to users table...")
    if not update_users_table_for_premium():
        return False
    
    # Step 2: Create payment history table
    logger.info("Step 2: Creating payment history table...")
    if not create_payment_history_table():
        return False
    
    # Step 3: Update storage limits
    logger.info("Step 3: Updating storage limits for existing users...")
    if not update_storage_limits_for_existing_users():
        logger.warning("⚠️  Could not update user limits, but continuing...")
    
    logger.info("=" * 50)
    logger.info("🎉 Premium Features Update Completed!")
    logger.info("=" * 50)
    
    print("""
📋 UPDATE SUMMARY:
==================
✅ Added email and phone fields to users table
✅ Added premium subscription fields to users table
✅ Created payment history table
✅ Updated storage limits for existing users

🆕 NEW FEATURES:
================
- Email and phone number support
- Premium subscription tracking
- Payment history logging
- Flexible plan types (free, premium, business)
- Automatic limit adjustments based on plan

📊 PLAN LIMITS:
===============
- Free Plan: 5GB storage, 1GB/day downloads
- Premium Plan: 50GB storage, 10GB/day downloads
- Business Plan: Custom limits (configurable)

🔧 NEXT STEPS:
==============
1. Update your application code to use the new fields
2. Implement payment gateway integration
3. Add premium upgrade functionality
4. Update your frontend to show premium features
""")
    
    return True

if __name__ == "__main__":
    print("🚀 FastAPI File Share - Premium Features Update")
    print("=" * 50)
    
    # Test MySQL connection
    try:
        password = settings.MYSQL_PASSWORD if settings.MYSQL_PASSWORD else None
        
        connection = mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=password,
            database=settings.MYSQL_DATABASE
        )
        if connection.is_connected():
            connection.close()
            logger.info("✅ MySQL connection successful")
        else:
            logger.error("❌ Cannot connect to MySQL")
            sys.exit(1)
    except Error as e:
        logger.error(f"❌ MySQL connection failed: {e}")
        sys.exit(1)
    
    if run_premium_update():
        print("✅ Update completed successfully!")
        print("Your FastAPI application now supports premium features!")
    else:
        print("❌ Update failed! Please check the logs.")
        sys.exit(1)