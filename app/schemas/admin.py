from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

# Enums matching the database models
class AdminRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"

class AdminPermission(str, Enum):
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    SUSPEND_USERS = "suspend_users"
    VIEW_SYSTEM_STATS = "view_system_stats"
    MANAGE_SETTINGS = "manage_settings"

class AdminBase(BaseModel):
    admin_username: str
    admin_email: EmailStr
    full_name: str
    role: AdminRole = AdminRole.ADMIN

class AdminCreate(AdminBase):
    password: str

class AdminLogin(BaseModel):
    admin_username: str
    password: str

class AdminUpdate(BaseModel):
    admin_email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[AdminRole] = None
    is_active: Optional[bool] = None

class AdminPasswordUpdate(BaseModel):
    current_password: str
    new_password: str

class Admin(AdminBase):
    id: str
    is_active: bool
    is_super_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    created_by: Optional[str] = None
    failed_login_attempts: int
    locked_until: Optional[datetime] = None
    last_password_change: datetime
    last_activity: datetime

    class Config:
        from_attributes = True

class AdminProfile(BaseModel):
    """Admin profile with permissions"""
    id: str
    admin_username: str
    admin_email: EmailStr
    full_name: str
    role: AdminRole
    is_active: bool
    is_super_admin: bool
    permissions: List[AdminPermission]
    created_at: datetime
    last_login: Optional[datetime] = None
    last_activity: datetime

    class Config:
        from_attributes = True

class AdminDashboardStats(BaseModel):
    """Admin dashboard statistics"""
    total_users: int
    active_users: int
    inactive_users: int
    premium_users: int
    total_files: int
    total_storage_used: int
    total_downloads: int
    files_uploaded_today: int
    new_users_today: int
    top_file_types: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]  # Empty list for privacy

class SystemSetting(BaseModel):
    """System setting model"""
    id: str
    setting_key: str
    setting_value: Optional[str] = None
    setting_type: str = "string"
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True

class SystemSettingUpdate(BaseModel):
    setting_value: str
    description: Optional[str] = None

class AdminToken(BaseModel):
    access_token: str
    token_type: str
    admin_info: AdminProfile