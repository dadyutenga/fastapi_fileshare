import uuid
import hashlib
import os
import time
from pathlib import Path
from app.core.config import settings

def generate_file_id():
    """Generate unique file ID using UUID4"""
    return str(uuid.uuid4())

def generate_secure_hash(data: str) -> str:
    """Generate SHA-256 hash instead of MD5"""
    return hashlib.sha256(data.encode()).hexdigest()

def generate_upload_id(filename: str, file_size: int) -> str:
    """Generate a unique upload ID using SHA-256 (replaces MD5)"""
    data = f"{filename}_{file_size}_{time.time()}"
    return hashlib.sha256(data.encode()).hexdigest()

def get_user_upload_path(user_id: int) -> str:
    """Get user-specific upload directory"""
    user_folder = Path(settings.UPLOAD_DIR) / "users" / str(user_id)
    user_folder.mkdir(parents=True, exist_ok=True)
    return str(user_folder)

def get_user_temp_directory(user_id: int) -> str:
    """Return the temp chunk upload directory for a user."""
    import os
    from app.core.config import settings
    return os.path.join(settings.UPLOAD_DIR, "temp_chunks", str(user_id))

def get_file_path_for_user(user_id: int, filename: str) -> str:
    """Get full file path for user"""
    user_folder = get_user_upload_path(user_id)
    return os.path.join(user_folder, filename)

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file for integrity checking"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        print(f"Error calculating hash for {file_path}: {e}")
        return ""

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"
