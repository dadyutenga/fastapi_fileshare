"""
MySQL-optimized File Service with User Folders and Storage Limits
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import os
import hashlib
import shutil
import asyncio
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, UploadFile, BackgroundTasks
from concurrent.futures import ThreadPoolExecutor

from app.db.models import File, User
from app.schemas.file import FilePreview
from app.utils.helpers import generate_file_id, get_user_upload_path, get_file_path_for_user
from app.core.config import settings

logger = logging.getLogger(__name__)
thread_pool = ThreadPoolExecutor(max_workers=4)

class MySQLFileService:
    """Enhanced file service for MySQL with user folders and storage limits"""
    
    @staticmethod
    def check_user_storage_limit(db: Session, user_id: int, file_size: int) -> bool:
        """Check if user has enough storage space"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user.check_storage_available(file_size)
    
    @staticmethod
    def check_user_download_limit(db: Session, user_id: int, download_size: int) -> bool:
        """Check if user has enough daily download quota"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user.check_download_available(download_size)
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    @staticmethod
    async def save_file_with_limits(
        db: Session, 
        file: UploadFile, 
        ttl: int, 
        owner_id: int, 
        is_public: bool = False,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> File:
        """Save file with storage limit validation and user folder organization"""
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Check storage limit
        if not MySQLFileService.check_user_storage_limit(db, owner_id, file_size):
            raise HTTPException(
                status_code=413, 
                detail="Storage limit exceeded. Please delete some files or upgrade your plan."
            )
        
        # Get user upload directory
        user_upload_path = get_user_upload_path(owner_id)
        
        # Generate file identifiers
        file_id = generate_file_id()
        safe_filename = f"{file_id}_{file.filename}"
        file_path = get_file_path_for_user(owner_id, safe_filename)
        
        try:
            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Calculate file hash
            file_hash = MySQLFileService.calculate_file_hash(file_path)
            
            # Determine content type
            import mimetypes
            content_type, _ = mimetypes.guess_type(file.filename)
            
            # Create database record
            db_file = File(
                file_id=file_id,
                filename=safe_filename,
                original_filename=file.filename,
                path=file_path,
                file_size=file_size,
                content_type=content_type,
                ttl=ttl,
                is_public=is_public,
                owner_id=owner_id,
                file_hash=file_hash
            )
            
            db.add(db_file)
            
            # Update user storage usage
            user = db.query(User).filter(User.id == owner_id).first()
            user.add_storage_usage(file_size)
            
            db.commit()
            db.refresh(db_file)
            
            logger.info(f"File saved: {file.filename} ({file_size} bytes) for user {owner_id}")
            return db_file
            
        except Exception as e:
            # Clean up file if database save failed
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    @staticmethod
    def get_file_with_download_limit(db: Session, file_id: str, user_id: Optional[int] = None) -> Tuple[str, File]:
        """Get file path with download limit validation"""
        
        # Get file info
        file = db.query(File).filter(
            and_(File.file_id == file_id, File.is_active == True)
        ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check if file is expired
        if file.is_expired():
            raise HTTPException(status_code=410, detail="File has expired")
        
        # Check access permissions
        if not file.is_public:
            if not user_id or file.owner_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Check download limit (for authenticated users)
        if user_id:
            if not MySQLFileService.check_user_download_limit(db, user_id, file.file_size):
                raise HTTPException(
                    status_code=429, 
                    detail="Daily download limit exceeded. Please try again tomorrow."
                )
        
        # Check if file exists on disk
        if not os.path.exists(file.path):
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        # Update download count and user's download usage
        file.download_count += 1
        
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.add_download_usage(file.file_size)
        
        db.commit()
        
        return file.path, file
    
    @staticmethod
    def delete_file_with_storage_update(db: Session, file_id: str, user_id: int) -> Dict[str, Any]:
        """Delete file and update user storage usage"""
        
        file = db.query(File).filter(
            and_(
                File.file_id == file_id,
                File.owner_id == user_id,
                File.is_active == True
            )
        ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Soft delete in database
        file.is_active = False
        
        # Update user storage usage
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.remove_storage_usage(file.file_size)
        
        db.commit()
        
        # Schedule physical file deletion
        def cleanup_file():
            try:
                if os.path.exists(file.path):
                    os.remove(file.path)
                    logger.info(f"Physical file deleted: {file.path}")
            except Exception as e:
                logger.error(f"Error deleting physical file {file.path}: {e}")
        
        # Delete file in background
        asyncio.create_task(asyncio.get_event_loop().run_in_executor(thread_pool, cleanup_file))
        
        return {
            "success": True,
            "message": f"File '{file.original_filename}' deleted successfully",
            "file_id": file_id,
            "storage_freed": file.file_size
        }
    
    @staticmethod
    def get_user_storage_stats(db: Session, user_id: int) -> Dict[str, Any]:
        """Get comprehensive storage statistics for user"""
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get file statistics
        file_stats = db.query(
            func.count(File.id).label('total_files'),
            func.sum(File.file_size).label('total_size'),
            func.sum(File.download_count).label('total_downloads')
        ).filter(
            and_(File.owner_id == user_id, File.is_active == True)
        ).first()
        
        # Get file type breakdown
        file_types = db.query(
            File.content_type,
            func.count(File.id).label('count'),
            func.sum(File.file_size).label('size')
        ).filter(
            and_(File.owner_id == user_id, File.is_active == True)
        ).group_by(File.content_type).all()
        
        return {
            "user_id": user_id,
            "username": user.username,
            "storage_limit": user.storage_limit,
            "storage_used": user.storage_used,
            "storage_available": user.storage_limit - user.storage_used,
            "storage_percentage": user.get_storage_percentage(),
            "daily_download_limit": user.daily_download_limit,
            "daily_downloads_used": user.daily_downloads_used,
            "daily_download_percentage": user.get_daily_download_percentage(),
            "total_files": file_stats.total_files or 0,
            "total_downloads": file_stats.total_downloads or 0,
            "file_types": [
                {
                    "content_type": ft.content_type or "Unknown",
                    "count": ft.count,
                    "size": ft.size
                } for ft in file_types
            ]
        }

# Export the main functions for backward compatibility
mysql_file_service = MySQLFileService()

# Legacy function names
save_file_async = mysql_file_service.save_file_with_limits
get_file_path = mysql_file_service.get_file_with_download_limit
delete_file = mysql_file_service.delete_file_with_storage_update
get_user_stats = mysql_file_service.get_user_storage_stats
