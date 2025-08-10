from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, BackgroundTasks, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
import os
import mimetypes
import asyncio
from datetime import datetime

from app.api.deps import get_current_active_user, get_current_user_optional, get_db
from app.db.models import User, File as FileModel
from app.services import file_service
from app.schemas.file import FilePreview
from app.utils.chunked_upload import chunked_upload_manager
from app.utils.helpers import generate_file_id
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.post("/upload", response_class=HTMLResponse)
async def upload_file_from_web(
    request: Request,
    file: UploadFile = File(...),
    ttl: int = Form(0),
    is_public: str = Form("false"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload file (requires authentication) - Returns HTML response"""
    try:
        # Convert string to boolean
        is_public_bool = is_public.lower() == "true"
        
        db_file = await file_service.save_file_async(db, file, ttl, current_user.id, is_public_bool)
        download_link = request.url_for("download_file", file_id=db_file.file_id)
        preview_link = request.url_for("preview_file", file_id=db_file.file_id)
        return templates.TemplateResponse(
            "upload_success.html", {
                "request": request, 
                "download_link": str(download_link),
                "preview_link": str(preview_link),
                "file": db_file,
                "user": current_user
            }
        )
    except HTTPException as e:
        return templates.TemplateResponse(
            "error.html", {
                "request": request, 
                "error": e.detail,
                "user": current_user
            }
        )

@router.post("/upload-api")
async def upload_file_api(
    request: Request,
    file: UploadFile = File(...),
    ttl: int = Form(0),
    is_public: str = Form("false"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload file API endpoint - Returns JSON response with improved performance"""
    try:
        # Validate file size first
        if file.size and file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Convert string to boolean
        is_public_bool = is_public.lower() == "true"
        
        # Use async file saving for better performance
        db_file = await file_service.save_file_async(db, file, ttl, current_user.id, is_public_bool)
        download_link = request.url_for("download_file", file_id=db_file.file_id)
        preview_link = request.url_for("preview_file", file_id=db_file.file_id)
        
        return JSONResponse({
            "success": True,
            "message": "File uploaded successfully",
            "file_id": db_file.file_id,
            "download_url": str(download_link),
            "preview_url": str(preview_link),
            "filename": db_file.original_filename,
            "file_size": db_file.file_size,
            "is_public": db_file.is_public
        })
    except HTTPException as e:
        return JSONResponse({
            "success": False,
            "message": e.detail
        }, status_code=e.status_code)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"Upload failed: {str(e)}"
        }, status_code=500)

# Chunked Upload Endpoints for Large Files (Improved)
@router.post("/chunked-upload/start")
async def start_chunked_upload(
    filename: str = Form(...),
    file_size: int = Form(...),
    total_chunks: int = Form(...),
    ttl: int = Form(0),
    is_public: str = Form("false"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Start a chunked upload session with validation"""
    try:
        # Validate file size
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Validate file extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in settings.allowed_extensions_list:
            raise HTTPException(status_code=400, detail="File type not allowed")
        
        # Generate upload ID
        upload_id = chunked_upload_manager.generate_upload_id(filename, file_size)
        
        # Save upload metadata - Fixed method call
        success = chunked_upload_manager.save_upload_info(upload_id, filename, total_chunks, file_size)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save upload info")
        
        return JSONResponse({
            "upload_id": upload_id,
            "status": "started",
            "message": f"Ready to receive {total_chunks} chunks",
            "chunk_size": settings.CHUNK_SIZE
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start upload: {str(e)}")

@router.post("/chunked-upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_number: int = Form(...),
    chunk: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Upload a single chunk with improved error handling"""
    try:
        # Read chunk data
        chunk_data = await chunk.read()
        
        # Validate chunk size
        if len(chunk_data) > settings.CHUNK_SIZE + 1024:  # Allow small overhead
            raise HTTPException(status_code=413, detail="Chunk too large")
        
        # Save chunk asynchronously
        success = await asyncio.get_event_loop().run_in_executor(
            None, chunked_upload_manager.save_chunk, upload_id, chunk_number, chunk_data
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save chunk")
        
        # Check if upload is complete
        is_complete = chunked_upload_manager.is_upload_complete(upload_id)
        
        return JSONResponse({
            "chunk_number": chunk_number,
            "status": "received",
            "upload_complete": is_complete,
            "message": f"Chunk {chunk_number} uploaded successfully"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload chunk: {str(e)}")

@router.post("/chunked-upload/complete")
async def complete_chunked_upload(
    request: Request,
    upload_id: str = Form(...),
    ttl: int = Form(0),
    is_public: str = Form("false"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Complete a chunked upload and create file record with better error handling"""
    temp_assembled_path = None
    final_file_path = None
    
    try:
        # Check if upload is complete
        if not chunked_upload_manager.is_upload_complete(upload_id):
            raise HTTPException(status_code=400, detail="Upload not complete - missing chunks")
        
        # Get upload info
        upload_info = chunked_upload_manager.get_upload_info(upload_id)
        if not upload_info:
            raise HTTPException(status_code=400, detail="Upload info not found")
        
        original_filename, total_chunks, file_size = upload_info
        
        # Assemble file - this returns a temporary path
        temp_assembled_path = chunked_upload_manager.assemble_file(upload_id)
        
        # Generate file ID and create final path
        file_id = generate_file_id()
        filename = f"{file_id}_{original_filename}"
        final_file_path = os.path.join(settings.UPLOAD_DIR, filename)
        
        # Move assembled file to final location
        if os.path.exists(temp_assembled_path):
            # Ensure upload directory exists
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            
            # Move file to final location
            import shutil
            shutil.move(temp_assembled_path, final_file_path)
        else:
            raise HTTPException(status_code=500, detail="Assembled file not found")
        
        # Determine content type
        import mimetypes
        content_type, _ = mimetypes.guess_type(original_filename)
        
        # Convert string to boolean
        is_public_bool = is_public.lower() == "true"
        
        # Create database record
        db_file = FileModel(
            file_id=file_id,
            filename=filename,
            original_filename=original_filename,
            path=final_file_path,
            file_size=file_size,
            content_type=content_type,
            ttl=ttl,
            is_public=is_public_bool,
            owner_id=current_user.id
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        # Schedule cleanup of temp files in background
        background_tasks.add_task(chunked_upload_manager.cleanup_upload, upload_id)
        
        return JSONResponse({
            "status": "complete",
            "file_id": file_id,
            "download_url": str(request.url_for("download_file", file_id=file_id)),
            "preview_url": str(request.url_for("preview_file", file_id=file_id)),
            "message": "Large file uploaded successfully",
            "filename": original_filename,
            "file_size": file_size,
            "is_public": is_public_bool
        })
        
    except Exception as e:
        # Clean up on error
        print(f"Error completing chunked upload: {str(e)}")
        
        # Clean up temp assembled file
        if temp_assembled_path and os.path.exists(temp_assembled_path):
            try:
                os.remove(temp_assembled_path)
            except:
                pass
        
        # Clean up final file if it was created
        if final_file_path and os.path.exists(final_file_path):
            try:
                os.remove(final_file_path)
            except:
                pass
        
        # Clean up upload chunks
        chunked_upload_manager.cleanup_upload(upload_id)
        
        raise HTTPException(status_code=500, detail=f"Failed to complete upload: {str(e)}")

@router.delete("/chunked-upload/cancel")
async def cancel_chunked_upload(
    upload_id: str = Form(...),
    current_user: User = Depends(get_current_active_user),
):
    """Cancel a chunked upload and clean up"""
    try:
        chunked_upload_manager.cleanup_upload(upload_id)
        return JSONResponse({
            "status": "cancelled",
            "message": "Upload cancelled and cleaned up"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel upload: {str(e)}")

@router.get("/download/{file_id}", name="download_file")
def download_file(
    file_id: str, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Download file (public access for public files, authentication required for private files)"""
    # Get file info first to check if it's public
    file_info = db.query(FileModel).filter(
        FileModel.file_id == file_id, 
        FileModel.is_active == True
    ).first()
    
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    
    # If file is private, user must be authenticated and be the owner
    if not file_info.is_public:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required for private files")
        if file_info.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied - you don't own this private file")
    
    # If we get here, access is allowed
    user_id = current_user.id if current_user else None
    file_path, _ = file_service.get_file_path(db, file_id, user_id)  # <-- UNPACK the tuple here
    
    return FileResponse(
        file_path, 
        filename=file_info.original_filename,
        media_type=file_info.content_type
    )

@router.post("/delete/{file_id}", response_class=HTMLResponse)
async def delete_file(
    request: Request,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete file (user can only delete own files)"""
    try:
        file_service.delete_file(db, file_id, current_user.id)
        return RedirectResponse(url="/files", status_code=302)
    except HTTPException as e:
        return templates.TemplateResponse(
            "error.html", {
                "request": request, 
                "error": e.detail,
                "user": current_user
            }
        )

@router.post("/toggle-privacy/{file_id}", response_class=HTMLResponse)
async def toggle_file_privacy(
    request: Request,
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Toggle file privacy (public/private) - user can only toggle own files"""
    try:
        db_file = db.query(FileModel).filter(
            FileModel.file_id == file_id, 
            FileModel.owner_id == current_user.id, 
            FileModel.is_active == True
        ).first()
        
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found or access denied")
        
        # Toggle the privacy setting
        db_file.is_public = not db_file.is_public
        db.commit()
        
        return RedirectResponse(url="/files", status_code=302)
        
    except HTTPException as e:
        return templates.TemplateResponse(
            "error.html", {
                "request": request, 
                "error": e.detail,
                "user": current_user
            }
        )

@router.get("/preview/{file_id}", response_class=HTMLResponse, name="preview_file")
async def preview_file(
    request: Request, 
    file_id: str, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Preview file (public access for public files, authentication required for private files)"""
    try:
        user_id = current_user.id if current_user else None
        preview = file_service.get_file_preview(db, file_id, user_id)
        return templates.TemplateResponse(
            "preview.html", {
                "request": request, 
                "preview": preview,
                "user": current_user
            }
        )
    except HTTPException as e:
        return templates.TemplateResponse(
            "error.html", {
                "request": request, 
                "error": e.detail,
                "user": current_user
            }
        )

@router.get("/api/preview/{file_id}")
async def get_file_preview_api(
    file_id: str, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> FilePreview:
    """Get file preview data as JSON"""
    user_id = current_user.id if current_user else None
    return file_service.get_file_preview(db, file_id, user_id)

@router.post("/delete-all")
async def delete_all_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Delete all files for the current user"""
    try:
        # Get all user files
        user_files = db.query(FileModel).filter(
            FileModel.owner_id == current_user.id,
            FileModel.is_active == True
        ).all()
        
        if not user_files:
            raise HTTPException(status_code=404, detail="No files found to delete")
        
        file_count = len(user_files)
        deleted_files = []
        
        # Delete each file
        for file in user_files:
            try:
                # Soft delete from database
                file.is_active = False
                deleted_files.append(file.original_filename)
                
                # Schedule physical file deletion in background
                background_tasks.add_task(delete_physical_file, file.path)
                
            except Exception as e:
                print(f"Error deleting file {file.file_id}: {e}")
                continue
        
        # Commit all database changes
        db.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"Successfully deleted {len(deleted_files)} files",
            "deleted_count": len(deleted_files),
            "total_files": file_count,
            "deleted_files": deleted_files[:10]  # Show first 10 file names
        })
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete files: {str(e)}")

def delete_physical_file(file_path: str):
    """Helper function to delete physical file (for background tasks)"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted physical file: {file_path}")
    except Exception as e:
        print(f"Error deleting physical file {file_path}: {e}")

@router.get("/api/user-files")
async def get_user_files_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(100, ge=1, le=500),  # Pagination limit (default 100, max 500)
    offset: int = Query(0, ge=0),  # Pagination offset
    file_type: Optional[str] = Query(None),  # Filter by file type (e.g., 'image', 'video')
    search_query: Optional[str] = Query(None),  # Search by filename
) -> Dict:
    """Get list of files for the authenticated user - JSON API for mobile apps"""
    try:
        # Build the query
        query = db.query(FileModel).filter(
            FileModel.owner_id == current_user.id,
            FileModel.is_active == True
        )
        
        # Apply search filter if provided
        if search_query:
            query = query.filter(
                FileModel.original_filename.ilike(f"%{search_query}%")
            )
        
        # Apply file type filter if provided
        if file_type:
            if file_type.lower() == 'image':
                query = query.filter(
                    FileModel.content_type.like('image/%')
                )
            elif file_type.lower() == 'video':
                query = query.filter(
                    FileModel.content_type.like('video/%')
                )
            elif file_type.lower() == 'document':
                query = query.filter(
                    FileModel.content_type.in_([
                        'application/pdf',
                        'application/msword',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'text/plain'
                    ])
                )
            elif file_type.lower() == 'audio':
                query = query.filter(
                    FileModel.content_type.like('audio/%')
                )
        
        # Get total count for pagination info
        total_count = query.count()
        
        # Apply pagination and get results
        files = query.order_by(FileModel.created_at.desc()).offset(offset).limit(limit).all()
        
        # Build response data
        file_list = []
        for file in files:
            # Check if file is expired
            is_expired = file.is_expired() if hasattr(file, 'is_expired') else False
            
            # Categorize file type
            file_category = categorize_file_type(file.content_type or '')
            
            # Format file size
            formatted_size = format_file_size(file.file_size)
            
            file_data = {
                "file_id": file.file_id,
                "filename": file.original_filename,
                "file_size": file.file_size,
                "formatted_size": formatted_size,
                "content_type": file.content_type,
                "file_category": file_category,
                "is_public": file.is_public,
                "is_expired": is_expired,
                "upload_date": file.created_at.isoformat() if file.created_at else None,
                "ttl": file.ttl,
                "download_url": f"/api/files/download/{file.file_id}",
                "preview_url": f"/api/files/preview/{file.file_id}",
            }
            file_list.append(file_data)
        
        # Calculate pagination info
        has_next = (offset + limit) < total_count
        has_previous = offset > 0
        
        return JSONResponse({
            "success": True,
            "files": file_list,
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_next": has_next,
                "has_previous": has_previous,
                "current_page": (offset // limit) + 1,
                "total_pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "file_type": file_type,
                "search_query": search_query
            },
            "user_info": {
                "user_id": current_user.id,
                "username": current_user.username if hasattr(current_user, 'username') else None
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user files: {str(e)}")


def categorize_file_type(content_type: str) -> str:
    """Helper function to categorize file types"""
    if not content_type:
        return "unknown"
    
    content_type = content_type.lower()
    
    if content_type.startswith('image/'):
        return "image"
    elif content_type.startswith('video/'):
        return "video"
    elif content_type.startswith('audio/'):
        return "audio"
    elif content_type in [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain',
        'text/csv'
    ]:
        return "document"
    elif content_type.startswith('text/'):
        return "text"
    elif content_type in ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed']:
        return "archive"
    else:
        return "other"


def format_file_size(size_bytes: int) -> str:
    """Helper function to format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"