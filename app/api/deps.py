from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.db.base import SessionLocal
from app.db.models import User
from app.schemas import token as token_schema

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_token_from_cookie_or_header(
    request: Request,
    access_token: Optional[str] = Cookie(None),
    authorization: Optional[str] = Depends(reusable_oauth2)
) -> Optional[str]:
    """Extract token from cookie or Authorization header"""
    token = None
    
    # First try to get from cookie
    if access_token:
        if access_token.startswith("Bearer "):
            token = access_token[7:]
        else:
            token = access_token
    
    # Fallback to Authorization header
    elif authorization:
        token = authorization
    
    return token

def get_current_user(
    db: Session = Depends(get_db), 
    token: Optional[str] = Depends(get_token_from_cookie_or_header)
) -> Optional[User]:
    """Get current user from token. Returns None if not authenticated."""
    if not token:
        return None
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            return None
        token_data = token_schema.TokenData(username=username)
    except (JWTError, ValidationError):
        return None
    
    user = db.query(User).filter(User.username == token_data.username, User.is_active == True).first()
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current user and raise exception if not authenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

def get_current_user_optional(current_user: Optional[User] = Depends(get_current_user)) -> Optional[User]:
    """Get current user but don't raise exception if not authenticated."""
    return current_user