"""
Request Log Management Service - Completely separate from existing services
Provides analytics and management for request logs
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc

from app.db.request_log_models import RequestLog, LoginAttemptLog, SecurityAlert

class RequestLogService:
    """Service for managing and analyzing request logs"""
    
    @staticmethod
    def get_request_stats(db: Session, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive request statistics for the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Total requests
        total_requests = db.query(RequestLog).filter(
            RequestLog.timestamp >= cutoff_time
        ).count()
        
        # Successful requests
        successful_requests = db.query(RequestLog).filter(
            and_(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.status_code >= 200,
                RequestLog.status_code < 300
            )
        ).count()
        
        # Error requests
        error_requests = db.query(RequestLog).filter(
            and_(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.status_code >= 400
            )
        ).count()
        
        # Unique IPs
        unique_ips = db.query(func.count(func.distinct(RequestLog.client_ip))).filter(
            RequestLog.timestamp >= cutoff_time
        ).scalar()
        
        # Average response time
        avg_response_time = db.query(func.avg(RequestLog.response_time_ms)).filter(
            and_(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.response_time_ms.isnot(None)
            )
        ).scalar() or 0
        
        # Top endpoints
        top_endpoints = db.query(
            RequestLog.endpoint,
            func.count(RequestLog.id).label('count')
        ).filter(
            RequestLog.timestamp >= cutoff_time
        ).group_by(RequestLog.endpoint).order_by(desc('count')).limit(10).all()
        
        # HTTP methods distribution
        methods = db.query(
            RequestLog.method,
            func.count(RequestLog.id).label('count')
        ).filter(
            RequestLog.timestamp >= cutoff_time
        ).group_by(RequestLog.method).all()
        
        # Status codes distribution
        status_codes = db.query(
            RequestLog.status_code,
            func.count(RequestLog.id).label('count')
        ).filter(
            RequestLog.timestamp >= cutoff_time
        ).group_by(RequestLog.status_code).order_by(desc('count')).all()
        
        return {
            "period_hours": hours,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_requests": error_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "unique_ips": unique_ips,
            "average_response_time_ms": round(avg_response_time, 2),
            "top_endpoints": [{"endpoint": ep, "count": count} for ep, count in top_endpoints],
            "methods": [{"method": method, "count": count} for method, count in methods],
            "status_codes": [{"code": code, "count": count} for code, count in status_codes]
        }
    
    @staticmethod
    def get_login_attempt_stats(db: Session, hours: int = 24) -> Dict[str, Any]:
        """Get login attempt statistics"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Total login attempts
        total_attempts = db.query(LoginAttemptLog).filter(
            LoginAttemptLog.timestamp >= cutoff_time
        ).count()
        
        # Successful logins
        successful_logins = db.query(LoginAttemptLog).filter(
            and_(
                LoginAttemptLog.timestamp >= cutoff_time,
                LoginAttemptLog.success == True
            )
        ).count()
        
        # Failed logins
        failed_logins = total_attempts - successful_logins
        
        # Brute force attempts
        brute_force_attempts = db.query(LoginAttemptLog).filter(
            and_(
                LoginAttemptLog.timestamp >= cutoff_time,
                LoginAttemptLog.is_brute_force_attempt == True
            )
        ).count()
        
        # Top IPs with failed attempts
        top_failed_ips = db.query(
            LoginAttemptLog.client_ip,
            func.count(LoginAttemptLog.id).label('count')
        ).filter(
            and_(
                LoginAttemptLog.timestamp >= cutoff_time,
                LoginAttemptLog.success == False
            )
        ).group_by(LoginAttemptLog.client_ip).order_by(desc('count')).limit(10).all()
        
        # Login endpoints distribution
        endpoints = db.query(
            LoginAttemptLog.endpoint,
            func.count(LoginAttemptLog.id).label('count')
        ).filter(
            LoginAttemptLog.timestamp >= cutoff_time
        ).group_by(LoginAttemptLog.endpoint).all()
        
        return {
            "period_hours": hours,
            "total_attempts": total_attempts,
            "successful_logins": successful_logins,
            "failed_logins": failed_logins,
            "success_rate": (successful_logins / total_attempts * 100) if total_attempts > 0 else 0,
            "brute_force_attempts": brute_force_attempts,
            "top_failed_ips": [{"ip": ip, "failed_count": count} for ip, count in top_failed_ips],
            "endpoints": [{"endpoint": ep, "count": count} for ep, count in endpoints]
        }
    
    @staticmethod
    def get_security_analysis(db: Session, hours: int = 24) -> Dict[str, Any]:
        """Analyze security-related patterns in requests"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # High-risk requests
        high_risk_requests = db.query(RequestLog).filter(
            and_(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.risk_score >= 50
            )
        ).count()
        
        # Suspicious IPs (high error rate or high risk score)
        suspicious_ips = db.query(
            RequestLog.client_ip,
            func.avg(RequestLog.risk_score).label('avg_risk'),
            func.count(RequestLog.id).label('total_requests'),
            func.sum(func.case([(RequestLog.status_code >= 400, 1)], else_=0)).label('error_requests')
        ).filter(
            RequestLog.timestamp >= cutoff_time
        ).group_by(RequestLog.client_ip).having(
            or_(
                func.avg(RequestLog.risk_score) >= 30,
                func.sum(func.case([(RequestLog.status_code >= 400, 1)], else_=0)) >= 10
            )
        ).order_by(desc('avg_risk')).limit(20).all()
        
        # File upload analysis
        file_uploads = db.query(RequestLog).filter(
            and_(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.has_files == True
            )
        ).count()
        
        large_uploads = db.query(RequestLog).filter(
            and_(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.has_files == True,
                RequestLog.content_length >= 100 * 1024 * 1024  # 100MB+
            )
        ).count()
        
        # Error patterns
        error_patterns = db.query(
            RequestLog.endpoint,
            RequestLog.status_code,
            func.count(RequestLog.id).label('count')
        ).filter(
            and_(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.status_code >= 400
            )
        ).group_by(RequestLog.endpoint, RequestLog.status_code).order_by(desc('count')).limit(20).all()
        
        return {
            "period_hours": hours,
            "high_risk_requests": high_risk_requests,
            "file_uploads": file_uploads,
            "large_uploads": large_uploads,
            "suspicious_ips": [
                {
                    "ip": ip,
                    "avg_risk_score": round(float(avg_risk), 2),
                    "total_requests": total_req,
                    "error_requests": error_req,
                    "error_rate": round((error_req / total_req * 100), 2) if total_req > 0 else 0
                }
                for ip, avg_risk, total_req, error_req in suspicious_ips
            ],
            "error_patterns": [
                {
                    "endpoint": ep,
                    "status_code": code,
                    "count": count
                }
                for ep, code, count in error_patterns
            ]
        }
    
    @staticmethod
    def get_recent_requests(
        db: Session,
        limit: int = 100,
        offset: int = 0,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        client_ip: Optional[str] = None,
        min_risk_score: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent requests with filtering options"""
        
        query = db.query(RequestLog)
        
        # Apply filters
        if status_code:
            query = query.filter(RequestLog.status_code == status_code)
        
        if endpoint:
            query = query.filter(RequestLog.endpoint.contains(endpoint))
        
        if client_ip:
            query = query.filter(RequestLog.client_ip == client_ip)
        
        if min_risk_score:
            query = query.filter(RequestLog.risk_score >= min_risk_score)
        
        # Order by timestamp and apply pagination
        requests = query.order_by(desc(RequestLog.timestamp)).offset(offset).limit(limit).all()
        
        return [
            {
                "id": req.id,
                "timestamp": req.timestamp,
                "method": req.method,
                "endpoint": req.endpoint,
                "status_code": req.status_code,
                "client_ip": req.client_ip,
                "user_agent": req.user_agent[:100] if req.user_agent else None,  # Truncate for display
                "response_time_ms": req.response_time_ms,
                "risk_score": req.risk_score,
                "is_authenticated": req.is_authenticated,
                "username": req.username,
                "error_message": req.error_message
            }
            for req in requests
        ]
    
    @staticmethod
    def get_hourly_request_distribution(db: Session, hours: int = 24) -> List[Dict[str, Any]]:
        """Get request distribution by hour"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get requests grouped by hour
        hourly_data = db.query(
            func.date_format(RequestLog.timestamp, '%Y-%m-%d %H:00:00').label('hour'),
            func.count(RequestLog.id).label('total_requests'),
            func.sum(func.case([(and_(RequestLog.status_code >= 200, RequestLog.status_code < 300), 1)], else_=0)).label('success_requests'),
            func.sum(func.case([(RequestLog.status_code >= 400, 1)], else_=0)).label('error_requests'),
            func.avg(RequestLog.response_time_ms).label('avg_response_time')
        ).filter(
            RequestLog.timestamp >= cutoff_time
        ).group_by('hour').order_by('hour').all()
        
        return [
            {
                "hour": hour,
                "total_requests": total,
                "success_requests": success,
                "error_requests": errors,
                "average_response_time": round(float(avg_time), 2) if avg_time else 0
            }
            for hour, total, success, errors, avg_time in hourly_data
        ]
    
    @staticmethod
    def cleanup_old_logs(db: Session, days_to_keep: int = 30) -> int:
        """Clean up old request logs to manage database size"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old request logs
        deleted_requests = db.query(RequestLog).filter(
            RequestLog.timestamp < cutoff_date
        ).delete()
        
        # Delete old login attempt logs
        deleted_logins = db.query(LoginAttemptLog).filter(
            LoginAttemptLog.timestamp < cutoff_date
        ).delete()
        
        # Delete resolved security alerts older than 90 days
        alert_cutoff = datetime.utcnow() - timedelta(days=90)
        deleted_alerts = db.query(SecurityAlert).filter(
            and_(
                SecurityAlert.created_at < alert_cutoff,
                SecurityAlert.is_resolved == True
            )
        ).delete()
        
        db.commit()
        
        total_deleted = deleted_requests + deleted_logins + deleted_alerts
        return total_deleted

# Export service instance
request_log_service = RequestLogService()