import uuid
import hashlib
import os
from pathlib import Path
from app.core.config import settings

def generate_file_id():
    """Generate unique file ID using UUID4"""
    return str(uuid.uuid4())

def generate_secure_hash(data: str) -> str:
    """Generate SHA-256 hash instead of MD5"""
    return hashlib.sha256(data.encode()).hexdigest()

def get_user_upload_path(user_id: int) -> str:
    """Get user-specific upload directory"""
    user_folder = Path(settings.UPLOAD_DIR) / "users" / str(user_id)
    user_folder.mkdir(parents=True, exist_ok=True)
    return str(user_folder)

def get_file_path_for_user(user_id: int, filename: str) -> str:
    """Get full file path for user"""
    user_folder = get_user_upload_path(user_id)
    return os.path.join(user_folder, filename)
