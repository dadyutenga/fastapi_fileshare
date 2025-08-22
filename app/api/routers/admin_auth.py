"""
Admin Authentication Router
Separate from regular user authentication
"""
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.security import create_access_token
from app.api.deps import get_db
from app.api.admin_deps import get_current_admin, get_client_ip, get_user_agent, require_super_admin
from app.db.admin_models import Admin
from app.schemas.admin import AdminLogin, AdminCreate, AdminToken, AdminProfile
from app.services.admin_auth_service import AdminAuthService
from app.schemas.token import Token

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
templates = Jinja2Templates(directory="templates")

@router.post("/login", response_model=AdminToken)
async def admin_login_api(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Admin login via API"""
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    admin = AdminAuthService.authenticate_admin(
        db, form_data.username, form_data.password, ip_address
    )
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token with admin type
    access_token = create_access_token(
        data={"sub": admin.admin_username, "type": "admin"}
    )
    
    # Get admin permissions
    from app.db.admin_models import AdminPermission
    permissions = [perm for perm in AdminPermission if admin.has_permission(perm)]
    
    admin_profile = AdminProfile(
        id=admin.id,
        admin_username=admin.admin_username,
        admin_email=admin.admin_email,
        full_name=admin.full_name,
        role=admin.role,
        is_active=admin.is_active,
        is_super_admin=admin.is_super_admin,
        permissions=permissions,
        created_at=admin.created_at,
        last_login=admin.last_login,
        last_activity=admin.last_activity
    )
    
    return AdminToken(
        access_token=access_token,
        token_type="bearer",
        admin_info=admin_profile
    )

@router.post("/login-web", response_class=HTMLResponse)
async def admin_login_web(
    request: Request,
    admin_username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Admin login via web form"""
    try:
        ip_address = get_client_ip(request)
        
        admin = AdminAuthService.authenticate_admin(
            db, admin_username, password, ip_address
        )
        
        if not admin:
            return templates.TemplateResponse(
                "admin/login.html",
                {
                    "request": request,
                    "error": "Invalid admin credentials",
                    "admin_username": admin_username
                }
            )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": admin.admin_username, "type": "admin"}
        )
        
        # Redirect to admin dashboard
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
        response.set_cookie(
            key="admin_access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=3600,  # 1 hour for admin sessions
            samesite="lax",
            secure=False  # Set to True in production with HTTPS
        )
        
        return response
        
    except HTTPException as e:
        return templates.TemplateResponse(
            "admin/login.html",
            {
                "request": request,
                "error": e.detail,
                "admin_username": admin_username
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "admin/login.html",
            {
                "request": request,
                "error": f"Login failed: {str(e)}",
                "admin_username": admin_username
            }
        )

@router.post("/create-admin", response_model=AdminProfile)
async def create_admin(
    admin_data: AdminCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin)
):
    """Create new admin (super admin only)"""
    new_admin = AdminAuthService.create_admin(db, admin_data, current_admin.id)
    
    # Get permissions for response
    from app.db.admin_models import AdminPermission
    permissions = [perm for perm in AdminPermission if new_admin.has_permission(perm)]
    
    return AdminProfile(
        id=new_admin.id,
        admin_username=new_admin.admin_username,
        admin_email=new_admin.admin_email,
        full_name=new_admin.full_name,
        role=new_admin.role,
        is_active=new_admin.is_active,
        is_super_admin=new_admin.is_super_admin,
        permissions=permissions,
        created_at=new_admin.created_at,
        last_login=new_admin.last_login,
        last_activity=new_admin.last_activity
    )

@router.get("/profile", response_model=AdminProfile)
async def get_admin_profile(
    current_admin: Admin = Depends(get_current_admin)
):
    """Get current admin profile"""
    from app.db.admin_models import AdminPermission
    permissions = [perm for perm in AdminPermission if current_admin.has_permission(perm)]
    
    return AdminProfile(
        id=current_admin.id,
        admin_username=current_admin.admin_username,
        admin_email=current_admin.admin_email,
        full_name=current_admin.full_name,
        role=current_admin.role,
        is_active=current_admin.is_active,
        is_super_admin=current_admin.is_super_admin,
        permissions=permissions,
        created_at=current_admin.created_at,
        last_login=current_admin.last_login,
        last_activity=current_admin.last_activity
    )

@router.post("/logout")
async def admin_logout():
    """Admin logout"""
    response = JSONResponse(content={"message": "Successfully logged out"})
    response.delete_cookie(key="admin_access_token")
    return response

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request}
    )