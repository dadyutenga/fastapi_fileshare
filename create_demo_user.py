#!/usr/bin/env python3
"""
Script to create demo users for testing the FileShare Portal
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal, init_db
from app.db.models import User
from app.core.security import get_password_hash
from datetime import datetime

def create_demo_user():
    """Create demo user for testing"""
    init_db()
    db = SessionLocal()
    
    try:
        # Check if demo user already exists
        existing_user = db.query(User).filter(User.username == "demo").first()
        if existing_user:
            print("✅ Demo user 'demo' already exists")
            return
        
        # Create demo user
        demo_user = User(
            username="demo",
            hashed_password=get_password_hash("demo123"),
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        
        print("🎉 Demo user created successfully!")
        print("Username: demo")
        print("Password: demo123")
        print()
        print("You can now login with these credentials to test the application.")
        
    except Exception as e:
        print(f"❌ Error creating demo user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_demo_user()
