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

    class Config:
        from_attributes = True