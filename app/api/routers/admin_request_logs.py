"""
Admin Request Log Views - Separate admin endpoints for viewing request logs
Security focused endpoints for administrators only
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime

from app.api.deps import get_db
from app.api.admin_deps import get_current_admin, require_super_admin
from app.db.admin_models import Admin
from app.services.request_log_service import RequestLogService

router = APIRouter(prefix="/admin/logs", tags=["admin-request-logs"])
templates = Jinja2Templates(directory="templates")

@router.get("/requests", response_class=HTMLResponse)
async def admin_request_logs_page(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Admin page for viewing request logs"""
    return templates.TemplateResponse(
        "admin/request_logs.html",
        {
            "request": request,
            "admin": current_admin,
            "page_title": "Request Logs"
        }
    )

@router.get("/requests/api")
async def get_request_logs_api(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_code: Optional[int] = Query(None),
    endpoint: Optional[str] = Query(None),
    client_ip: Optional[str] = Query(None),
    min_risk_score: Optional[int] = Query(None, ge=0, le=100)
) -> Dict[str, Any]:
    """API endpoint to get request logs with filtering"""
    
    logs = RequestLogService.get_recent_requests(
        db=db,
        limit=limit,
        offset=offset,
        status_code=status_code,
        endpoint=endpoint,
        client_ip=client_ip,
        min_risk_score=min_risk_score
    )
    
    return {
        "logs": logs,
        "total": len(logs),
        "limit": limit,
        "offset": offset,
        "filters": {
            "status_code": status_code,
            "endpoint": endpoint,
            "client_ip": client_ip,
            "min_risk_score": min_risk_score
        }
    }

@router.get("/stats")
async def get_request_stats_api(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    hours: int = Query(24, ge=1, le=168)  # Max 1 week
) -> Dict[str, Any]:
    """Get comprehensive request statistics"""
    
    # Get general request stats
    request_stats = RequestLogService.get_request_stats(db, hours)
    
    # Get login attempt stats
    login_stats = RequestLogService.get_login_attempt_stats(db, hours)
    
    # Get security analysis
    security_analysis = RequestLogService.get_security_analysis(db, hours)
    
    # Get hourly distribution
    hourly_distribution = RequestLogService.get_hourly_request_distribution(db, hours)
    
    return {
        "request_stats": request_stats,
        "login_stats": login_stats,
        "security_analysis": security_analysis,
        "hourly_distribution": hourly_distribution,
        "generated_at": datetime.utcnow().isoformat()
    }

@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics_page(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Admin analytics page with charts and statistics"""
    return templates.TemplateResponse(
        "admin/request_analytics.html",
        {
            "request": request,
            "admin": current_admin,
            "page_title": "Request Analytics"
        }
    )

@router.get("/security", response_class=HTMLResponse)
async def admin_security_page(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Admin security monitoring page"""
    return templates.TemplateResponse(
        "admin/security_monitoring.html",
        {
            "request": request,
            "admin": current_admin,
            "page_title": "Security Monitoring"
        }
    )

@router.get("/login-attempts")
async def get_login_attempts_api(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    hours: int = Query(24, ge=1, le=168)
) -> Dict[str, Any]:
    """Get detailed login attempt statistics"""
    
    login_stats = RequestLogService.get_login_attempt_stats(db, hours)
    return login_stats

@router.get("/security-analysis")
async def get_security_analysis_api(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    hours: int = Query(24, ge=1, le=168)
) -> Dict[str, Any]:
    """Get security analysis data"""
    
    security_analysis = RequestLogService.get_security_analysis(db, hours)
    return security_analysis

@router.post("/cleanup")
async def cleanup_old_logs(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin),
    days_to_keep: int = Query(30, ge=7, le=365)
) -> Dict[str, Any]:
    """Clean up old request logs (Super Admin only)"""
    
    deleted_count = RequestLogService.cleanup_old_logs(db, days_to_keep)
    
    return {
        "success": True,
        "message": f"Cleaned up {deleted_count} old log entries",
        "deleted_count": deleted_count,
        "days_kept": days_to_keep
    }

@router.get("/export")
async def export_request_logs(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin),
    hours: int = Query(24, ge=1, le=168),
    format: str = Query("json", regex="^(json|csv)$")
) -> Dict[str, Any]:
    """Export request logs (Super Admin only)"""
    
    # Get comprehensive data
    request_stats = RequestLogService.get_request_stats(db, hours)
    login_stats = RequestLogService.get_login_attempt_stats(db, hours)
    security_analysis = RequestLogService.get_security_analysis(db, hours)
    recent_logs = RequestLogService.get_recent_requests(db, limit=1000)
    
    export_data = {
        "export_info": {
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": current_admin.admin_username,
            "period_hours": hours,
            "format": format
        },
        "request_statistics": request_stats,
        "login_statistics": login_stats,
        "security_analysis": security_analysis,
        "recent_requests": recent_logs
    }
    
    if format == "json":
        return export_data
    else:
        # For CSV format, you might want to implement CSV conversion
        # For now, return JSON with a note
        export_data["note"] = "CSV export not yet implemented, returning JSON format"
        return export_data