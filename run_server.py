#!/usr/bin/env python3
"""
Production server runner for FileShare Portal with concurrency support
"""
import uvicorn
import os
from app.core.config import settings

if __name__ == "__main__":
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"🌐 Server will be available at: http://0.0.0.0:8000")
    print(f"📝 Demo credentials: demo / demo123")
    print(f"⚡ Concurrent mode: Multiple users supported")
    print(f"📦 Chunked uploads: Large files supported")
    print("-" * 50)
    
    # Create uploads directory if it doesn't exist
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR)
        print(f"📁 Created uploads directory: {settings.UPLOAD_DIR}")
    
    # Run the server with concurrency support
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,  # Set to False for production
        access_log=True,
        log_level="info",
        workers=1,  # Use 1 worker for SQLite (multiple workers would need separate DB connections)
        limit_concurrency=1000,  # Allow up to 1000 concurrent connections
        limit_max_requests=10000,  # Restart worker after 10k requests
        timeout_keep_alive=75,  # Keep connections alive for 75 seconds
        timeout_graceful_shutdown=30  # Graceful shutdown timeout
    )
