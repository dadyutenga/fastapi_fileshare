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
    require_system_management
)
from app.db.admin_models import Admin, AdminPermission
from app.db.models import User
from app.schemas.admin import AdminDashboardStats
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
    
    return templates.TemplateResponse(
        "admin/user_detail.html",
        {
            "request": request,
            "admin": current_admin,
            "user": user,
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
    
    return JSONResponse(content={
        "success": True,
        "message": f"Admin {'activated' if admin.is_active else 'deactivated'} successfully",
        "is_active": admin.is_active
    })