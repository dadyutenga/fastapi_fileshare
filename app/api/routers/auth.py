from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.security import get_password_hash, create_access_token, verify_password
from app.api.deps import get_db
from app.db.models import User
from app.schemas.token import Token
from app.schemas.user import UserCreate

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.post("/register", response_model=Token)
async def register_api(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """Register a new user via API"""
    # Check if username already exists
    user = db.query(User).filter(User.username == form_data.username).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # Validate password length
    if len(form_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long",
        )
    
    # Create new user
    hashed_password = get_password_hash(form_data.password)
    db_user = User(
        username=form_data.username, 
        hashed_password=hashed_password,
        created_at=datetime.utcnow()
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token = create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register-web", response_class=HTMLResponse)
async def register_web(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Register a new user via web form"""
    try:
        # Check if username already exists
        user = db.query(User).filter(User.username == username).first()
        if user:
            return templates.TemplateResponse(
                "register.html", 
                {
                    "request": request, 
                    "error": "Username already registered",
                    "username": username
                }
            )
        
        # Validate password length
        if len(password) < 6:
            return templates.TemplateResponse(
                "register.html", 
                {
                    "request": request, 
                    "error": "Password must be at least 6 characters long",
                    "username": username
                }
            )
        
        # Create new user
        hashed_password = get_password_hash(password)
        db_user = User(
            username=username, 
            hashed_password=hashed_password,
            created_at=datetime.utcnow()
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Create access token and set cookie
        access_token = create_access_token(data={"sub": db_user.username})
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token", 
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=1800,  # 30 minutes
            samesite="lax"
        )
        return response
        
    except Exception as e:
        return templates.TemplateResponse(
            "register.html", 
            {
                "request": request, 
                "error": f"Registration failed: {str(e)}",
                "username": username
            }
        )

@router.post("/login", response_model=Token)
async def login_api(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """Login user via API and return access token"""
    print(f"🟡 DEBUG: /login API endpoint hit!")
    print(f"🟡 DEBUG: Username: {form_data.username}")
    
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        print(f"🔴 DEBUG: API Authentication failed for {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        print(f"🔴 DEBUG: API User {form_data.username} is inactive")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    print(f"🟢 DEBUG: API Authentication successful for {form_data.username}")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create access token
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login-web", response_class=HTMLResponse)
async def login_web(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Login user via web form"""
    print(f"🔵 DEBUG: /login-web endpoint hit!")
    print(f"🔵 DEBUG: Username: {username}")
    print(f"🔵 DEBUG: Request URL: {request.url}")
    print(f"🔵 DEBUG: Request method: {request.method}")
    
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            print(f"🔴 DEBUG: Authentication failed for {username}")
            return templates.TemplateResponse(
                "login.html", 
                {
                    "request": request, 
                    "error": "Incorrect username or password",
                    "username": username
                }
            )
        
        if not user.is_active:
            print(f"🔴 DEBUG: User {username} is inactive")
            return templates.TemplateResponse(
                "login.html", 
                {
                    "request": request, 
                    "error": "Account is disabled",
                    "username": username
                }
            )
        
        print(f"🟢 DEBUG: Authentication successful for {username}")
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create access token and set cookie
        access_token = create_access_token(data={"sub": user.username})
        print(f"🟢 DEBUG: Token created, redirecting to dashboard")
        
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token", 
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=1800,  # 30 minutes
            samesite="lax"
        )
        
        print(f"🟢 DEBUG: Redirect response created")
        return response
        
    except Exception as e:
        print(f"🔴 DEBUG: Exception in login-web: {str(e)}")
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request, 
                "error": f"Login failed: {str(e)}",
                "username": username
            }
        )

@router.post("/logout")
async def logout():
    """Logout endpoint (client should delete token)"""
    return {"message": "Successfully logged out"}