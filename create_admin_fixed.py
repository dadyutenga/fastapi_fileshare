"""
Fixed script to create a new admin user
This script fixes the admin_id null issue and email validation
"""
import os
import sys
import logging
from pathlib import Path
import getpass

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from app.db.base import SessionLocal
    from app.db.admin_models import Admin, AdminRole
    from app.schemas.admin import AdminCreate
    from app.core.security import get_password_hash
    from sqlalchemy import or_
    import uuid
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

def get_admin_input():
    """Get admin details from user input"""
    print("🔧 Create New Admin Account")
    print("=" * 30)
    
    # Get admin details
    admin_username = input("Enter admin username: ").strip()
    if not admin_username:
        print("❌ Username cannot be empty!")
        return None
    
    # Get email with validation
    while True:
        admin_email = input("Enter admin email (use a real email format like admin@gmail.com): ").strip()
        if not admin_email:
            print("❌ Email cannot be empty!")
            continue
        if "@" not in admin_email or "." not in admin_email.split("@")[1]:
            print("❌ Please enter a valid email address!")
            continue
        if admin_email.endswith(".local"):
            print("❌ .local domain is not allowed. Use a real domain like .com, .org, etc.")
            continue
        break
    
    full_name = input("Enter full name: ").strip()
    if not full_name:
        print("❌ Full name cannot be empty!")
        return None
    
    # Get password
    while True:
        password = getpass.getpass("Enter password: ")
        if len(password) < 6:
            print("❌ Password must be at least 6 characters long!")
            continue
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("❌ Passwords do not match!")
            continue
        break
    
    # Get role
    print("\nAvailable roles:")
    print("1. SUPER_ADMIN (all permissions)")
    print("2. ADMIN (most permissions)")
    print("3. MODERATOR (basic permissions)")
    
    while True:
        role_choice = input("Enter role choice (1-3): ").strip()
        if role_choice == "1":
            role = AdminRole.SUPER_ADMIN
            break
        elif role_choice == "2":
            role = AdminRole.ADMIN
            break
        elif role_choice == "3":
            role = AdminRole.MODERATOR
            break
        else:
            print("❌ Please enter 1, 2, or 3!")
    
    return {
        "admin_username": admin_username,
        "admin_email": admin_email,
        "full_name": full_name,
        "password": password,
        "role": role
    }

def check_existing_admin(db, username, email):
    """Check if admin with username or email already exists"""
    existing_admin = db.query(Admin).filter(
        or_(
            Admin.admin_username == username,
            Admin.admin_email == email
        )
    ).first()
    return existing_admin

def create_admin_direct(admin_data):
    """Create admin directly without using the service to avoid logging issues"""
    try:
        db = SessionLocal()
        
        # Check if admin already exists
        existing = check_existing_admin(db, admin_data["admin_username"], admin_data["admin_email"])
        if existing:
            logger.error(f"❌ Admin with username '{admin_data['admin_username']}' or email '{admin_data['admin_email']}' already exists!")
            return False
        
        # Create admin directly
        hashed_password = get_password_hash(admin_data["password"])
        
        admin = Admin(
            id=str(uuid.uuid4()),
            admin_username=admin_data["admin_username"],
            admin_email=admin_data["admin_email"],
            full_name=admin_data["full_name"],
            hashed_password=hashed_password,
            role=admin_data["role"],
            is_super_admin=(admin_data["role"] == AdminRole.SUPER_ADMIN)
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        logger.info("✅ Admin created successfully!")
        logger.info("=" * 40)
        logger.info(f"Username: {admin.admin_username}")
        logger.info(f"Email: {admin.admin_email}")
        logger.info(f"Full Name: {admin.full_name}")
        logger.info(f"Role: {admin.role.value}")
        logger.info(f"Super Admin: {admin.is_super_admin}")
        logger.info("=" * 40)
        logger.info("You can now login at: http://localhost:8001/admin/login")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating admin: {e}")
        if 'db' in locals():
            db.rollback()
        return False
    finally:
        if 'db' in locals():
            db.close()

def create_default_super_admin():
    """Create a default super admin with valid email"""
    admin_data = {
        "admin_username": "superadmin",
        "admin_email": "admin@example.com",  # Use a valid email format
        "full_name": "Super Administrator",
        "password": "admin123",
        "role": AdminRole.SUPER_ADMIN
    }
    
    logger.info("🔧 Creating default super admin...")
    return create_admin_direct(admin_data)

def list_existing_admins():
    """List all existing admins"""
    try:
        db = SessionLocal()
        admins = db.query(Admin).all()
        
        if not admins:
            logger.info("📋 No admins found in the database")
            return
        
        logger.info("📋 Existing admins:")
        logger.info("-" * 80)
        for admin in admins:
            status = "Active" if admin.is_active else "Inactive"
            super_admin = "Yes" if admin.is_super_admin else "No"
            logger.info(f"Username: {admin.admin_username:<15} | Email: {admin.admin_email:<25} | Role: {admin.role.value:<12} | Super: {super_admin:<3} | Status: {status}")
        logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"❌ Error listing admins: {e}")
    finally:
        if 'db' in locals():
            db.close()

def main():
    """Main function"""
    logger.info("🚀 Admin Management Script (Fixed)")
    logger.info("=" * 50)
    
    # List existing admins first
    list_existing_admins()
    
    print("\nOptions:")
    print("1. Create a new admin (interactive)")
    print("2. Create default super admin (admin@example.com)")
    print("3. Exit")
    
    while True:
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            admin_data = get_admin_input()
            if admin_data:
                success = create_admin_direct(admin_data)
                if success:
                    break
        
        elif choice == "2":
            success = create_default_super_admin()
            if success:
                break
                
        elif choice == "3":
            logger.info("👋 Goodbye!")
            break
            
        else:
            print("❌ Please enter 1, 2, or 3!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        sys.exit(1)