"""
Request Logging Models - Completely separate from existing models
For tracking all HTTP requests passing through the application
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy.dialects.mysql import CHAR
from datetime import datetime
import enum
import uuid

from .base import Base

class RequestMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"

class RequestStatus(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    SERVER_ERROR = "server_error"

class RequestLog(Base):
    """Model for logging all HTTP requests"""
    __tablename__ = "request_logs"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Request details
    method = Column(String(10), nullable=False)  # HTTP method
    endpoint = Column(String(500), nullable=False)  # Request path/endpoint
    full_url = Column(Text, nullable=True)  # Complete URL
    
    # Client information
    client_ip = Column(String(45), nullable=True)  # IPv4/IPv6 address
    user_agent = Column(Text, nullable=True)  # Browser/client info
    referer = Column(Text, nullable=True)  # Referring page
    
    # Authentication info
    user_id = Column(CHAR(36), nullable=True)  # User ID if authenticated
    username = Column(String(100), nullable=True)  # Username if authenticated
    is_authenticated = Column(Boolean, default=False)
    auth_method = Column(String(50), nullable=True)  # "bearer", "cookie", etc.
    
    # Response details
    status_code = Column(Integer, nullable=False)  # HTTP status code
    response_time_ms = Column(Float, nullable=True)  # Response time in milliseconds
    response_size = Column(Integer, nullable=True)  # Response size in bytes
    request_status = Column(String(20), nullable=False, default="success")
    
    # Request body info (for security analysis)
    content_type = Column(String(100), nullable=True)  # Request content type
    content_length = Column(Integer, nullable=True)  # Request body size
    has_files = Column(Boolean, default=False)  # Whether request contains file uploads
    
    # Security and analysis fields
    is_suspicious = Column(Boolean, default=False)  # Flagged as suspicious
    risk_score = Column(Integer, default=0)  # Risk score 0-100
    geolocation = Column(String(100), nullable=True)  # Country/region
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Error details (if any)
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    
    def get_status_category(self) -> RequestStatus:
        """Get status category based on HTTP status code"""
        if 200 <= self.status_code < 300:
            return RequestStatus.SUCCESS
        elif self.status_code == 401:
            return RequestStatus.UNAUTHORIZED
        elif self.status_code == 403:
            return RequestStatus.FORBIDDEN
        elif self.status_code == 404:
            return RequestStatus.NOT_FOUND
        elif 500 <= self.status_code < 600:
            return RequestStatus.SERVER_ERROR
        else:
            return RequestStatus.ERROR
    
    def is_login_request(self) -> bool:
        """Check if this is a login-related request"""
        login_endpoints = ['/login', '/login-web', '/register', '/register-web', '/admin/login']
        return any(endpoint in self.endpoint for endpoint in login_endpoints)
    
    def is_file_operation(self) -> bool:
        """Check if this is a file-related operation"""
        file_endpoints = ['/upload', '/download', '/delete', '/files']
        return any(endpoint in self.endpoint for endpoint in file_endpoints)
    
    def is_admin_request(self) -> bool:
        """Check if this is an admin panel request"""
        return self.endpoint.startswith('/admin')

class LoginAttemptLog(Base):
    """Specific model for detailed login attempt tracking"""
    __tablename__ = "login_attempt_logs"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Login attempt details
    username = Column(String(100), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)  # /login, /login-web, /admin/login
    success = Column(Boolean, nullable=False)
    
    # Client information
    client_ip = Column(String(45), nullable=False, index=True)
    user_agent = Column(Text, nullable=True)
    country = Column(String(50), nullable=True)
    
    # Failure details (if login failed)
    failure_reason = Column(String(100), nullable=True)  # "invalid_password", "user_not_found", etc.
    
    # Security analysis
    is_brute_force_attempt = Column(Boolean, default=False)
    risk_score = Column(Integer, default=0)  # 0-100 risk score
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Associated request log
    request_log_id = Column(CHAR(36), nullable=True)  # Link to main request log

class SecurityAlert(Base):
    """Model for security alerts and suspicious activity"""
    __tablename__ = "security_alerts"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Alert details
    alert_type = Column(String(50), nullable=False)  # "brute_force", "suspicious_ip", etc.
    severity = Column(String(20), nullable=False)  # "low", "medium", "high", "critical"
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Related entities
    client_ip = Column(String(45), nullable=True, index=True)
    username = Column(String(100), nullable=True, index=True)
    endpoint = Column(String(500), nullable=True)
    
    # Alert metadata
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)  # Admin who resolved
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Associated request logs
    related_request_count = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)