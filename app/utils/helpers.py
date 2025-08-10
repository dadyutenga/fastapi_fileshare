import uuid
import hashlib
import secrets
import time
from typing import Optional

def generate_file_id() -> str:
    """Generate a unique file ID using UUID4"""
    return str(uuid.uuid4())

def generate_secure_hash(data: str) -> str:
    """Generate SHA-256 hash for secure operations (replaces MD5)"""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def generate_upload_id(filename: str, file_size: int) -> str:
    """Generate a unique upload ID using SHA-256 (replaces MD5)"""
    # Include timestamp and random data for uniqueness
    random_data = secrets.token_hex(16)
    data = f"{filename}_{file_size}_{time.time()}_{random_data}"
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> Optional[str]:
    """Calculate SHA-256 hash of a file for integrity checking"""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        print(f"Error calculating file hash: {e}")
        return None

def format_bytes(bytes_value: int) -> str:
    """Format bytes into human readable format"""
    if bytes_value == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(bytes_value)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

def get_user_upload_directory(user_id: int) -> str:
    """Get user-specific upload directory path"""
    from app.core.config import settings
    import os
    
    user_dir = os.path.join(settings.UPLOAD_DIR, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_temp_directory(user_id: int) -> str:
    """Get user-specific temporary directory for chunked uploads"""
    from app.core.config import settings
    import os
    
    temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_chunks", f"user_{user_id}")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir
