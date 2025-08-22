from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from .base import Base

# Admin-specific enums
class AdminRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"

class AdminPermission(enum.Enum):
    # User management
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    SUSPEND_USERS = "suspend_users"
    
    # File management
    VIEW_ALL_FILES = "view_all_files"
    DELETE_ANY_FILE = "delete_any_file"
    MODERATE_FILES = "moderate_files"
    
    # System management
    VIEW_SYSTEM_STATS = "view_system_stats"
    MANAGE_SETTINGS = "manage_settings"
    VIEW_LOGS = "view_logs"
    
    # Admin management (super admin only)
    MANAGE_ADMINS = "manage_admins"
    ASSIGN_ROLES = "assign_roles"

class Admin(Base):
    __tablename__ = "admins"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    admin_username = Column(String(100), unique=True, index=True, nullable=False)
    admin_email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Admin specific fields
    full_name = Column(String(200), nullable=False)
    role = Column(Enum(AdminRole), default=AdminRole.MODERATOR)
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
    
    # Relationships
    admin_logs = relationship("AdminLog", back_populates="admin")
    
    def has_permission(self, permission: AdminPermission) -> bool:
        """Check if admin has specific permission based on role"""
        role_permissions = {
            AdminRole.SUPER_ADMIN: list(AdminPermission),  # All permissions
            AdminRole.ADMIN: [
                AdminPermission.VIEW_USERS,
                AdminPermission.EDIT_USERS,
                AdminPermission.SUSPEND_USERS,
                AdminPermission.VIEW_ALL_FILES,
                AdminPermission.DELETE_ANY_FILE,
                AdminPermission.MODERATE_FILES,
                AdminPermission.VIEW_SYSTEM_STATS,
                AdminPermission.VIEW_LOGS,
            ],
            AdminRole.MODERATOR: [
                AdminPermission.VIEW_USERS,
                AdminPermission.VIEW_ALL_FILES,
                AdminPermission.MODERATE_FILES,
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

class AdminLog(Base):
    __tablename__ = "admin_logs"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    admin_id = Column(CHAR(36), ForeignKey("admins.id"), nullable=False)
    
    # Log details
    action = Column(String(100), nullable=False)  # e.g., "DELETE_USER", "SUSPEND_USER"
    target_type = Column(String(50), nullable=True)  # "USER", "FILE", "ADMIN"
    target_id = Column(String(100), nullable=True)  # ID of the target
    details = Column(Text, nullable=True)  # Additional details in JSON format
    
    # Request information
    ip_address = Column(String(45), nullable=True)  # Support IPv6
    user_agent = Column(Text, nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    admin = relationship("Admin", back_populates="admin_logs")

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