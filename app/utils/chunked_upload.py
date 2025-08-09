"""
Chunked file upload handler for large files
"""
import os
import json
import hashlib
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException
from app.core.config import settings

class ChunkedUploadManager:
    def __init__(self):
        self.temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_chunks")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
    
    def get_chunk_path(self, upload_id: str, chunk_number: int) -> str:
        """Get the path for a specific chunk"""
        return os.path.join(self.temp_dir, f"{upload_id}_chunk_{chunk_number}")
    
    def get_upload_info_path(self, upload_id: str) -> str:
        """Get the path for upload metadata"""
        return os.path.join(self.temp_dir, f"{upload_id}_info.json")
    
    def save_chunk(self, upload_id: str, chunk_number: int, chunk_data: bytes) -> bool:
        """Save a chunk to disk"""
        try:
            chunk_path = self.get_chunk_path(upload_id, chunk_number)
            with open(chunk_path, 'wb') as f:
                f.write(chunk_data)
            return True
        except Exception as e:
            print(f"Error saving chunk {chunk_number} for upload {upload_id}: {e}")
            return False
    
    def save_upload_info(self, upload_id: str, filename: str, total_chunks: int, file_size: int) -> bool:
        """Save upload metadata as JSON"""
        try:
            info_path = self.get_upload_info_path(upload_id)
            info_data = {
                "filename": filename,
                "total_chunks": total_chunks,
                "file_size": file_size,
                "created_at": time.time()
            }
            with open(info_path, 'w') as f:
                json.dump(info_data, f)
            return True
        except Exception as e:
            print(f"Error saving upload info for {upload_id}: {e}")
            return False
    
    def get_upload_info(self, upload_id: str) -> Optional[tuple]:
        """Get upload metadata"""
        try:
            info_path = self.get_upload_info_path(upload_id)
            if not os.path.exists(info_path):
                return None
            
            with open(info_path, 'r') as f:
                info_data = json.load(f)
                return (
                    info_data["filename"], 
                    info_data["total_chunks"], 
                    info_data["file_size"]
                )
        except Exception as e:
            print(f"Error reading upload info for {upload_id}: {e}")
            return None
    
    def is_upload_complete(self, upload_id: str) -> bool:
        """Check if all chunks have been uploaded"""
        upload_info = self.get_upload_info(upload_id)
        if not upload_info:
            return False
        
        filename, total_chunks, file_size = upload_info
        
        # Check if all chunk files exist
        for i in range(total_chunks):
            chunk_path = self.get_chunk_path(upload_id, i)
            if not os.path.exists(chunk_path):
                return False
        
        return True
    
    def assemble_file(self, upload_id: str) -> str:
        """Assemble all chunks into the final file"""
        upload_info = self.get_upload_info(upload_id)
        if not upload_info:
            raise HTTPException(status_code=400, detail="Upload info not found")
        
        filename, total_chunks, expected_size = upload_info
        
        # Create temporary assembled file path (not final location)
        temp_final_path = os.path.join(self.temp_dir, f"{upload_id}_assembled_{filename}")
        
        try:
            # Assemble chunks
            actual_size = 0
            with open(temp_final_path, 'wb') as final_file:
                for i in range(total_chunks):
                    chunk_path = self.get_chunk_path(upload_id, i)
                    if not os.path.exists(chunk_path):
                        raise HTTPException(status_code=400, detail=f"Chunk {i} missing")
                    
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
            if os.path.exists(temp_final_path):
                try:
                    os.remove(temp_final_path)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Assembly failed: {str(e)}")
    
    def cleanup_upload(self, upload_id: str):
        """Clean up temporary files for an upload"""
        try:
            upload_info = self.get_upload_info(upload_id)
            if upload_info:
                filename, total_chunks, file_size = upload_info
                
                # Remove chunk files
                for i in range(total_chunks):
                    chunk_path = self.get_chunk_path(upload_id, i)
                    if os.path.exists(chunk_path):
                        try:
                            os.remove(chunk_path)
                        except:
                            pass
                
                # Remove assembled temp file if it exists
                temp_final_path = os.path.join(self.temp_dir, f"{upload_id}_assembled_{filename}")
                if os.path.exists(temp_final_path):
                    try:
                        os.remove(temp_final_path)
                    except:
                        pass
                
                # Remove info file
                info_path = self.get_upload_info_path(upload_id)
                if os.path.exists(info_path):
                    try:
                        os.remove(info_path)
                    except:
                        pass
        except Exception as e:
            print(f"Error cleaning up upload {upload_id}: {e}")
    
    def generate_upload_id(self, filename: str, file_size: int) -> str:
        """Generate a unique upload ID"""
        data = f"{filename}_{file_size}_{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()

# Global instance
chunked_upload_manager = ChunkedUploadManager()
