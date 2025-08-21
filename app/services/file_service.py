"""
MySQL-optimized File Service with User Folders, Storage Limits, and UUID support
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
from app.utils.helpers import generate_file_id, get_user_upload_path, get_file_path_for_user, is_valid_uuid
from app.core.config import settings

logger = logging.getLogger(__name__)
thread_pool = ThreadPoolExecutor(max_workers=4)

class MySQLFileService:
    """Enhanced file service for MySQL with user folders, storage limits, and UUID support"""
    
    @staticmethod
    def check_user_storage_limit(db: Session, user_id: str, file_size: int) -> Tuple[bool, Dict[str, Any]]:
        """Check if user has enough storage space and return detailed info"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user account is active
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is disabled")
        
        available_space = user.storage_limit - user.storage_used
        can_upload = user.check_storage_available(file_size)
        
        return can_upload, {
            "can_upload": can_upload,
            "storage_used": user.storage_used,
            "storage_limit": user.storage_limit,
            "available_space": available_space,
            "file_size": file_size,
            "would_exceed_by": max(0, (user.storage_used + file_size) - user.storage_limit),
            "storage_percentage": user.get_storage_percentage(),
            "plan_type": user.plan_type.value if user.plan_type else "free",
            "is_premium": user.is_premium
        }
    
    @staticmethod
    def check_user_download_limit(db: Session, user_id: str, download_size: int) -> Tuple[bool, Dict[str, Any]]:
        """Check if user has enough daily download quota and return detailed info"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user account is active
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is disabled")
        
        can_download = user.check_download_available(download_size)
        available_quota = user.daily_download_limit - user.daily_downloads_used
        
        return can_download, {
            "can_download": can_download,
            "daily_downloads_used": user.daily_downloads_used,
            "daily_download_limit": user.daily_download_limit,
            "available_quota": available_quota,
            "download_size": download_size,
            "would_exceed_by": max(0, (user.daily_downloads_used + download_size) - user.daily_download_limit),
            "download_percentage": user.get_daily_download_percentage(),
            "reset_time": user.last_download_reset,
            "plan_type": user.plan_type.value if user.plan_type else "free",
            "is_premium": user.is_premium
        }
    
    @staticmethod
    def validate_file_upload(file: UploadFile, max_file_size: int = None) -> Dict[str, Any]:
        """Validate file upload with comprehensive checks"""
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        # Check file extension
        allowed_extensions = settings.allowed_extensions_list
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"File type '{file_extension}' not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Use user's max file size or system default
        max_size = max_file_size or settings.MAX_FILE_SIZE
        
        return {
            "filename": file.filename,
            "file_extension": file_extension,
            "max_allowed_size": max_size,
            "is_valid": True
        }
    
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
        owner_id: str, 
        is_public: bool = False,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> File:
        """Save file with comprehensive validation, storage limits, and user folder organization"""
        
        # Validate user ID format
        if not is_valid_uuid(owner_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Validate file upload
        file_validation = MySQLFileService.validate_file_upload(file)
        
        # Read file content and get actual size
        file_content = await file.read()
        actual_file_size = len(file_content)
        
        # Check if file size exceeds maximum allowed
        if actual_file_size > file_validation["max_allowed_size"]:
            raise HTTPException(
                status_code=413, 
                detail=f"File size ({actual_file_size} bytes) exceeds maximum allowed size ({file_validation['max_allowed_size']} bytes)"
            )
        
        # Check storage limit with detailed response
        can_upload, storage_info = MySQLFileService.check_user_storage_limit(db, owner_id, actual_file_size)
        
        if not can_upload:
            error_msg = f"Storage limit exceeded. Used: {storage_info['storage_used']} bytes, Limit: {storage_info['storage_limit']} bytes"
            if storage_info['would_exceed_by'] > 0:
                error_msg += f", Would exceed by: {storage_info['would_exceed_by']} bytes"
            
            # Suggest upgrade for free users
            if storage_info['plan_type'] == 'free':
                error_msg += ". Consider upgrading to Premium for more storage."
            
            raise HTTPException(status_code=413, detail=error_msg)
        
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
            
            # Calculate file hash for integrity
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
                file_size=actual_file_size,
                content_type=content_type,
                ttl=ttl,
                is_public=is_public,
                owner_id=owner_id,
                file_hash=file_hash
            )
            
            db.add(db_file)
            
            # Update user storage usage
            user = db.query(User).filter(User.id == owner_id).first()
            user.add_storage_usage(actual_file_size)
            
            db.commit()
            db.refresh(db_file)
            
            logger.info(f"File saved: {file.filename} ({actual_file_size} bytes) for user {owner_id}")
            return db_file
            
        except Exception as e:
            # Clean up file if database save failed
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    @staticmethod
    def get_file_with_download_limit(db: Session, file_id: str, user_id: Optional[str] = None) -> Tuple[str, File]:
        """Get file path with download limit validation and UUID support"""
        
        # Validate user ID if provided
        if user_id and not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Get file info - support both UUID and file_id
        file = None
        if is_valid_uuid(file_id):
            # Try as primary key UUID first
            file = db.query(File).filter(
                and_(File.id == file_id, File.is_active == True)
            ).first()
        
        if not file:
            # Try as file_id (legacy support)
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
                raise HTTPException(status_code=403, detail="Access denied to private file")
        
        # Check download limit (for authenticated users)
        if user_id:
            can_download, download_info = MySQLFileService.check_user_download_limit(db, user_id, file.file_size or 0)
            
            if not can_download:
                error_msg = f"Daily download limit exceeded. Used: {download_info['daily_downloads_used']} bytes, Limit: {download_info['daily_download_limit']} bytes"
                if download_info['would_exceed_by'] > 0:
                    error_msg += f", Would exceed by: {download_info['would_exceed_by']} bytes"
                
                # Suggest upgrade for free users
                if download_info['plan_type'] == 'free':
                    error_msg += ". Consider upgrading to Premium for higher download limits."
                
                raise HTTPException(status_code=429, detail=error_msg)
        
        # Check if file exists on disk
        if not os.path.exists(file.path):
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        # Update download count and user's download usage
        file.download_count += 1
        
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.add_download_usage(file.file_size or 0)
        
        db.commit()
        
        return file.path, file
    
    @staticmethod
    def get_user_files(db: Session, user_id: str, limit: int = 100, offset: int = 0) -> List[File]:
        """Get user files with pagination and UUID support"""
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        return db.query(File).filter(
            and_(File.owner_id == user_id, File.is_active == True)
        ).order_by(File.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def delete_file_with_storage_update(db: Session, file_id: str, user_id: str) -> Dict[str, Any]:
        """Delete file and update user storage usage with UUID support"""
        
        # Validate user ID
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Find file - support both UUID and file_id
        file = None
        if is_valid_uuid(file_id):
            # Try as primary key UUID first
            file = db.query(File).filter(
                and_(
                    File.id == file_id,
                    File.owner_id == user_id,
                    File.is_active == True
                )
            ).first()
        
        if not file:
            # Try as file_id (legacy support)
            file = db.query(File).filter(
                and_(
                    File.file_id == file_id,
                    File.owner_id == user_id,
                    File.is_active == True
                )
            ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found or access denied")
        
        # Store file info before deletion
        file_path = file.path
        file_name = file.original_filename
        file_size = file.file_size or 0
        
        # Soft delete in database
        file.is_active = False
        
        # Update user storage usage
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.remove_storage_usage(file_size)
        
        # Commit database changes immediately
        db.commit()
        
        # Schedule physical file deletion in a separate thread
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
            "storage_freed": file_size,
            "formatted_storage_freed": MySQLFileService._format_bytes(file_size)
        }
    
    @staticmethod
    def get_file_preview(db: Session, file_id: str, user_id: Optional[str] = None) -> FilePreview:
        """Get file preview information with UUID support"""
        
        # Validate user ID if provided
        if user_id and not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Find file - support both UUID and file_id
        file = None
        if is_valid_uuid(file_id):
            # Try as primary key UUID first
            file = db.query(File).filter(
                and_(File.id == file_id, File.is_active == True)
            ).first()
        
        if not file:
            # Try as file_id (legacy support)
            file = db.query(File).filter(
                and_(File.file_id == file_id, File.is_active == True)
            ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check access permissions
        if not file.is_public:
            if not user_id or file.owner_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied to private file")
        
        # Determine preview type based on content type
        preview_type = "other"
        can_preview = False
        
        if file.content_type:
            if file.content_type.startswith('image/'):
                preview_type = "image"
                can_preview = True
            elif file.content_type.startswith('video/'):
                preview_type = "video"
                can_preview = True
            elif file.content_type.startswith('audio/'):
                preview_type = "audio"
                can_preview = True
            elif file.content_type == 'application/pdf':
                preview_type = "pdf"
                can_preview = True
            elif file.content_type.startswith('text/'):
                preview_type = "text"
                can_preview = True
            elif file.content_type in ['application/zip', 'application/x-rar-compressed']:
                preview_type = "archive"
                can_preview = False
        
        return FilePreview(
            file_id=file.file_id,
            filename=file.filename,
            original_filename=file.original_filename,
            file_size=file.file_size or 0,
            content_type=file.content_type,
            upload_time=file.upload_time,
            download_count=file.download_count,
            is_public=file.is_public,
            preview_type=preview_type,
            preview_content=None,
            can_preview=can_preview
        )
    
    @staticmethod
    def get_user_storage_stats(db: Session, user_id: str) -> Dict[str, Any]:
        """Get comprehensive storage statistics for user with UUID support"""
        
        if not is_valid_uuid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
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
        
        # Convert Decimal values to float/int for JSON serialization
        def safe_convert(value, default=0):
            """Convert Decimal/None values to JSON-serializable types"""
            if value is None:
                return default
            try:
                # Convert Decimal to float, or return as-is for other types
                from decimal import Decimal
                if isinstance(value, Decimal):
                    return float(value)
                return value
            except:
                return default
        
        return {
            "user_id": user_id,
            "username": getattr(user, 'username', 'Unknown'),
            "email": getattr(user, 'email', None),
            "plan_type": user.plan_type.value if user.plan_type else "free",
            "is_premium": user.is_premium,
            "premium_until": user.premium_until,
            "premium_days_remaining": user.get_premium_days_remaining() if user.is_premium else 0,
            "storage_limit": safe_convert(user.storage_limit, 5368709120),  # 5GB default
            "formatted_storage_limit": MySQLFileService._format_bytes(user.storage_limit),
            "storage_used": safe_convert(user.storage_used, 0),
            "formatted_storage_used": MySQLFileService._format_bytes(user.storage_used),
            "storage_available": safe_convert(user.storage_limit, 5368709120) - safe_convert(user.storage_used, 0),
            "formatted_storage_available": MySQLFileService._format_bytes(
                safe_convert(user.storage_limit, 5368709120) - safe_convert(user.storage_used, 0)
            ),
            "storage_percentage": safe_convert(user.get_storage_percentage(), 0.0),
            "daily_download_limit": safe_convert(user.daily_download_limit, 1073741824),  # 1GB default
            "formatted_download_limit": MySQLFileService._format_bytes(user.daily_download_limit),
            "daily_downloads_used": safe_convert(user.daily_downloads_used, 0),
            "formatted_daily_downloads_used": MySQLFileService._format_bytes(user.daily_downloads_used),
            "daily_download_percentage": safe_convert(user.get_daily_download_percentage(), 0.0),
            "total_files": safe_convert(file_stats.total_files, 0),
            "total_downloads": safe_convert(file_stats.total_downloads, 0),
            "last_download_reset": user.last_download_reset,
            "is_near_storage_limit": user.get_storage_percentage() >= 90.0,
            "is_near_download_limit": user.get_daily_download_percentage() >= 90.0,
            "file_types": [
                {
                    "content_type": ft.content_type or "Unknown",
                    "count": safe_convert(ft.count, 0),
                    "size": safe_convert(ft.size, 0),
                    "formatted_size": MySQLFileService._format_bytes(ft.size)
                } for ft in file_types
            ]
        }
    
    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes in human-readable format"""
        if bytes_value is None:
            return "0 B"
        
        bytes_value = int(bytes_value)
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"

# Export the main functions for backward compatibility
mysql_file_service = MySQLFileService()

# Legacy function names for compatibility with UUID support
save_file_async = mysql_file_service.save_file_with_limits
get_file_path = mysql_file_service.get_file_with_download_limit
delete_file = mysql_file_service.delete_file_with_storage_update
get_user_stats = mysql_file_service.get_user_storage_stats
get_file_preview = mysql_file_service.get_file_preview
get_user_files = mysql_file_service.get_user_files

# Additional compatibility functions with UUID support
def save_file(db: Session, file: UploadFile, ttl: int, owner_id: str, is_public: bool = False) -> File:
    """Synchronous wrapper for save_file_async with UUID support"""
    import asyncio
    return asyncio.run(save_file_async(db, file, ttl, owner_id, is_public))

def get_file_info(db: Session, file_id: str, user_id: Optional[str] = None) -> File:
    """Get file info without download tracking with UUID support"""
    
    # Validate user ID if provided
    if user_id and not is_valid_uuid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Find file - support both UUID and file_id
    file = None
    if is_valid_uuid(file_id):
        # Try as primary key UUID first
        file = db.query(File).filter(
            and_(File.id == file_id, File.is_active == True)
        ).first()
    
    if not file:
        # Try as file_id (legacy support)
        file = db.query(File).filter(
            and_(File.file_id == file_id, File.is_active == True)
        ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check access permissions
    if not file.is_public:
        if not user_id or file.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to private file")
    
    return file

def toggle_file_privacy(db: Session, file_id: str, user_id: str) -> File:
    """Toggle file privacy setting with UUID support"""
    
    # Validate user ID
    if not is_valid_uuid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Find file - support both UUID and file_id
    file = None
    if is_valid_uuid(file_id):
        # Try as primary key UUID first
        file = db.query(File).filter(
            and_(
                File.id == file_id,
                File.owner_id == user_id,
                File.is_active == True
            )
        ).first()
    
    if not file:
        # Try as file_id (legacy support)
        file = db.query(File).filter(
            and_(
                File.file_id == file_id,
                File.owner_id == user_id,
                File.is_active == True
            )
        ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found or access denied")
    
    file.is_public = not file.is_public
    db.commit()
    db.refresh(file)
    
    return file

def check_user_can_upload(db: Session, user_id: str, file_size: int) -> Dict[str, Any]:
    """Check if user can upload a file of given size"""
    can_upload, info = MySQLFileService.check_user_storage_limit(db, user_id, file_size)
    return info

def check_user_can_download(db: Session, user_id: str, download_size: int) -> Dict[str, Any]:
    """Check if user can download a file of given size"""
    can_download, info = MySQLFileService.check_user_download_limit(db, user_id, download_size)
    return info

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
    'check_user_can_upload',
    'check_user_can_download',
    'mysql_file_service'
]
