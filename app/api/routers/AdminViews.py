"""
Admin Panel Views and Management
Completely separate from regular user system
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List

from app.api.deps import get_db
from app.api.admin_deps import (
    get_current_admin, 
    require_super_admin,
    require_user_management,
    require_file_management,
    require_system_management,
    get_client_ip,
    get_user_agent
)
from app.db.admin_models import Admin, AdminPermission
from app.db.models import User, File as FileModel
from app.schemas.admin import AdminDashboardStats, AdminLogEntry
from app.services.admin_auth_service import AdminAuthService, AdminUserManagementService

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Admin dashboard"""
    stats = AdminAuthService.get_dashboard_stats(db)
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "admin": current_admin,
            "stats": stats,
            "admin_permission": AdminPermission  # Add this line
        }
    )

@router.get("/dashboard/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get dashboard statistics as JSON"""
    return AdminAuthService.get_dashboard_stats(db)

@router.get("/users", response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_user_management),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    plan_filter: Optional[str] = Query("all")
):
    """Admin users management page"""
    limit = 20
    offset = (page - 1) * limit
    
    result = AdminUserManagementService.get_all_users(
        db, current_admin, limit, offset, search, plan_filter
    )
    
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "admin": current_admin,
            "users": result["users"],
            "total": result["total"],
            "page": result["page"],
            "pages": result["pages"],
            "search": search,
            "plan_filter": plan_filter,
            "admin_permission": AdminPermission  # Add this line
        }
    )

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_user_management)
):
    """Admin user detail page"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's files
    user_files = db.query(FileModel).filter(
        FileModel.owner_id == user_id
    ).order_by(FileModel.upload_time.desc()).limit(10).all()
    
    return templates.TemplateResponse(
        "admin/user_detail.html",
        {
            "request": request,
            "admin": current_admin,
            "user": user,
            "user_files": user_files,
            "admin_permission": AdminPermission  # Add this line
        }
    )

@router.post("/users/{user_id}/suspend")
async def admin_suspend_user(
    request: Request,
    user_id: str,
    reason: str = Form(""),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_user_management)
):
    """Suspend/unsuspend user"""
    ip_address = get_client_ip(request)
    
    user = AdminUserManagementService.suspend_user(db, current_admin, user_id, reason)
    
    return JSONResponse(content={
        "success": True,
        "message": f"User {'activated' if user.is_active else 'suspended'} successfully",
        "is_active": user.is_active
    })

@router.delete("/users/{user_id}")
async def admin_delete_user(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_user_management)
):
    """Delete user and all their files (dangerous operation)"""
    # Require explicit permission check for deletion
    AdminAuthService.require_permission(current_admin, AdminPermission.DELETE_USERS)
    
    result = AdminUserManagementService.delete_user_and_files(db, current_admin, user_id)
    
    return JSONResponse(content=result)

@router.get("/files", response_class=HTMLResponse)
async def admin_files_list(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_file_management),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None)
):
    """Admin files management page"""
    limit = 50
    offset = (page - 1) * limit
    
    query = db.query(FileModel).filter(FileModel.is_active == True)
    
    if search:
        query = query.filter(FileModel.original_filename.contains(search))
    
    total = query.count()
    files = query.order_by(FileModel.upload_time.desc()).offset(offset).limit(limit).all()
    
    AdminAuthService.log_admin_action(
        db, current_admin.id, "VIEW_FILES", "FILE", None,
        f"Viewed files list (search: {search})"
    )
    
    return templates.TemplateResponse(
        "admin/files.html",
        {
            "request": request,
            "admin": current_admin,
            "files": files,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
            "search": search,
            "admin_permission": AdminPermission  # Add this line
        }
    )

@router.delete("/files/{file_id}")
async def admin_delete_file(
    request: Request,
    file_id: str,
    reason: str = Form(""),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_file_management)
):
    """Delete any file (admin override)"""
    AdminAuthService.require_permission(current_admin, AdminPermission.DELETE_ANY_FILE)
    
    file = db.query(FileModel).filter(FileModel.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    filename = file.original_filename
    owner_username = file.owner.username if file.owner else "unknown"
    
    # Soft delete
    file.is_active = False
    db.commit()
    
    AdminAuthService.log_admin_action(
        db, current_admin.id, "DELETE_FILE", "FILE", file_id,
        f"Deleted file: {filename} owned by {owner_username}. Reason: {reason}"
    )
    
    return JSONResponse(content={
        "success": True,
        "message": f"File '{filename}' deleted successfully"
    })

@router.get("/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    action: Optional[str] = Query(None)
):
    """Admin activity logs"""
    limit = 50
    offset = (page - 1) * limit
    
    logs = AdminAuthService.get_admin_logs(db, action=action, limit=limit, offset=offset)
    
    return templates.TemplateResponse(
        "admin/logs.html",
        {
            "request": request,
            "admin": current_admin,
            "logs": logs,
            "page": page,
            "action_filter": action,
            "admin_permission": AdminPermission  # Add this line
        }
    )

@router.get("/logs/api", response_model=List[AdminLogEntry])
async def get_admin_logs_api(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    action: Optional[str] = Query(None),
    admin_id: Optional[str] = Query(None)
):
    """Get admin logs as JSON"""
    return AdminAuthService.get_admin_logs(db, admin_id, action, limit, offset)

@router.get("/admins", response_class=HTMLResponse)
async def admin_management(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin)
):
    """Admin management page (super admin only)"""
    admins = db.query(Admin).order_by(Admin.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "admin/admin_management.html",
        {
            "request": request,
            "admin": current_admin,
            "admins": admins,
            "admin_permission": AdminPermission  # Add this line
        }
    )

@router.post("/admins/{admin_id}/toggle-active")
async def toggle_admin_active(
    admin_id: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin)
):
    """Toggle admin active status (super admin only)"""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    if admin.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    admin.is_active = not admin.is_active
    db.commit()
    
    AdminAuthService.log_admin_action(
        db, current_admin.id, 
        "ACTIVATE_ADMIN" if admin.is_active else "DEACTIVATE_ADMIN",
        "ADMIN", admin_id,
        f"{'Activated' if admin.is_active else 'Deactivated'} admin: {admin.admin_username}"
    )
    
    return JSONResponse(content={
        "success": True,
        "message": f"Admin {'activated' if admin.is_active else 'deactivated'} successfully",
        "is_active": admin.is_active
    })