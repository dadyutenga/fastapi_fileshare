"""
Chunked file upload handler for large files - Updated with user folders and SHA-256
"""
import os
import json
import hashlib
import time
import secrets
from typing import Optional, Dict, Any
from fastapi import HTTPException
from app.core.config import settings
from app.utils.helpers import get_user_temp_directory, generate_upload_id

class ChunkedUploadManager:
    def __init__(self):
        self.base_temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_chunks")
        if not os.path.exists(self.base_temp_dir):
            os.makedirs(self.base_temp_dir)
    
    def get_user_temp_dir(self, user_id: int) -> str:
        """Get user-specific temp directory"""
        return get_user_temp_directory(user_id)
    
    def get_chunk_path(self, upload_id: str, chunk_number: int, user_id: int) -> str:
        """Get the path for a specific chunk in user's temp directory"""
        user_temp_dir = self.get_user_temp_dir(user_id)
        return os.path.join(user_temp_dir, f"{upload_id}_chunk_{chunk_number}")
    
    def get_upload_info_path(self, upload_id: str, user_id: int) -> str:
        """Get the path for upload metadata in user's temp directory"""
        user_temp_dir = self.get_user_temp_dir(user_id)
        return os.path.join(user_temp_dir, f"{upload_id}_info.json")

    def save_chunk(self, upload_id: str, chunk_number: int, chunk_data: bytes, user_id: int) -> bool:
        """Save a chunk to disk in user's temp directory"""
        try:
            chunk_path = self.get_chunk_path(upload_id, chunk_number, user_id)
            with open(chunk_path, 'wb') as f:
                f.write(chunk_data)
            return True
        except Exception as e:
            print(f"Error saving chunk {chunk_number} for upload {upload_id}: {e}")
            return False

    def save_upload_info(self, upload_id: str, filename: str, total_chunks: int, file_size: int, user_id: int) -> bool:
        """Save upload metadata as JSON in user's temp directory"""
        try:
            info_path = self.get_upload_info_path(upload_id, user_id)
            info_data = {
                "filename": filename,
                "total_chunks": total_chunks,
                "file_size": file_size,
                "user_id": user_id,
                "created_at": time.time()
            }
            with open(info_path, 'w') as f:
                json.dump(info_data, f)
            return True
        except Exception as e:
            print(f"Error saving upload info for {upload_id}: {e}")
            return False

    def get_upload_info(self, upload_id: str, user_id: int) -> Optional[tuple]:
        """Get upload metadata from user's temp directory"""
        try:
            info_path = self.get_upload_info_path(upload_id, user_id)
            if not os.path.exists(info_path):
                return None
            
            with open(info_path, 'r') as f:
                info_data = json.load(f)
                return (info_data["filename"], info_data["total_chunks"], info_data["file_size"])
        except Exception as e:
            print(f"Error reading upload info for {upload_id}: {e}")
            return None

    def is_upload_complete(self, upload_id: str, user_id: int) -> bool:
        """Check if all chunks have been uploaded"""
        try:
            upload_info = self.get_upload_info(upload_id, user_id)
            if not upload_info:
                return False
            
            filename, total_chunks, file_size = upload_info
            
            # Check if all chunk files exist
            for i in range(total_chunks):
                chunk_path = self.get_chunk_path(upload_id, i, user_id)
                if not os.path.exists(chunk_path):
                    return False
            
            return True
        except Exception as e:
            print(f"Error checking upload completion for {upload_id}: {e}")
            return False

    def assemble_file(self, upload_id: str, user_id: int) -> str:
        """Assemble all chunks into the final file in user's temp directory"""
        try:
            upload_info = self.get_upload_info(upload_id, user_id)
            if not upload_info:
                raise HTTPException(status_code=400, detail="Upload info not found")
            
            filename, total_chunks, expected_size = upload_info
            user_temp_dir = self.get_user_temp_dir(user_id)
            temp_final_path = os.path.join(user_temp_dir, f"{upload_id}_assembled_{filename}")
            
            # Assemble chunks
            actual_size = 0
            with open(temp_final_path, 'wb') as final_file:
                for i in range(total_chunks):
                    chunk_path = self.get_chunk_path(upload_id, i, user_id)
                    if not os.path.exists(chunk_path):
                        raise HTTPException(status_code=400, detail=f"Missing chunk {i}")
                    
                    with open(chunk_path, 'rb') as chunk_file:
                        chunk_data = chunk_file.read()
                        final_file.write(chunk_data)
                        actual_size += len(chunk_data)
            
            # Verify file size
            if actual_size != expected_size:
                os.remove(temp_final_path)
                raise HTTPException(status_code=400, detail=f"File size mismatch: expected {expected_size}, got {actual_size}")
            
            return temp_final_path
            
        except Exception as e:
            # Clean up on error
            user_temp_dir = self.get_user_temp_dir(user_id)
            temp_final_path = os.path.join(user_temp_dir, f"{upload_id}_assembled_{filename}")
            if os.path.exists(temp_final_path):
                try:
                    os.remove(temp_final_path)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Assembly failed: {str(e)}")

    def cleanup_upload(self, upload_id: str, user_id: int):
        """Clean up temporary files for an upload in user's temp directory"""
        try:
            upload_info = self.get_upload_info(upload_id, user_id)
            if upload_info:
                filename, total_chunks, file_size = upload_info
                
                # Remove chunk files
                for i in range(total_chunks):
                    chunk_path = self.get_chunk_path(upload_id, i, user_id)
                    if os.path.exists(chunk_path):
                        try:
                            os.remove(chunk_path)
                        except:
                            pass
                
                # Remove assembled temp file if it exists
                user_temp_dir = self.get_user_temp_dir(user_id)
                temp_final_path = os.path.join(user_temp_dir, f"{upload_id}_assembled_{filename}")
                if os.path.exists(temp_final_path):
                    try:
                        os.remove(temp_final_path)
                    except:
                        pass
                
                # Remove info file
                info_path = self.get_upload_info_path(upload_id, user_id)
                if os.path.exists(info_path):
                    try:
                        os.remove(info_path)
                    except:
                        pass
        except Exception as e:
            print(f"Error cleaning up upload {upload_id}: {e}")

    def generate_upload_id(self, filename: str, file_size: int) -> str:
        """Generate a unique upload ID using SHA-256 (replaces MD5)"""
        return generate_upload_id(filename, file_size)

# Global instance
chunked_upload_manager = ChunkedUploadManager()
