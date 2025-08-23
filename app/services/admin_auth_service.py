"""
Admin Authentication and Authorization Service
Completely separate from regular user authentication
"""
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from fastapi import HTTPException, status

from app.db.admin_models import Admin, SystemSettings, AdminRole, AdminPermission
from app.db.models import User
from app.schemas.admin import AdminCreate, AdminUpdate, AdminDashboardStats
from app.core.security import get_password_hash, verify_password, create_access_token

class AdminAuthService:
    """Service for admin authentication and authorization"""
    
    @staticmethod
    def create_admin(db: Session, admin_data: AdminCreate, creator_id: Optional[str] = None) -> Admin:
        """Create a new admin (only super admin can create other admins)"""
        # Check if username or email already exists
        existing_admin = db.query(Admin).filter(
            or_(
                Admin.admin_username == admin_data.admin_username,
                Admin.admin_email == admin_data.admin_email
            )
        ).first()
        
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin username or email already exists"
            )
        
        # Hash password
        hashed_password = get_password_hash(admin_data.password)
        
        # Create admin
        admin = Admin(
            admin_username=admin_data.admin_username,
            admin_email=admin_data.admin_email,
            full_name=admin_data.full_name,
            role=admin_data.role,
            hashed_password=hashed_password,
            created_by=creator_id
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        return admin
    
    @staticmethod
    def authenticate_admin(db: Session, username: str, password: str, ip_address: str = None) -> Optional[Admin]:
        """Authenticate admin login"""
        admin = db.query(Admin).filter(Admin.admin_username == username).first()
        
        if not admin:
            return None
        
        # Check if account is locked
        if admin.is_account_locked():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked until {admin.locked_until}"
            )
        
        # Check if account is active
        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is disabled"
            )
        
        # Verify password
        if not verify_password(password, admin.hashed_password):
            admin.increment_failed_attempts()
            db.commit()
            return None
        
        # Successful login
        admin.reset_failed_attempts()
        admin.last_login = datetime.utcnow()
        admin.update_last_activity()
        db.commit()
        
        return admin
    
    @staticmethod
    def check_permission(admin: Admin, permission: AdminPermission) -> bool:
        """Check if admin has specific permission"""
        return admin.has_permission(permission)
    
    @staticmethod
    def require_permission(admin: Admin, permission: AdminPermission):
        """Require admin to have specific permission, raise exception if not"""
        if not admin.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission.value}"
            )
    
    @staticmethod
    def get_dashboard_stats(db: Session) -> AdminDashboardStats:
        """Get admin dashboard statistics"""
        # User statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        inactive_users = total_users - active_users
        premium_users = db.query(User).filter(User.is_premium == True).count()
        
        # Today's statistics
        today = datetime.utcnow().date()
        users_today = db.query(User).filter(User.created_at >= today).count()
        
        return AdminDashboardStats(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            premium_users=premium_users,
            total_files=0,  # No file stats for privacy
            total_storage_used=0,  # No storage stats for privacy  
            total_downloads=0,  # No download stats for privacy
            files_uploaded_today=0,  # No file stats for privacy
            new_users_today=users_today,
            top_file_types=[],  # No file type stats for privacy
            recent_activity=[]  # No activity logs for privacy
        )

class AdminUserManagementService:
    """Service for admin user management operations"""
    
    @staticmethod
    def get_all_users(
        db: Session,
        admin: Admin,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        plan_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all users with filtering"""
        AdminAuthService.require_permission(admin, AdminPermission.VIEW_USERS)
        
        query = db.query(User)
        
        if search:
            query = query.filter(
                or_(
                    User.username.contains(search),
                    User.email.contains(search)
                )
            )
        
        if plan_filter and plan_filter != "all":
            if plan_filter == "premium":
                query = query.filter(User.is_premium == True)
            elif plan_filter == "free":
                query = query.filter(User.is_premium == False)
        
        total = query.count()
        users = query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()
        
        return {
            "users": users,
            "total": total,
            "page": offset // limit + 1,
            "pages": (total + limit - 1) // limit
        }
    
    @staticmethod
    def suspend_user(db: Session, admin: Admin, user_id: str, reason: str = "") -> User:
        """Suspend/unsuspend user"""
        AdminAuthService.require_permission(admin, AdminPermission.SUSPEND_USERS)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_active = not user.is_active
        db.commit()
        
        return user
    
    @staticmethod
    def delete_user_and_files(db: Session, admin: Admin, user_id: str) -> Dict[str, Any]:
        """Delete user (files are not accessible to admin for privacy)"""
        AdminAuthService.require_permission(admin, AdminPermission.DELETE_USERS)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Note: Files are not deleted by admin for privacy reasons
        # User data deletion only removes user account
        username = user.username
        db.delete(user)
        db.commit()
        
        return {
            "deleted_user": username,
            "message": f"Successfully deleted user {username}"
        }

# Global service instances
admin_auth_service = AdminAuthService()
admin_user_service = AdminUserManagementService()