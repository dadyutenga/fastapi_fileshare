"""
Optimized File Service - High Performance File Operations with User Limits and Folders
"""
import os
import asyncio
import hashlib
import logging
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, UploadFile, BackgroundTasks
from cachetools import TTLCache

from app.db.models import File, User
from app.schemas.file import FilePreview
from app.utils.helpers import generate_file_id, calculate_file_hash, format_bytes, get_user_upload_directory
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Thread pool for I/O operations
thread_pool = ThreadPoolExecutor(max_workers=4)

# Cache for file stats and metadata (TTL: 5 minutes)
file_cache = TTLCache(maxsize=1000, ttl=300)

# File type mappings for better performance
FILE_TYPE_ICONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'],
    'video': ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm'],
    'audio': ['mp3', 'wav', 'flac', 'aac', 'ogg', 'wma'],
    'pdf': ['pdf'],
    'document': ['doc', 'docx', 'txt', 'rtf'],
    'spreadsheet': ['xls', 'xlsx', 'csv'],
    'presentation': ['ppt', 'pptx'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz', 'bz2'],
    'code': ['py', 'js', 'html', 'css', 'json', 'xml', 'sql']
}

class FileServiceError(Exception):
    """Custom exception for file service errors"""
    pass

# ================================
# UTILITY FUNCTIONS
# ================================

def ensure_upload_dir() -> None:
    """Ensure upload directory exists with proper permissions"""
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Create temp directory for chunks
    temp_path = upload_path / "temp_chunks"
    temp_path.mkdir(exist_ok=True)

@lru_cache(maxsize=512)
def get_file_type_from_extension(file_ext: str) -> str:
    """Get file type category from extension"""
    file_ext = file_ext.lower().lstrip('.')
    for file_type, extensions in FILE_TYPE_ICONS.items():
        if file_ext in extensions:
            return file_type
    return 'other'

@lru_cache(maxsize=512)
def get_content_type_cached(filename: str) -> Optional[str]:
    """Get content type with caching"""
    content_type, _ = mimetypes.guess_type(filename)
    return content_type

# ================================
# VALIDATION FUNCTIONS
# ================================

def validate_file_comprehensive(file: UploadFile) -> Dict[str, Any]:
    """Comprehensive file validation with detailed feedback"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Check filename length
    if len(file.filename) > 255:
        raise HTTPException(status_code=400, detail="Filename too long (max 255 characters)")
    
    # Check for dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
    if any(char in file.filename for char in dangerous_chars):
        raise HTTPException(status_code=400, detail="Filename contains invalid characters")
    
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.allowed_extensions_list:
        raise HTTPException(status_code=400, detail=f"File type {file_ext} not allowed")
    
    # Check file size
    if hasattr(file, 'size') and file.size:
        if file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE // (1024*1024)}MB"
            )
    
    return {
        "filename": file.filename,
        "extension": file_ext,
        "file_type": get_file_type_from_extension(file_ext),
        "estimated_size": getattr(file, 'size', 0)
    }

def check_user_storage_limit(db: Session, user_id: int, file_size: int) -> None:
    """Check if user has enough storage space"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.check_storage_available(file_size):
        used_gb = user.storage_used / (1024**3)
        limit_gb = user.storage_limit / (1024**3)
        raise HTTPException(
            status_code=413, 
            detail=f"Storage limit exceeded. Used: {used_gb:.2f}GB / {limit_gb:.2f}GB"
        )

def check_user_download_limit(db: Session, user_id: int, download_size: int) -> None:
    """Check if user has enough daily download quota"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.check_download_available(download_size):
        used_gb = user.daily_downloads_used / (1024**3)
        limit_gb = user.daily_download_limit / (1024**3)
        raise HTTPException(
            status_code=429, 
            detail=f"Daily download limit exceeded. Used: {used_gb:.2f}GB / {limit_gb:.2f}GB today"
        )

# ================================
# CORE FILE OPERATIONS
# ================================

async def save_file_async(
    db: Session, 
    file: UploadFile, 
    ttl: int, 
    owner_id: int, 
    is_public: bool = False,
    background_tasks: Optional[BackgroundTasks] = None
) -> File:
    """Save file to user-specific directory with storage limit checking"""
    
    # Validate file
    validation_result = validate_file_comprehensive(file)
    
    # Read file content first to get actual size
    file_content = await file.read()
    actual_file_size = len(file_content)
    
    # Check user storage limit
    check_user_storage_limit(db, owner_id, actual_file_size)
    
    # Ensure upload directory exists
    ensure_upload_dir()
    
    # Get user-specific upload directory
    user_upload_dir = get_user_upload_directory(owner_id)
    
    # Generate unique identifiers
    file_id = generate_file_id()
    safe_filename = f"{file_id}_{validation_result['filename']}"
    file_path = os.path.join(user_upload_dir, safe_filename)
    
    try:
        # Write file to user's directory
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Calculate file hash in background
        file_hash = None
        if background_tasks:
            file_hash = await asyncio.get_event_loop().run_in_executor(
                None, calculate_file_hash, file_path
            )
        
        # Determine content type
        content_type = get_content_type_cached(validation_result['filename'])
        
        # Create database record
        db_file = File(
            file_id=file_id,
            filename=safe_filename,
            original_filename=validation_result['filename'],
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
        
        logger.info(f"File {file_id} saved for user {owner_id}: {format_bytes(actual_file_size)}")
        return db_file
        
    except Exception as e:
        # Clean up file if database operation fails
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        logger.error(f"Error saving file for user {owner_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

def get_file_path(db: Session, file_id: str, user_id: Optional[int] = None) -> Tuple[str, File]:
    """Get file path with access control and download limit checking"""
    
    # Get file info
    file = db.query(File).filter(
        and_(File.file_id == file_id, File.is_active == True)
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check access permissions
    if not file.is_public:
        if not user_id or file.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if file has expired
    if file.is_expired():
        raise HTTPException(status_code=410, detail="File has expired")
    
    # Check if file exists on disk
    if not os.path.exists(file.path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # For private files, check download limits (public files don't count against limits)
    if not file.is_public and user_id:
        check_user_download_limit(db, user_id, file.file_size)
        
        # Update user download usage
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.add_download_usage(file.file_size)
    
    # Increment download count
    file.download_count += 1
    db.commit()
    
    logger.info(f"File {file_id} downloaded by user {user_id}: {format_bytes(file.file_size)}")
    return file.path, file

def delete_file(db: Session, file_id: str, user_id: int) -> Dict[str, Any]:
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
    
    # Schedule physical file deletion in background
    def delete_physical_file():
        try:
            if os.path.exists(file.path):
                os.remove(file.path)
                logger.info(f"Physical file deleted: {file.path}")
        except Exception as e:
            logger.error(f"Error deleting physical file {file.path}: {e}")
    
    # Run deletion in background
    asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, delete_physical_file))
    
    logger.info(f"File {file_id} deleted by user {user_id}")
    return {
        "success": True,
        "message": f"File '{file.original_filename}' deleted successfully",
        "file_id": file_id
    }

def get_user_files(db: Session, user_id: int, limit: int = 100, offset: int = 0) -> List[File]:
    """Get user files with pagination"""
    return db.query(File).filter(
        and_(File.owner_id == user_id, File.is_active == True)
    ).order_by(File.upload_time.desc()).offset(offset).limit(limit).all()

def get_file_preview(db: Session, file_id: str, user_id: Optional[int] = None) -> FilePreview:
    """Get file preview with access control"""
    
    file = db.query(File).filter(
        and_(File.file_id == file_id, File.is_active == True)
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check access permissions
    if not file.is_public:
        if not user_id or file.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if file has expired
    if file.is_expired():
        raise HTTPException(status_code=410, detail="File has expired")
    
    # Determine preview type
    file_ext = os.path.splitext(file.original_filename)[1].lower().lstrip('.')
    preview_type = get_file_type_from_extension(file_ext)
    
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
        can_preview=preview_type in ['image', 'text', 'pdf']
    )

def get_user_stats(db: Session, user_id: int) -> Dict[str, Any]:
    """Get comprehensive user statistics"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get file statistics
    files = db.query(File).filter(
        and_(File.owner_id == user_id, File.is_active == True)
    ).all()
    
    total_files = len(files)
    total_downloads = sum(f.download_count for f in files)
    
    # Group files by type
    file_types = {}
    for file in files:
        file_ext = os.path.splitext(file.original_filename)[1].lower().lstrip('.')
        file_type = get_file_type_from_extension(file_ext)
        if file_type not in file_types:
            file_types[file_type] = {"count": 0, "size": 0}
        file_types[file_type]["count"] += 1
        file_types[file_type]["size"] += file.file_size
    
    return {
        "user_id": user_id,
        "total_files": total_files,
        "storage_used": user.storage_used,
        "storage_limit": user.storage_limit,
        "storage_percentage": user.get_storage_percentage(),
        "daily_downloads_used": user.daily_downloads_used,
        "daily_download_limit": user.daily_download_limit,
        "daily_download_percentage": user.get_daily_download_percentage(),
        "total_downloads": total_downloads,
        "file_types": file_types,
        "formatted_storage_used": format_bytes(user.storage_used),
        "formatted_storage_limit": format_bytes(user.storage_limit),
        "formatted_daily_downloads": format_bytes(user.daily_downloads_used),
        "formatted_daily_limit": format_bytes(user.daily_download_limit)
    }

# Legacy compatibility functions
save_file = save_file_async
save_file_async_legacy = save_file_async
save_file_sync = save_file_async  # For compatibility
save_file_sync_optimized = save_file_async  # For compatibility
save_file_ultra_fast = save_file_async  # For compatibility
