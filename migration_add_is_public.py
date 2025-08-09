#!/usr/bin/env python3
"""
Migration script to add is_public field to existing files
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

def main():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if the is_public column exists
        try:
            result = conn.execute(text("PRAGMA table_info(files)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'is_public' not in columns:
                print("Adding is_public column to files table...")
                conn.execute(text("ALTER TABLE files ADD COLUMN is_public BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("✅ Successfully added is_public column")
            else:
                print("✅ is_public column already exists")
                
            # Update existing records to have is_public = False (default)
            result = conn.execute(text("UPDATE files SET is_public = FALSE WHERE is_public IS NULL"))
            affected_rows = result.rowcount
            conn.commit()
            
            if affected_rows > 0:
                print(f"✅ Updated {affected_rows} existing files to private by default")
            else:
                print("✅ All files already have is_public values set")
                
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            return False
    
    print("🎉 Migration completed successfully!")
    return True

if __name__ == "__main__":
    main()
