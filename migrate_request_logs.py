"""
Database Migration Script for Request Logging Tables
Creates new tables without affecting existing database structure
"""
from sqlalchemy import create_engine
from app.core.config import settings
from app.db.base import Base
from app.db.request_log_models import RequestLog, LoginAttemptLog, SecurityAlert

def create_request_log_tables():
    """Create request logging tables"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    # Import the models to ensure they're registered
    from app.db.request_log_models import RequestLog, LoginAttemptLog, SecurityAlert
    
    # Create only the request log tables (won't affect existing tables)
    RequestLog.__table__.create(engine, checkfirst=True)
    LoginAttemptLog.__table__.create(engine, checkfirst=True)  
    SecurityAlert.__table__.create(engine, checkfirst=True)
    
    print("✅ Request logging tables created successfully!")
    print("📊 Tables created:")
    print("   - request_logs")
    print("   - login_attempt_logs") 
    print("   - security_alerts")

if __name__ == "__main__":
    create_request_log_tables()