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

from app.db.admin_models import Admin, AdminLog, SystemSettings, AdminRole, AdminPermission
from app.db.models import User, File as FileModel
from app.schemas.admin import AdminCreate, AdminUpdate, AdminLogEntry, AdminDashboardStats
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
        
        # Log the action
        AdminAuthService.log_admin_action(
            db, creator_id, "CREATE_ADMIN", "ADMIN", admin.id,
            f"Created admin: {admin.admin_username} with role: {admin.role.value}"
        )
        
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
            
            AdminAuthService.log_admin_action(
                db, admin.id, "FAILED_LOGIN", "ADMIN", admin.id,
                f"Failed login attempt from IP: {ip_address}"
            )
            
            return None
        
        # Successful login
        admin.reset_failed_attempts()
        admin.last_login = datetime.utcnow()
        admin.update_last_activity()
        db.commit()
        
        AdminAuthService.log_admin_action(
            db, admin.id, "LOGIN", "ADMIN", admin.id,
            f"Successful login from IP: {ip_address}"
        )
        
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
    def log_admin_action(
        db: Session, 
        admin_id: str, 
        action: str, 
        target_type: str = None,
        target_id: str = None, 
        details: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Log admin action"""
        log_entry = AdminLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(log_entry)
        db.commit()
    
    @staticmethod
    def get_admin_logs(
        db: Session, 
        admin_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AdminLogEntry]:
        """Get admin activity logs"""
        query = db.query(AdminLog).join(Admin)
        
        if admin_id:
            query = query.filter(AdminLog.admin_id == admin_id)
        
        if action:
            query = query.filter(AdminLog.action == action)
        
        logs = query.order_by(desc(AdminLog.timestamp)).offset(offset).limit(limit).all()
        
        return [
            AdminLogEntry(
                id=log.id,
                admin_id=log.admin_id,
                admin_username=log.admin.admin_username,
                action=log.action,
                target_type=log.target_type,
                target_id=log.target_id,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                timestamp=log.timestamp
            )
            for log in logs
        ]
    
    @staticmethod
    def get_dashboard_stats(db: Session) -> AdminDashboardStats:
        """Get admin dashboard statistics"""
        # User statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        inactive_users = total_users - active_users
        premium_users = db.query(User).filter(User.is_premium == True).count()
        
        # File statistics
        total_files = db.query(FileModel).filter(FileModel.is_active == True).count()
        total_storage = db.query(func.sum(FileModel.file_size)).filter(FileModel.is_active == True).scalar() or 0
        total_downloads = db.query(func.sum(FileModel.download_count)).scalar() or 0
        
        # Today's statistics
        today = datetime.utcnow().date()
        files_today = db.query(FileModel).filter(
            and_(
                FileModel.upload_time >= today,
                FileModel.is_active == True
            )
        ).count()
        
        users_today = db.query(User).filter(User.created_at >= today).count()
        
        # Top file types
        file_types = db.query(
            FileModel.content_type,
            func.count(FileModel.id).label('count')
        ).filter(
            FileModel.is_active == True
        ).group_by(FileModel.content_type).order_by(desc('count')).limit(10).all()
        
        top_file_types = [
            {"content_type": ft.content_type, "count": ft.count}
            for ft in file_types
        ]
        
        # Recent activity
        recent_activity = AdminAuthService.get_admin_logs(db, limit=10)
        
        return AdminDashboardStats(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            premium_users=premium_users,
            total_files=total_files,
            total_storage_used=total_storage,
            total_downloads=total_downloads,
            files_uploaded_today=files_today,
            new_users_today=users_today,
            top_file_types=top_file_types,
            recent_activity=recent_activity
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
        
        AdminAuthService.log_admin_action(
            db, admin.id, "VIEW_USERS", "USER", None,
            f"Viewed users list (search: {search}, filter: {plan_filter})"
        )
        
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
        
        action = "UNSUSPEND_USER" if user.is_active else "SUSPEND_USER"
        AdminAuthService.log_admin_action(
            db, admin.id, action, "USER", user_id,
            f"{'Unsuspended' if user.is_active else 'Suspended'} user: {user.username}. Reason: {reason}"
        )
        
        return user
    
    @staticmethod
    def delete_user_and_files(db: Session, admin: Admin, user_id: str) -> Dict[str, Any]:
        """Delete user and all their files (dangerous operation)"""
        AdminAuthService.require_permission(admin, AdminPermission.DELETE_USERS)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user's files
        user_files = db.query(FileModel).filter(FileModel.owner_id == user_id).all()
        file_count = len(user_files)
        
        # Delete files
        for file in user_files:
            db.delete(file)
        
        # Delete user
        username = user.username
        db.delete(user)
        db.commit()
        
        AdminAuthService.log_admin_action(
            db, admin.id, "DELETE_USER", "USER", user_id,
            f"Deleted user: {username} and {file_count} files"
        )
        
        return {
            "deleted_user": username,
            "deleted_files": file_count,
            "message": f"Successfully deleted user {username} and {file_count} files"
        }

# Global service instances
admin_auth_service = AdminAuthService()
admin_user_service = AdminUserManagementService()