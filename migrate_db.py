#!/usr/bin/env python3
"""
Database migration script to update the schema
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.base import engine, init_db

def migrate_database():
    """Migrate database to new schema"""
    try:
        with engine.connect() as connection:
            # Start transaction
            trans = connection.begin()
            
            try:
                # Add new columns to users table
                try:
                    connection.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                    print("✅ Added is_active column to users table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add is_active column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME"))
                    print("✅ Added created_at column to users table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add created_at column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE users ADD COLUMN last_login DATETIME"))
                    print("✅ Added last_login column to users table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add last_login column: {e}")
                
                # Add new columns to files table
                try:
                    connection.execute(text("ALTER TABLE files ADD COLUMN original_filename TEXT"))
                    print("✅ Added original_filename column to files table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add original_filename column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE files ADD COLUMN file_size INTEGER"))
                    print("✅ Added file_size column to files table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add file_size column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE files ADD COLUMN content_type TEXT"))
                    print("✅ Added content_type column to files table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add content_type column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE files ADD COLUMN download_count INTEGER DEFAULT 0"))
                    print("✅ Added download_count column to files table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add download_count column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE files ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                    print("✅ Added is_active column to files table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add is_active column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE files ADD COLUMN is_public BOOLEAN DEFAULT 0"))
                    print("✅ Added is_public column to files table")
                except Exception as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"⚠️  Could not add is_public column: {e}")
                
                # Update existing data
                connection.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))
                connection.execute(text("UPDATE files SET is_active = 1 WHERE is_active IS NULL"))
                connection.execute(text("UPDATE files SET download_count = 0 WHERE download_count IS NULL"))
                connection.execute(text("UPDATE files SET original_filename = filename WHERE original_filename IS NULL"))
                connection.execute(text("UPDATE files SET is_public = 0 WHERE is_public IS NULL"))
                
                # Commit transaction
                trans.commit()
                print("🎉 Database migration completed successfully!")
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Migration failed: {e}")
                raise
                
    except Exception as e:
        print(f"❌ Database migration error: {e}")

if __name__ == "__main__":
    migrate_database()
