"""
Admin service for handling administrative operations
"""
from sqlalchemy.orm import Session
from app.db.models import User, File
from typing import List, Dict, Any

class AdminService:
    @staticmethod
    def get_system_stats(db: Session) -> Dict[str, Any]:
        """Get overall system statistics"""
        total_users = db.query(User).count()
        total_files = db.query(File).count()
        total_file_size = db.query(File).filter(File.is_active == True).with_entities(
            db.func.sum(File.file_size)
        ).scalar() or 0
        
        return {
            "total_users": total_users,
            "total_files": total_files,
            "total_file_size": total_file_size
        }
    
    @staticmethod
    def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination"""
        return db.query(User).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_all_files(db: Session, skip: int = 0, limit: int = 100) -> List[File]:
        """Get all files with pagination"""
        return db.query(File).offset(skip).limit(limit).all()
    
    @staticmethod
    def toggle_user_status(db: Session, user_id: int) -> User:
        """Toggle user active status"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = not user.is_active
            db.commit()
            db.refresh(user)
        return user
    
    @staticmethod
    def delete_file(db: Session, file_id: str) -> bool:
        """Delete a file (soft delete)"""
        file = db.query(File).filter(File.file_id == file_id).first()
        if file:
            file.is_active = False
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_user_files(db: Session, user_id: int) -> List[File]:
        """Get all files for a specific user"""
        return db.query(File).filter(File.owner_id == user_id).all()
    
    @staticmethod
    def get_user_stats(db: Session, user_id: int) -> Dict[str, Any]:
        """Get statistics for a specific user"""
        user_files = db.query(File).filter(File.owner_id == user_id).all()
        total_files = len(user_files)
        total_size = sum(f.file_size for f in user_files)
        
        return {
            "total_files": total_files,
            "total_size": total_size,
            "files": user_files
        }

# Global instance
admin_service = AdminService()