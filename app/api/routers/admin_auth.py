"""
Admin Authentication Routes
Completely separate from regular user authentication
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime, timedelta
import jwt

from app.api.deps import get_db
from app.db.admin_models import Admin, AdminRole
from app.schemas.admin import AdminCreate, AdminLogin, AdminToken, AdminProfile
from app.services.admin_auth_service import AdminAuthService
from app.core.security import create_access_token
from app.core.config import settings

# Remove the prefix here since it's added in main.py
router = APIRouter(tags=["admin-auth"])
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request}
    )

@router.post("/login", response_model=AdminToken)
async def admin_login_api(
    admin_data: AdminLogin,
    db: Session = Depends(get_db)
):
    """Admin API login"""
    admin = AdminAuthService.authenticate_admin(
        db, admin_data.admin_username, admin_data.password
    )
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create access token with admin type
    access_token = create_access_token(
        data={"sub": admin.admin_username, "type": "admin"}
    )
    
    # Get admin permissions
    permissions = [perm.value for perm in admin.role.value if admin.has_permission(perm)]
    
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
    """Admin web login"""
    try:
        admin = AdminAuthService.authenticate_admin(
            db, admin_username, password
        )
        
        if not admin:
            return templates.TemplateResponse(
                "admin/login.html",
                {
                    "request": request, 
                    "error": "Invalid username or password"
                }
            )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": admin.admin_username, "type": "admin"}
        )
        
        # Redirect to admin dashboard
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
        response.set_cookie(
            key="admin_token", 
            value=access_token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        return response
        
    except Exception as e:
        return templates.TemplateResponse(
            "admin/login.html",
            {
                "request": request, 
                "error": f"Login failed: {str(e)}"
            }
        )

@router.post("/logout")
async def admin_logout():
    """Admin logout"""
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_token")
    return response