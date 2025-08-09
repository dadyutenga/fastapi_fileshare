from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_current_user_optional, get_current_active_user, get_db
from app.db.models import User
from app.services import file_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request, 
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Home page with upload form (requires login) or welcome message"""
    return templates.TemplateResponse(
        "index.html", {
            "request": request, 
            "user": current_user
        }
    )

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Login page"""
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "login.html", {
            "request": request,
            "user": current_user
        }
    )

@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Registration page"""
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "register.html", {
            "request": request,
            "user": current_user
        }
    )

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """User dashboard with file statistics"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    files = file_service.get_user_files(db, current_user.id)
    total_files = len(files)
    total_size = sum(f.file_size for f in files)
    total_downloads = sum(f.download_count for f in files)
    
    return templates.TemplateResponse(
        "dashboard.html", {
            "request": request,
            "user": current_user,
            "total_files": total_files,
            "total_size": total_size,
            "total_downloads": total_downloads,
            "recent_files": files[:5]  # Show 5 most recent files
        }
    )

@router.get("/logout")
async def logout():
    """Logout and redirect to home"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@router.get("/files", response_class=HTMLResponse)
async def get_user_files(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    """Get user's uploaded files dashboard"""
    files = file_service.get_user_files(db, current_user.id)
    return templates.TemplateResponse(
        "files.html", {
            "request": request, 
            "files": files, 
            "user": current_user
        }
    )