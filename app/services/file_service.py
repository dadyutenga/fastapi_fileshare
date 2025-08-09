"""
Optimized File Service - High Performance File Operations
"""
import os
import shutil
import mimetypes
import hashlib
import asyncio
import aiofiles
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, UploadFile, BackgroundTasks
from cachetools import TTLCache

from app.db.models import File
from app.schemas.file import FilePreview
from app.utils.helpers import generate_file_id
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

MIME_TYPE_CACHE = {}

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
    """Get file type category from extension (cached)"""
    file_ext = file_ext.lower().lstrip('.')
    
    for file_type, extensions in FILE_TYPE_ICONS.items():
        if file_ext in extensions:
            return file_type
    return 'other'

@lru_cache(maxsize=512)
def get_content_type_cached(filename: str) -> Optional[str]:
    """Get content type with caching"""
    if filename in MIME_TYPE_CACHE:
        return MIME_TYPE_CACHE[filename]
    
    content_type, _ = mimetypes.guess_type(filename)
    MIME_TYPE_CACHE[filename] = content_type
    return content_type

def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> str:
    """Calculate SHA-256 hash of file for integrity checking"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate hash for {file_path}: {e}")
        return ""

async def safe_file_operation(operation, *args, **kwargs):
    """Safely execute file operations with error handling"""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(thread_pool, operation, *args, **kwargs)
    except Exception as e:
        logger.error(f"File operation failed: {e}")
        raise FileServiceError(f"File operation failed: {str(e)}")

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
        raise HTTPException(
            status_code=400, 
            detail=f"File type '{file_ext}' not allowed. Allowed: {', '.join(settings.allowed_extensions_list[:10])}..."
        )
    
    # Check file size
    if hasattr(file, 'size') and file.size:
        if file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large ({file.size:,} bytes). Maximum: {settings.MAX_FILE_SIZE:,} bytes"
            )
    
    return {
        "filename": file.filename,
        "extension": file_ext,
        "file_type": get_file_type_from_extension(file_ext),
        "estimated_size": getattr(file, 'size', 0)
    }

# ================================
# CORE FILE OPERATIONS
# ================================

async def save_file_ultra_fast(
    db: Session, 
    file: UploadFile, 
    ttl: int, 
    owner_id: int, 
    is_public: bool = False,
    background_tasks: Optional[BackgroundTasks] = None
) -> File:
    """Ultra-fast file saving with async I/O and optimizations"""
    
    # Validate file
    validation_result = validate_file_comprehensive(file)
    
    # Ensure upload directory exists
    ensure_upload_dir()
    
    # Generate unique identifiers
    file_id = generate_file_id()
    safe_filename = f"{file_id}_{validation_result['filename']}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    
    # Read file content asynchronously
    try:
        content = await file.read()
        file_size = len(content)
        
        # Validate actual file size
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large ({file_size:,} bytes). Maximum: {settings.MAX_FILE_SIZE:,} bytes"
            )
        
        # Write file asynchronously
        async def write_file_async():
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
        
        await write_file_async()
        
        # Get content type
        content_type = get_content_type_cached(validation_result['filename'])
        
        # Create optimized database record (without file_hash field)
        db_file = File(
            file_id=file_id,
            filename=safe_filename,
            original_filename=validation_result['filename'],
            path=file_path,
            file_size=file_size,
            content_type=content_type,
            ttl=ttl,
            is_public=is_public,
            owner_id=owner_id
            # Removed file_hash=file_hash since the field doesn't exist
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        # Calculate file hash in background if requested (optional feature)
        if background_tasks:
            background_tasks.add_task(calculate_and_log_file_hash, file_path, file_id)
        
        # Cache file info
        cache_key = f"file_info_{file_id}"
        file_cache[cache_key] = db_file
        
        logger.info(f"File saved successfully: {file_id} ({file_size:,} bytes)")
        return db_file
        
    except Exception as e:
        # Cleanup on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        logger.error(f"Failed to save file {validation_result['filename']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

# Add a background task function for file hash calculation (optional)
def calculate_and_log_file_hash(file_path: str, file_id: str):
    """Background task to calculate and log file hash for integrity checking"""
    try:
        file_hash = calculate_file_hash(file_path)
        if file_hash:
            logger.info(f"File hash calculated for {file_id}: {file_hash[:16]}...")
    except Exception as e:
        logger.error(f"Failed to calculate hash for {file_id}: {e}")

def save_file_sync_optimized(db: Session, file: UploadFile, ttl: int, owner_id: int, is_public: bool = False) -> File:
    """Optimized synchronous file saving for compatibility"""
    
    validation_result = validate_file_comprehensive(file)
    ensure_upload_dir()
    
    file_id = generate_file_id()
    safe_filename = f"{file_id}_{validation_result['filename']}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    
    try:
        # Optimized file copying
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer, length=1024*1024)  # 1MB buffer
        
        file_size = os.path.getsize(file_path)
        content_type = get_content_type_cached(validation_result['filename'])
        
        db_file = File(
            file_id=file_id,
            filename=safe_filename,
            original_filename=validation_result['filename'],
            path=file_path,
            file_size=file_size,
            content_type=content_type,
            ttl=ttl,
            is_public=is_public,
            owner_id=owner_id
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        # Cache the result
        cache_key = f"file_info_{file_id}"
        file_cache[cache_key] = db_file
        
        return db_file
        
    except Exception as e:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

# ================================
# FILE RETRIEVAL & ACCESS
# ================================

def get_file_info_cached(db: Session, file_id: str, user_id: Optional[int] = None) -> File:
    """Get file information with caching"""
    cache_key = f"file_info_{file_id}"
    
    # Try cache first
    if cache_key in file_cache:
        file = file_cache[cache_key]
        if file.is_active:  # Verify still active
            # Check access permissions
            if not file.is_public and (not user_id or file.owner_id != user_id):
                raise HTTPException(status_code=403, detail="Access denied")
            return file
    
    # Query database
    file = db.query(File).filter(
        and_(File.file_id == file_id, File.is_active == True)
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check access permissions
    if not file.is_public and (not user_id or file.owner_id != user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Cache the result
    file_cache[cache_key] = file
    return file

def get_file_path_optimized(db: Session, file_id: str, user_id: Optional[int] = None) -> Tuple[str, File]:
    """Optimized file path retrieval with caching and validation"""
    file = get_file_info_cached(db, file_id, user_id)
    
    # Check if file has expired
    if file.ttl > 0:
        expiry_time = file.upload_time + timedelta(hours=file.ttl)
        if datetime.utcnow() > expiry_time:
            # Auto-cleanup expired file
            file.is_active = False
            db.commit()
            raise HTTPException(status_code=410, detail="File has expired")
    
    # Check if file exists on disk
    if not os.path.exists(file.path):
        logger.error(f"File not found on disk: {file.path}")
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Increment download count atomically
    db.query(File).filter_by(file_id=file_id).update(
        {File.download_count: File.download_count + 1}
    )
    db.commit()
    
    # Update cache
    file.download_count += 1
    cache_key = f"file_info_{file_id}"
    file_cache[cache_key] = file
    
    return file.path, file

# ================================
# FILE MANAGEMENT
# ================================

def get_user_files_optimized(
    db: Session, 
    user_id: int, 
    limit: int = 100, 
    offset: int = 0,
    file_type: Optional[str] = None,
    search_query: Optional[str] = None
) -> List[File]:
    """Optimized user files retrieval with filtering and search"""
    
    query = db.query(File).filter(
        and_(File.owner_id == user_id, File.is_active == True)
    )
    
    # Add file type filter
    if file_type and file_type != 'all':
        if file_type == 'image':
            query = query.filter(File.content_type.like('image/%'))
        elif file_type == 'video':
            query = query.filter(File.content_type.like('video/%'))
        elif file_type == 'audio':
            query = query.filter(File.content_type.like('audio/%'))
        elif file_type == 'document':
            query = query.filter(or_(
                File.content_type.like('application/pdf'),
                File.content_type.like('application/msword%'),
                File.content_type.like('text/%')
            ))
    
    # Add search functionality
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(File.original_filename.ilike(search_pattern))
    
    return query.order_by(File.upload_time.desc()).offset(offset).limit(limit).all()

async def delete_file_optimized(db: Session, file_id: str, user_id: int) -> Dict[str, Any]:
    """Optimized file deletion with async cleanup"""
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
    db.commit()
    
    # Remove from cache
    cache_key = f"file_info_{file_id}"
    file_cache.pop(cache_key, None)
    
    # Schedule physical file deletion
    async def cleanup_physical_file():
        try:
            if os.path.exists(file.path):
                await safe_file_operation(os.remove, file.path)
                logger.info(f"Physical file deleted: {file.path}")
        except Exception as e:
            logger.error(f"Failed to delete physical file {file.path}: {e}")
    
    # Return immediately, cleanup in background
    asyncio.create_task(cleanup_physical_file())
    
    return {
        "success": True,
        "message": f"File '{file.original_filename}' deleted successfully",
        "file_id": file_id
    }

async def delete_all_user_files_optimized(db: Session, user_id: int) -> Dict[str, Any]:
    """Ultra-optimized bulk file deletion"""
    
    # Get all user files in one query
    user_files = db.query(File).filter(
        and_(File.owner_id == user_id, File.is_active == True)
    ).all()
    
    if not user_files:
        return {
            "success": False,
            "message": "No files found to delete",
            "deleted_count": 0,
            "failed_count": 0
        }
    
    file_paths = [file.path for file in user_files]
    file_count = len(user_files)
    
    # Bulk update in database (much faster than individual updates)
    db.query(File).filter(
        and_(File.owner_id == user_id, File.is_active == True)
    ).update({File.is_active: False}, synchronize_session=False)
    
    db.commit()
    
    # Clear cache for all user files
    for file in user_files:
        cache_key = f"file_info_{file.file_id}"
        file_cache.pop(cache_key, None)
    
    # Bulk delete physical files asynchronously
    async def cleanup_all_files():
        deleted_count = 0
        failed_count = 0
        
        # Use semaphore to limit concurrent deletions
        semaphore = asyncio.Semaphore(10)
        
        async def delete_single_file(file_path: str):
            nonlocal deleted_count, failed_count
            async with semaphore:
                try:
                    if os.path.exists(file_path):
                        await safe_file_operation(os.remove, file_path)
                        deleted_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to delete {file_path}: {e}")
        
        # Delete all files concurrently
        tasks = [delete_single_file(path) for path in file_paths]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Bulk deletion completed: {deleted_count} deleted, {failed_count} failed")
    
    # Start cleanup in background
    asyncio.create_task(cleanup_all_files())
    
    return {
        "success": True,
        "message": f"Successfully initiated deletion of {file_count} files",
        "deleted_count": file_count,
        "failed_count": 0
    }

# ================================
# FILE PREVIEW & METADATA
# ================================

def get_file_preview_optimized(db: Session, file_id: str, user_id: Optional[int] = None) -> FilePreview:
    """Optimized file preview with better type detection"""
    file = get_file_info_cached(db, file_id, user_id)
    
    # Determine file type more accurately
    file_ext = os.path.splitext(file.original_filename)[1].lower().lstrip('.')
    file_type = get_file_type_from_extension(file_ext)
    
    preview = FilePreview(
        file_id=file.file_id,
        filename=file.filename,
        original_filename=file.original_filename,
        file_size=file.file_size,
        content_type=file.content_type,
        upload_time=file.upload_time,
        download_count=file.download_count,
        is_public=file.is_public,
        preview_type=file_type,
        preview_content=None,
        can_preview=True
    )
    
    # Generate preview content based on type
    try:
        if file_type == 'image':
            preview.preview_type = "image"
            preview.can_preview = True
            
        elif file_type == 'pdf':
            preview.preview_type = "pdf"
            preview.can_preview = True
            
        elif file_type in ['document', 'code'] or (file.content_type and file.content_type.startswith('text/')):
            preview.preview_type = "text"
            try:
                # Read file content safely
                with open(file.path, "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read(3000)  # Increased limit
                    if len(text_content) == 3000:
                        text_content += "\n\n... [File truncated for preview]"
                    preview.preview_content = text_content
            except Exception:
                preview.preview_content = "Error reading file content"
                
        elif file_type == 'video':
            preview.preview_type = "video"
            preview.can_preview = True
            
        elif file_type == 'audio':
            preview.preview_type = "audio"
            preview.can_preview = True
            
        elif file_type == 'archive':
            preview.preview_type = "archive"
            preview.preview_content = f"Archive file: {file.original_filename}\nSize: {file.file_size:,} bytes"
            preview.can_preview = True
            
        else:
            preview.preview_type = "other"
            preview.can_preview = False
            preview.preview_content = f"Preview not available for {file_type} files"
            
    except Exception as e:
        logger.error(f"Error generating preview for {file_id}: {e}")
        preview.preview_type = "other"
        preview.can_preview = False
        preview.preview_content = f"Error generating preview: {str(e)}"
    
    return preview

# ================================
# STATISTICS & ANALYTICS
# ================================

def get_user_stats_comprehensive(db: Session, user_id: int) -> Dict[str, Any]:
    """Comprehensive user statistics with caching"""
    cache_key = f"user_stats_{user_id}"
    
    if cache_key in file_cache:
        return file_cache[cache_key]
    
    # Use aggregation for better performance
    stats_query = db.query(
        func.count(File.id).label('total_files'),
        func.sum(File.file_size).label('total_size'),
        func.sum(File.download_count).label('total_downloads'),
        func.count(func.nullif(File.is_public, False)).label('public_files')
    ).filter(
        and_(File.owner_id == user_id, File.is_active == True)
    ).first()
    
    # Get file type breakdown
    type_stats = {}
    files = db.query(File.original_filename, File.file_size).filter(
        and_(File.owner_id == user_id, File.is_active == True)
    ).all()
    
    for file in files:
        file_ext = os.path.splitext(file.original_filename)[1].lower().lstrip('.')
        file_type = get_file_type_from_extension(file_ext)
        
        if file_type not in type_stats:
            type_stats[file_type] = {'count': 0, 'size': 0}
        
        type_stats[file_type]['count'] += 1
        type_stats[file_type]['size'] += file.file_size
    
    result = {
        "total_files": stats_query.total_files or 0,
        "total_size": stats_query.total_size or 0,
        "total_downloads": stats_query.total_downloads or 0,
        "public_files": stats_query.public_files or 0,
        "private_files": (stats_query.total_files or 0) - (stats_query.public_files or 0),
        "file_types": type_stats,
        "average_file_size": (stats_query.total_size or 0) // max(stats_query.total_files or 1, 1),
        "storage_used_mb": round((stats_query.total_size or 0) / (1024 * 1024), 2),
        "storage_limit_mb": settings.MAX_FILE_SIZE // (1024 * 1024)
    }
    
    # Cache for 5 minutes
    file_cache[cache_key] = result
    return result

# ================================
# MAINTENANCE & CLEANUP
# ================================

async def cleanup_expired_files_optimized(db: Session) -> Dict[str, Any]:
    """Optimized cleanup of expired files"""
    current_time = datetime.utcnow()
    
    # Find expired files efficiently
    expired_files = db.query(File).filter(
        and_(
            File.is_active == True,
            File.ttl > 0,
            func.datetime(File.upload_time, f'+{File.ttl} hours') < current_time
        )
    ).all()
    
    if not expired_files:
        return {"expired_count": 0, "message": "No expired files found"}
    
    expired_count = len(expired_files)
    file_paths = [file.path for file in expired_files]
    
    # Bulk update expired files
    expired_file_ids = [file.file_id for file in expired_files]
    db.query(File).filter(File.file_id.in_(expired_file_ids)).update(
        {File.is_active: False}, synchronize_session=False
    )
    db.commit()
    
    # Clear cache for expired files
    for file in expired_files:
        cache_key = f"file_info_{file.file_id}"
        file_cache.pop(cache_key, None)
    
    # Delete physical files asynchronously
    async def cleanup_physical_files():
        deleted_count = 0
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    await safe_file_operation(os.remove, file_path)
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete expired file {file_path}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} expired files")
    
    asyncio.create_task(cleanup_physical_files())
    
    return {
        "expired_count": expired_count,
        "message": f"Successfully cleaned up {expired_count} expired files"
    }

def toggle_file_privacy_optimized(db: Session, file_id: str, user_id: int) -> File:
    """Optimized privacy toggle with cache update"""
    file = db.query(File).filter(
        and_(
            File.file_id == file_id,
            File.owner_id == user_id,
            File.is_active == True
        )
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Toggle privacy
    file.is_public = not file.is_public
    db.commit()
    
    # Update cache
    cache_key = f"file_info_{file_id}"
    file_cache[cache_key] = file
    
    # Clear user stats cache to force refresh
    user_stats_key = f"user_stats_{user_id}"
    file_cache.pop(user_stats_key, None)
    
    return file

# ================================
# DEFINE EXPORTED FUNCTIONS
# ================================

# Define all exportable functions
__all__ = [
    'ensure_upload_dir',
    'validate_file_comprehensive', 
    'save_file_ultra_fast',
    'save_file_sync_optimized',
    'get_file_info_cached',
    'get_file_path_optimized',
    'get_user_files_optimized',
    'delete_file_optimized',
    'delete_all_user_files_optimized',
    'get_file_preview_optimized',
    'get_user_stats_comprehensive',
    'cleanup_expired_files_optimized',
    'toggle_file_privacy_optimized',
    'FileServiceError'
]

# ================================
# LEGACY COMPATIBILITY
# ================================

# Keep old function names for compatibility
save_file = save_file_sync_optimized
get_file_path = get_file_path_optimized
get_file_info = get_file_info_cached
get_user_files = get_user_files_optimized
delete_file = delete_file_optimized
delete_all_user_files = delete_all_user_files_optimized
get_file_preview = get_file_preview_optimized
get_file_stats = get_user_stats_comprehensive
cleanup_expired_files = cleanup_expired_files_optimized
toggle_file_privacy = toggle_file_privacy_optimized

# Add missing function names that might be called elsewhere
save_file_async = save_file_ultra_fast  # Async version
save_file_sync = save_file_sync_optimized  # Sync version

# For maximum compatibility, add all possible function name variations
async def save_file_async_legacy(
    db: Session, 
    file: UploadFile, 
    ttl: int, 
    owner_id: int, 
    is_public: bool = False,
    background_tasks: Optional[BackgroundTasks] = None
) -> File:
    """Legacy async save function for backward compatibility"""
    return await save_file_ultra_fast(db, file, ttl, owner_id, is_public, background_tasks)

# Add compatibility functions to __all__
__all__.extend([
    'save_file_async',
    'save_file_sync',
    'save_file_async_legacy',
    'save_file',
    'get_file_path',
    'get_file_info',
    'get_user_files',
    'delete_file',
    'delete_all_user_files',
    'get_file_preview',
    'get_file_stats',
    'cleanup_expired_files',
    'toggle_file_privacy'
])

def __getattr__(name):
    """Handle missing attribute calls for debugging"""
    if name == 'save_file_async':
        return save_file_ultra_fast
    elif name in ['save_file', 'save_file_sync']:
        return save_file_sync_optimized
    else:
        available_functions = [func for func in __all__ if not func.startswith('_')]
        raise AttributeError(
            f"module 'file_service' has no attribute '{name}'. "
            f"Available functions: {', '.join(available_functions[:10])}..."
        )
