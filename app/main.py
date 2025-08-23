from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from app.api.routers import auth, files, views
from app.db.base import init_db, SessionLocal
from app.core.config import settings
from app.api.routers import admin_auth, AdminViews
from app.api.routers import admin_request_logs
from app.middleware.request_logging import RequestLoggingMiddleware

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Secure file sharing platform with user authentication and file management",
    version=settings.APP_VERSION,
)

# Add CORS middleware (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(views.router, tags=["views"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin_auth.router, prefix="/admin", tags=["admin-auth"])
app.include_router(AdminViews.router, tags=["admin-views"])  # Removed prefix="/admin" here
app.include_router(admin_request_logs.router, prefix="/admin/logs", tags=["admin-request-logs"])

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    # For HTML requests, you could render an error template
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.on_event("startup")
def on_startup():
    """Initialize database and create upload directory on startup"""
    init_db()
    
    # Create upload directory if it doesn't exist
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR)
    
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} started successfully!")
    print(f"📁 Upload directory: {settings.UPLOAD_DIR}")
    print(f"💾 Database: {settings.DATABASE_URL}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }