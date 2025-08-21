"""
Admin service for handling administrative operations with UUID support
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import User, File, PaymentHistory, PlanType
from app.utils.helpers import is_valid_uuid
from typing import List, Dict, Any
from fastapi import HTTPException

class AdminService:
    @staticmethod
    def get_system_stats(db: Session) -> Dict[str, Any]:
        """Get overall system statistics with premium user breakdown"""
        total_users = db.query(User).count()
        premium_users = db.query(User).filter(User.is_premium == True).count()
        free_users = total_users - premium_users
        
        total_files = db.query(File).filter(File.is_active == True).count()
        
        # Calculate total storage used across all users
        total_storage_result = db.query(func.sum(User.storage_used)).scalar()
        total_storage_used = total_storage_result or 0
        
        # Calculate total file size
        total_file_size_result = db.query(func.sum(File.file_size)).filter(File.is_active == True).scalar()
        total_file_size = total_file_size_result or 0
        
        # Get users approaching storage limits
        users_near_limit = db.query(User).filter(
            User.storage_used >= (User.storage_limit * 0.9)
        ).count()
        
        return {
            "total_users": total_users,
            "premium_users": premium_users,
            "free_users": free_users,
            "total_files": total_files,
            "total_storage_used": int(total_storage_used),
            "total_file_size": int(total_file_size),
            "users_near_storage_limit": users_near_limit,
            "formatted_storage_used": AdminService._format_bytes(total_storage_used),
            "formatted_file_size": AdminService._format_bytes(total_file_size)
        }
    
    @staticmethod
    def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination"""
        return db.query(User).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> User:
        """Get user by UUID"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    
    @staticmethod
    def get_all_files(db: Session, skip: int = 0, limit: int = 100) -> List[File]:
        """Get all files with pagination"""
        return db.query(File).offset(skip).limit(limit).all()
    
    @staticmethod
    def toggle_user_status(db: Session, user_id: str) -> User:
        """Toggle user active status using UUID"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_active = not user.is_active
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def delete_file(db: Session, file_id: str) -> bool:
        """Delete a file (soft delete) using UUID"""
        if not is_valid_uuid(file_id):
            # Check if it's a file_id (might not be UUID)
            file = db.query(File).filter(File.file_id == file_id).first()
        else:
            # Check if it's the primary key UUID
            file = db.query(File).filter(File.id == file_id).first()
        
        if file:
            file.is_active = False
            
            # Update user storage usage
            if file.owner_id:
                user = db.query(User).filter(User.id == file.owner_id).first()
                if user:
                    user.remove_storage_usage(file.file_size or 0)
            
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_user_files(db: Session, user_id: str) -> List[File]:
        """Get all files for a specific user using UUID"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        return db.query(File).filter(File.owner_id == user_id).all()
    
    @staticmethod
    def get_user_stats(db: Session, user_id: str) -> Dict[str, Any]:
        """Get statistics for a specific user using UUID"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_files = db.query(File).filter(File.owner_id == user_id).all()
        active_files = [f for f in user_files if f.is_active]
        total_files = len(active_files)
        total_size = sum(f.file_size or 0 for f in active_files)
        total_downloads = sum(f.download_count or 0 for f in active_files)
        
        return {
            "user_id": user_id,
            "username": user.username,
            "email": user.email,
            "plan_type": user.plan_type.value if user.plan_type else "free",
            "is_premium": user.is_premium,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "last_login": user.last_login,
            "total_files": total_files,
            "total_size": total_size,
            "total_downloads": total_downloads,
            "storage_used": user.storage_used,
            "storage_limit": user.storage_limit,
            "storage_percentage": user.get_storage_percentage(),
            "daily_downloads_used": user.daily_downloads_used,
            "daily_download_limit": user.daily_download_limit,
            "daily_download_percentage": user.get_daily_download_percentage(),
            "formatted_storage_used": AdminService._format_bytes(user.storage_used),
            "formatted_storage_limit": AdminService._format_bytes(user.storage_limit),
            "formatted_total_size": AdminService._format_bytes(total_size),
            "files": active_files
        }
    
    @staticmethod
    def update_user_limits(db: Session, user_id: str, storage_limit: int = None, download_limit: int = None) -> User:
        """Update user storage and download limits"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if storage_limit is not None:
            user.storage_limit = storage_limit
        
        if download_limit is not None:
            user.daily_download_limit = download_limit
        
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def upgrade_user_to_premium(db: Session, user_id: str, duration_days: int = 30) -> User:
        """Upgrade user to premium plan"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.upgrade_to_premium(duration_days)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_users_by_plan(db: Session, plan_type: PlanType, skip: int = 0, limit: int = 100) -> List[User]:
        """Get users by plan type"""
        return db.query(User).filter(User.plan_type == plan_type).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_users_near_storage_limit(db: Session, percentage: float = 90.0, skip: int = 0, limit: int = 100) -> List[User]:
        """Get users approaching their storage limit"""
        return db.query(User).filter(
            User.storage_used >= (User.storage_limit * (percentage / 100.0))
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes in human-readable format"""
        if bytes_value is None:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"

# Global instance
admin_service = AdminService()