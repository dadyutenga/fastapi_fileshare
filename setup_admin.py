"""
Setup script to create the first super admin
Run this once to create the initial super admin account
"""
import sys
import os
from sqlalchemy.orm import Session

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.base import SessionLocal
from app.db.admin_models import Admin, AdminRole
from app.schemas.admin import AdminCreate
from app.services.admin_auth_service import AdminAuthService

def create_super_admin():
    """Create the first super admin"""
    db: Session = SessionLocal()
    
    try:
        # Check if super admin already exists
        existing_super_admin = db.query(Admin).filter(Admin.is_super_admin == True).first()
        if existing_super_admin:
            print("Super admin already exists!")
            print(f"Username: {existing_super_admin.admin_username}")
            print(f"Email: {existing_super_admin.admin_email}")
            return
        
        # Get admin details
        print("Creating Super Admin Account")
        print("-" * 30)
        
        admin_username = input("Enter admin username: ").strip()
        admin_email = input("Enter admin email: ").strip()
        full_name = input("Enter full name: ").strip()
        password = input("Enter password: ").strip()
        
        if not all([admin_username, admin_email, full_name, password]):
            print("All fields are required!")
            return
        
        # Create admin
        admin_data = AdminCreate(
            admin_username=admin_username,
            admin_email=admin_email,
            full_name=full_name,
            password=password,
            role=AdminRole.SUPER_ADMIN
        )
        
        admin = AdminAuthService.create_admin(db, admin_data)
        admin.is_super_admin = True
        db.commit()
        
        print("\n" + "=" * 40)
        print("Super Admin Created Successfully!")
        print("=" * 40)
        print(f"Username: {admin.admin_username}")
        print(f"Email: {admin.admin_email}")
        print(f"Full Name: {admin.full_name}")
        print(f"Role: {admin.role.value}")
        print("\nYou can now login at: http://localhost:8000/admin/login")
        
    except Exception as e:
        print(f"Error creating super admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_super_admin()