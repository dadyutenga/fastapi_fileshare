"""
Admin-specific dependencies for FastAPI
Completely separate from regular user dependencies
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import jwt
from datetime import datetime

from app.core.config import settings
from app.api.deps import get_db
from app.db.admin_models import Admin, AdminPermission
from app.services.admin_auth_service import AdminAuthService

# Admin-specific security scheme (optional for API)
admin_security = HTTPBearer(scheme_name="AdminBearer", auto_error=False)

def get_admin_token_from_cookie_or_header(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(admin_security)
) -> Optional[str]:
    """Get admin token from cookie or Authorization header"""
    # First try cookie (for web interface)
    admin_token = request.cookies.get("admin_token")
    if admin_token:
        return admin_token
    
    # Then try Authorization header (for API)
    if credentials:
        return credentials.credentials
    
    return None

def get_current_admin(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_admin_token_from_cookie_or_header)
) -> Admin:
    """Get current authenticated admin"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        admin_username: str = payload.get("sub")
        admin_type: str = payload.get("type")  # Should be "admin"
        
        if admin_username is None or admin_type != "admin":
            raise credentials_exception
            
    except jwt.PyJWTError:
        raise credentials_exception
    
    # Get admin from database
    admin = db.query(Admin).filter(Admin.admin_username == admin_username).first()
    if admin is None:
        raise credentials_exception
    
    # Check if admin is active
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled"
        )
    
    # Check if account is locked
    if admin.is_account_locked():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Admin account is locked until {admin.locked_until}"
        )
    
    # Update last activity
    admin.update_last_activity()
    db.commit()
    
    return admin

def get_current_active_admin(
    current_admin: Admin = Depends(get_current_admin)
) -> Admin:
    """Get current active admin (alias for compatibility)"""
    return current_admin

def require_super_admin(
    current_admin: Admin = Depends(get_current_admin)
) -> Admin:
    """Require super admin access"""
    if not current_admin.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_admin

def require_permission(permission: AdminPermission):
    """Dependency factory for requiring specific admin permissions"""
    def permission_checker(current_admin: Admin = Depends(get_current_admin)) -> Admin:
        AdminAuthService.require_permission(current_admin, permission)
        return current_admin
    return permission_checker

# Permission-specific dependencies
def require_user_management(admin: Admin = Depends(require_permission(AdminPermission.VIEW_USERS))) -> Admin:
    return admin

def require_system_management(admin: Admin = Depends(require_permission(AdminPermission.VIEW_SYSTEM_STATS))) -> Admin:
    return admin