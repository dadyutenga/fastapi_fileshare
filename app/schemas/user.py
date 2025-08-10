from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    storage_limit: int
    daily_download_limit: int
    storage_used: int
    daily_downloads_used: int
    last_download_reset: datetime

    class Config:
        from_attributes = True

class UserStats(BaseModel):
    user_id: int
    total_files: int
    storage_used: int
    storage_limit: int
    storage_percentage: float
    daily_downloads_used: int
    daily_download_limit: int
    daily_download_percentage: float
    total_downloads: int
    formatted_storage_used: str
    formatted_storage_limit: str
    formatted_daily_downloads: str
    formatted_daily_limit: str

class UserLimitsUpdate(BaseModel):
    storage_limit: Optional[int] = None
    daily_download_limit: Optional[int] = None