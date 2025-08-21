"""
Example API Endpoint Updates for UUID Support
This file shows how to update your API endpoints to work with UUIDs
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.db import get_db
from app.db.models import User, File, PaymentHistory
from app.schemas.user import User as UserSchema, UserCreate, UserProfile
from app.schemas.file import FileResponse
from app.utils.helpers import is_valid_uuid

router = APIRouter()

# Example: User endpoints with UUID support

@router.get("/users/{user_id}", response_model=UserSchema)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    """Get user by UUID"""
    # Validate UUID format
    if not is_valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.post("/users", response_model=UserSchema)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create new user with UUID"""
    # Check if username already exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Create new user - UUID will be auto-generated
    db_user = User(
        username=user.username,
        email=user.email,
        phone_number=user.phone_number,
        hashed_password="hashed_password_here"  # Replace with actual hashing
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

# Example: File endpoints with UUID support

@router.get("/users/{user_id}/files", response_model=List[FileResponse])
async def get_user_files(user_id: str, db: Session = Depends(get_db)):
    """Get all files for a user by UUID"""
    # Validate UUID format
    if not is_valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user's files
    files = db.query(File).filter(File.owner_id == user_id).all()
    return files

@router.get("/files/{file_id}", response_model=FileResponse)
async def get_file(file_id: str, db: Session = Depends(get_db)):
    """Get file by UUID"""
    # Validate UUID format  
    if not is_valid_uuid(file_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID format"
        )
    
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return file

# Example: Payment endpoints with UUID support

@router.get("/users/{user_id}/payments")
async def get_user_payments(user_id: str, db: Session = Depends(get_db)):
    """Get payment history for a user by UUID"""
    # Validate UUID format
    if not is_valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user's payment history
    payments = db.query(PaymentHistory).filter(PaymentHistory.user_id == user_id).all()
    return payments

# Example: Utility functions for working with UUIDs

def validate_uuid_param(uuid_string: str, param_name: str = "ID") -> str:
    """Validate UUID parameter and raise appropriate HTTP exception"""
    if not is_valid_uuid(uuid_string):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {param_name} format. Must be a valid UUID."
        )
    return uuid_string

def get_user_or_404(db: Session, user_id: str) -> User:
    """Get user by UUID or raise 404"""
    validate_uuid_param(user_id, "user ID")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

def get_file_or_404(db: Session, file_id: str) -> File:
    """Get file by UUID or raise 404"""
    validate_uuid_param(file_id, "file ID")
    
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return file

# Example: Updated endpoint using utility functions

@router.delete("/files/{file_id}")
async def delete_file(file_id: str, db: Session = Depends(get_db)):
    """Delete a file by UUID"""
    file = get_file_or_404(db, file_id)
    
    # Delete file from filesystem
    import os
    if os.path.exists(file.path):
        os.remove(file.path)
    
    # Delete from database
    db.delete(file)
    db.commit()
    
    return {"message": "File deleted successfully"}

"""
IMPORTANT MIGRATION NOTES:
==========================

1. PATH PARAMETERS:
   OLD: /users/{user_id:int}
   NEW: /users/{user_id:str}

2. VALIDATION:
   - Always validate UUID format before database queries
   - Use is_valid_uuid() helper function
   - Provide clear error messages for invalid UUIDs

3. DATABASE QUERIES:
   - No changes needed in query syntax
   - SQLAlchemy handles UUID/string conversion automatically

4. FRONTEND UPDATES:
   - Update all API calls to expect string IDs
   - Remove any integer parsing of IDs
   - Update local storage/state management

5. FILE PATHS:
   - User folders now use UUID strings: /uploads/users/{uuid}/
   - Existing files may need path migration

6. SECURITY BENEFITS:
   - No more ID enumeration attacks
   - Harder to guess valid IDs
   - Better for public APIs
"""