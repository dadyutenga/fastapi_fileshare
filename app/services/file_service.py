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
import threading

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
    def get_user_files(db: Session, user_id: int, limit: int = 100, offset: int = 0) -> List[File]:
        """Get user files with pagination"""
        return db.query(File).filter(
            and_(File.owner_id == user_id, File.is_active == True)
        ).order_by(File.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def delete_file_with_storage_update(db: Session, file_id: str, user_id: int) -> Dict[str, Any]:
        """Delete file and update user storage usage - Fixed async issues"""
        
        file = db.query(File).filter(
            and_(
                File.file_id == file_id,
                File.owner_id == user_id,
                File.is_active == True
            )
        ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Store file path before soft delete
        file_path = file.path
        file_name = file.original_filename
        file_size = file.file_size
        
        # Soft delete in database
        file.is_active = False
        
        # Update user storage usage
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.remove_storage_usage(file_size)
        
        # Commit database changes immediately
        db.commit()
        
        # Schedule physical file deletion in a separate thread (not async)
        def cleanup_file_sync():
            """Synchronous file cleanup function"""
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Physical file deleted: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting physical file {file_path}: {e}")
        
        # Use thread pool to delete file without blocking
        threading.Thread(target=cleanup_file_sync, daemon=True).start()
        
        return {
            "success": True,
            "message": f"File '{file_name}' deleted successfully",
            "file_id": file_id,
            "storage_freed": file_size
        }
    
    @staticmethod
    def get_file_preview(db: Session, file_id: str, user_id: Optional[int] = None) -> FilePreview:
        """Get file preview information"""
        file = db.query(File).filter(
            and_(File.file_id == file_id, File.is_active == True)
        ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check access permissions
        if not file.is_public:
            if not user_id or file.owner_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Determine preview type based on content type
        preview_type = "other"
        if file.content_type:
            if file.content_type.startswith('image/'):
                preview_type = "image"
            elif file.content_type.startswith('video/'):
                preview_type = "video"
            elif file.content_type.startswith('audio/'):
                preview_type = "audio"
            elif file.content_type == 'application/pdf':
                preview_type = "pdf"
            elif file.content_type.startswith('text/'):
                preview_type = "text"
        
        return FilePreview(
            file_id=file.file_id,
            filename=file.filename,
            original_filename=file.original_filename,
            file_size=file.file_size,
            content_type=file.content_type,
            upload_time=file.upload_time,
            download_count=file.download_count,
            is_public=file.is_public,
            preview_type=preview_type,
            preview_content=None,
            can_preview=preview_type != "other"
        )
    
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

# Legacy function names for compatibility
save_file_async = mysql_file_service.save_file_with_limits
get_file_path = mysql_file_service.get_file_with_download_limit
delete_file = mysql_file_service.delete_file_with_storage_update
get_user_stats = mysql_file_service.get_user_storage_stats
get_file_preview = mysql_file_service.get_file_preview

# Add the missing function
get_user_files = mysql_file_service.get_user_files

# Additional compatibility functions
def save_file(db: Session, file: UploadFile, ttl: int, owner_id: int, is_public: bool = False) -> File:
    """Synchronous wrapper for save_file_async"""
    import asyncio
    return asyncio.run(save_file_async(db, file, ttl, owner_id, is_public))

def get_file_info(db: Session, file_id: str, user_id: Optional[int] = None) -> File:
    """Get file info without download tracking"""
    file = db.query(File).filter(
        and_(File.file_id == file_id, File.is_active == True)
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check access permissions
    if not file.is_public:
        if not user_id or file.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return file

def toggle_file_privacy(db: Session, file_id: str, user_id: int) -> File:
    """Toggle file privacy setting"""
    file = db.query(File).filter(
        and_(
            File.file_id == file_id,
            File.owner_id == user_id,
            File.is_active == True
        )
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file.is_public = not file.is_public
    db.commit()
    db.refresh(file)
    
    return file

# Export all functions
__all__ = [
    'save_file_async',
    'save_file',
    'get_file_path', 
    'get_user_files',
    'delete_file',
    'get_user_stats',
    'get_file_preview',
    'get_file_info',
    'toggle_file_privacy',
    'mysql_file_service'
]
