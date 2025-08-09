from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List

from app.api.deps import get_current_active_user, get_db
from app.db.models import User, File
from app.schemas.user import User as UserSchema
from app.schemas.file import FileResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def check_admin_access(current_user: User):
    """Check if user has admin privileges"""
    # For now, we'll check a hardcoded admin user
    # In a real implementation, this would check an is_admin field
    if current_user.username != "admin":  # Simple check for demo
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    return True

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Admin dashboard"""
    check_admin_access(current_user)
    
    # Get statistics
    total_users = db.query(User).count()
    total_files = db.query(File).count()
    total_file_size = db.query(File).filter(File.is_active == True).with_entities(
        db.func.sum(File.file_size)
    ).scalar() or 0
    
    # Get recent users
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    
    # Get recent files
    recent_files = db.query(File).order_by(File.upload_time.desc()).limit(10).all()
    
    return templates.TemplateResponse(
        "admin/dashboard.html", {
            "request": request,
            "user": current_user,
            "total_users": total_users,
            "total_files": total_files,
            "total_file_size": total_file_size,
            "recent_users": recent_users,
            "recent_files": recent_files
        }
    )

@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all users"""
    check_admin_access(current_user)
    
    users = db.query(User).order_by(User.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "admin/users.html", {
            "request": request,
            "user": current_user,
            "users": users
        }
    )

@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """View user details"""
    check_admin_access(current_user)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's files
    files = db.query(File).filter(File.owner_id == user_id).order_by(File.upload_time.desc()).all()
    
    return templates.TemplateResponse(
        "admin/user_detail.html", {
            "request": request,
            "user": current_user,
            "target_user": user,
            "files": files
        }
    )

@router.post("/admin/users/{user_id}/toggle-active")
async def admin_toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Toggle user active status"""
    check_admin_access(current_user)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    user.is_active = not user.is_active
    db.commit()
    
    return {"success": True, "message": f"User {'activated' if user.is_active else 'deactivated'}"}

@router.get("/admin/files", response_class=HTMLResponse)
async def admin_files_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all files"""
    check_admin_access(current_user)
    
    files = db.query(File).order_by(File.upload_time.desc()).all()
    
    return templates.TemplateResponse(
        "admin/files.html", {
            "request": request,
            "user": current_user,
            "files": files
        }
    )

@router.post("/admin/files/{file_id}/delete")
async def admin_delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete any file (admin override)"""
    check_admin_access(current_user)
    
    file = db.query(File).filter(File.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Soft delete
    file.is_active = False
    db.commit()
    
    return {"success": True, "message": "File deleted successfully"}