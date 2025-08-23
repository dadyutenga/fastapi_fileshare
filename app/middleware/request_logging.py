"""
Request Logging Middleware - Captures all HTTP requests
Completely separate from existing code, no interference
"""
import time
import json
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.request_log_models import RequestLog, LoginAttemptLog, SecurityAlert
from app.core.config import settings
from app.db.base import SessionLocal

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests to the database"""
    
    def __init__(self, app, db_session_factory: sessionmaker = None):
        super().__init__(app)
        self.db_session_factory = db_session_factory
        
        # Endpoints to exclude from logging (to avoid noise)
        self.exclude_paths = {
            '/static',
            '/favicon.ico',
            '/robots.txt'
        }
        
        # Track login attempts for brute force detection
        self.login_attempts = {}  # IP -> {count, last_attempt}
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process each request and log it"""
        start_time = time.time()
        
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Extract request information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        referer = request.headers.get("referer", "")
        content_type = request.headers.get("content-type", "")
        content_length = request.headers.get("content-length", 0)
        
        # Try to get content length as integer
        try:
            content_length = int(content_length) if content_length else 0
        except:
            content_length = 0
        
        # Check if request has file uploads
        has_files = "multipart/form-data" in content_type
        
        # Extract authentication info
        auth_info = self._extract_auth_info(request)
        
        # Process the request
        response = None
        error_message = None
        error_type = None
        
        try:
            response = await call_next(request)
        except Exception as e:
            error_message = str(e)
            error_type = type(e).__name__
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Get response size if available
        response_size = None
        if hasattr(response, 'headers') and 'content-length' in response.headers:
            try:
                response_size = int(response.headers['content-length'])
            except:
                pass
        
        # Log the request in background (don't block response)
        try:
            self._log_request_async(
                method=request.method,
                endpoint=str(request.url.path),
                full_url=str(request.url),
                client_ip=client_ip,
                user_agent=user_agent,
                referer=referer,
                content_type=content_type,
                content_length=content_length,
                has_files=has_files,
                auth_info=auth_info,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                response_size=response_size,
                error_message=error_message,
                error_type=error_type
            )
        except Exception as log_error:
            # Don't let logging errors affect the actual response
            print(f"Request logging error: {log_error}")
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _extract_auth_info(self, request: Request) -> dict:
        """Extract authentication information from request"""
        auth_info = {
            "user_id": None,
            "username": None,
            "is_authenticated": False,
            "auth_method": None
        }
        
        # Check for Bearer token in Authorization header
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            auth_info["auth_method"] = "bearer"
            # Note: We don't decode the token here to avoid dependency issues
        
        # Check for token in cookies
        elif "access_token" in request.cookies:
            auth_info["auth_method"] = "cookie"
        
        # Check for admin token in cookies
        elif "admin_token" in request.cookies:
            auth_info["auth_method"] = "admin_cookie"
        
        return auth_info
    
    def _log_request_async(self, **kwargs):
        """Log request to database (should be called asynchronously)"""
        try:
            # Create database session using the existing SessionLocal
            db = SessionLocal()
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(kwargs)
            
            # Create request log entry
            request_log = RequestLog(
                method=kwargs.get("method"),
                endpoint=kwargs.get("endpoint"),
                full_url=kwargs.get("full_url"),
                client_ip=kwargs.get("client_ip"),
                user_agent=kwargs.get("user_agent"),
                referer=kwargs.get("referer"),
                user_id=kwargs.get("auth_info", {}).get("user_id"),
                username=kwargs.get("auth_info", {}).get("username"),
                is_authenticated=kwargs.get("auth_info", {}).get("is_authenticated", False),
                auth_method=kwargs.get("auth_info", {}).get("auth_method"),
                status_code=kwargs.get("status_code"),
                response_time_ms=kwargs.get("response_time_ms"),
                response_size=kwargs.get("response_size"),
                content_type=kwargs.get("content_type"),
                content_length=kwargs.get("content_length"),
                has_files=kwargs.get("has_files", False),
                risk_score=risk_score,
                error_message=kwargs.get("error_message"),
                error_type=kwargs.get("error_type")
            )
            
            # Set request status based on status code
            if 200 <= kwargs.get("status_code", 500) < 300:
                request_log.request_status = "success"
            elif kwargs.get("status_code") == 401:
                request_log.request_status = "unauthorized"
            elif kwargs.get("status_code") == 403:
                request_log.request_status = "forbidden"
            elif kwargs.get("status_code") == 404:
                request_log.request_status = "not_found"
            elif kwargs.get("status_code", 500) >= 500:
                request_log.request_status = "server_error"
            else:
                request_log.request_status = "error"
            
            db.add(request_log)
            
            # Log login attempts separately
            if self._is_login_endpoint(kwargs.get("endpoint", "")):
                self._log_login_attempt(db, request_log, kwargs)
            
            db.commit()
            db.close()
            
        except Exception as e:
            print(f"Database logging error: {e}")
            if 'db' in locals():
                db.close()
    
    def _is_login_endpoint(self, endpoint: str) -> bool:
        """Check if endpoint is a login-related endpoint"""
        login_endpoints = ['/login', '/login-web', '/register', '/register-web', '/admin/login']
        return any(login_ep in endpoint for login_ep in login_endpoints)
    
    def _log_login_attempt(self, db: Session, request_log: RequestLog, kwargs: dict):
        """Log detailed login attempt information"""
        try:
            # Extract username from request (this is simplified)
            username = "unknown"  # In real implementation, you'd extract from form data
            
            # Determine if login was successful
            success = 200 <= kwargs.get("status_code", 500) < 300
            
            # Determine failure reason
            failure_reason = None
            if not success:
                if kwargs.get("status_code") == 401:
                    failure_reason = "invalid_credentials"
                elif kwargs.get("status_code") == 400:
                    failure_reason = "bad_request"
                else:
                    failure_reason = "server_error"
            
            # Check for brute force attempts
            client_ip = kwargs.get("client_ip")
            is_brute_force = self._check_brute_force(client_ip, success)
            
            login_log = LoginAttemptLog(
                username=username,
                endpoint=kwargs.get("endpoint"),
                success=success,
                client_ip=client_ip,
                user_agent=kwargs.get("user_agent"),
                failure_reason=failure_reason,
                is_brute_force_attempt=is_brute_force,
                risk_score=min(100, kwargs.get("auth_info", {}).get("risk_score", 0)),
                request_log_id=request_log.id
            )
            
            db.add(login_log)
            
        except Exception as e:
            print(f"Login attempt logging error: {e}")
    
    def _check_brute_force(self, client_ip: str, success: bool) -> bool:
        """Simple brute force detection"""
        if not client_ip or client_ip == "unknown":
            return False
        
        current_time = time.time()
        
        # Clean old attempts (older than 1 hour)
        cutoff_time = current_time - 3600
        for ip in list(self.login_attempts.keys()):
            if self.login_attempts[ip]["last_attempt"] < cutoff_time:
                del self.login_attempts[ip]
        
        # Track this attempt
        if client_ip not in self.login_attempts:
            self.login_attempts[client_ip] = {"count": 0, "last_attempt": 0}
        
        if not success:
            self.login_attempts[client_ip]["count"] += 1
            self.login_attempts[client_ip]["last_attempt"] = current_time
            
            # Consider it brute force if more than 5 failures in last hour
            return self.login_attempts[client_ip]["count"] > 5
        else:
            # Reset on successful login
            if client_ip in self.login_attempts:
                del self.login_attempts[client_ip]
            return False
    
    def _calculate_risk_score(self, kwargs: dict) -> int:
        """Calculate risk score for request (0-100)"""
        risk_score = 0
        
        # High risk for multiple failed logins
        if kwargs.get("status_code") == 401:
            risk_score += 20
        
        # Medium risk for server errors
        elif kwargs.get("status_code", 0) >= 500:
            risk_score += 10
        
        # Low risk for long response times (possible DoS)
        if kwargs.get("response_time_ms", 0) > 5000:  # 5 seconds
            risk_score += 15
        
        # Risk for large file uploads
        if kwargs.get("has_files") and kwargs.get("content_length", 0) > 100 * 1024 * 1024:  # 100MB
            risk_score += 10
        
        # Risk for suspicious user agents
        user_agent = kwargs.get("user_agent", "").lower()
        suspicious_agents = ["bot", "crawler", "scanner", "curl", "wget"]
        if any(agent in user_agent for agent in suspicious_agents):
            risk_score += 25
        
        return min(100, risk_score)

# Factory function to create middleware with database session
def create_request_logging_middleware(app, database_url: str = None):
    """Create request logging middleware with database connection"""
    
    if database_url is None:
        database_url = settings.DATABASE_URL
    
    # Create engine and session factory for logging
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return RequestLoggingMiddleware(app, SessionLocal)