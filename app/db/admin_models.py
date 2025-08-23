from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum
import uuid

from .base import Base

# Admin-specific enums
class AdminRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
   
  

class AdminPermission(enum.Enum):
    # User management
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    SUSPEND_USERS = "suspend_users"
    
    # System management
    VIEW_SYSTEM_STATS = "view_system_stats"
    MANAGE_SETTINGS = "manage_settings"
    
    # Admin management (super admin only)
    

class Admin(Base):
    __tablename__ = "admins"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    admin_username = Column(String(100), unique=True, index=True, nullable=False)
    admin_email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Admin specific fields
    full_name = Column(String(200), nullable=False)
    role = Column(Enum(AdminRole), default=AdminRole.ADMIN)
    is_active = Column(Boolean, default=True)
    is_super_admin = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=True)  # Admin ID who created this admin
    
    # Security fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_password_change = Column(DateTime, default=datetime.utcnow)
    
    # Admin activity tracking
    last_activity = Column(DateTime, default=datetime.utcnow)
    session_token = Column(String(255), nullable=True)  # For session management
    
    def has_permission(self, permission: AdminPermission) -> bool:
        """Check if admin has specific permission based on role"""
        role_permissions = {
            AdminRole.SUPER_ADMIN: list(AdminPermission),  # All permissions
            AdminRole.ADMIN: [
                AdminPermission.VIEW_USERS,
                AdminPermission.EDIT_USERS,
                AdminPermission.SUSPEND_USERS,
                AdminPermission.VIEW_SYSTEM_STATS,
            ]
        }
        
        return permission in role_permissions.get(self.role, [])
    
    def is_account_locked(self) -> bool:
        """Check if admin account is locked"""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until
    
    def reset_failed_attempts(self):
        """Reset failed login attempts"""
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def increment_failed_attempts(self):
        """Increment failed login attempts and lock if necessary"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            # Lock account for 30 minutes after 5 failed attempts
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    def update_last_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=True)
    setting_type = Column(String(20), default="string")  # string, integer, boolean, json
    description = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(CHAR(36), nullable=True)  # Admin ID who last updated
    
    def get_typed_value(self):
        """Get the setting value with proper type conversion"""
        if self.setting_type == "integer":
            return int(self.setting_value) if self.setting_value else 0
        elif self.setting_type == "boolean":
            return self.setting_value.lower() == "true" if self.setting_value else False
        elif self.setting_type == "json":
            import json
            return json.loads(self.setting_value) if self.setting_value else {}
        else:
            return self.setting_value or ""