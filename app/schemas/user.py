from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from enum import Enum

# Enums matching the database models
class PlanType(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    BUSINESS = "business"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    # Premium/Subscription fields
    plan_type: PlanType
    is_premium: bool
    premium_until: Optional[datetime] = None
    premium_started_at: Optional[datetime] = None
    
    # Storage and limits
    storage_limit: int
    daily_download_limit: int
    storage_used: int
    daily_downloads_used: int
    last_download_reset: datetime

    class Config:
        from_attributes = True

class UserProfile(UserBase):
    """Extended user profile with premium status"""
    id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    plan_type: PlanType
    is_premium: bool
    premium_until: Optional[datetime] = None
    premium_days_remaining: Optional[int] = None
    storage_used: int
    storage_limit: int
    storage_percentage: float
    daily_downloads_used: int
    daily_download_limit: int
    daily_download_percentage: float

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
    
    # Premium stats
    is_premium: bool
    plan_type: PlanType
    premium_until: Optional[datetime] = None
    premium_days_remaining: Optional[int] = None

class UserLimitsUpdate(BaseModel):
    storage_limit: Optional[int] = None
    daily_download_limit: Optional[int] = None

class PaymentHistoryItem(BaseModel):
    """Single payment history item"""
    id: int
    payment_id: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    plan_type: PlanType
    duration_days: int
    created_at: datetime
    processed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    payment_method: Optional[str] = None

    class Config:
        from_attributes = True

class PaymentHistory(BaseModel):
    """User's complete payment history"""
    payments: List[PaymentHistoryItem]
    total_payments: int
    total_amount_spent: Decimal
    current_plan: PlanType
    is_premium_active: bool

class PremiumUpgradeRequest(BaseModel):
    """Request to upgrade to premium"""
    plan_type: PlanType = PlanType.PREMIUM
    duration_days: int = 30
    payment_method: str  # "stripe", "paypal", etc.

class PremiumUpgradeResponse(BaseModel):
    """Response after premium upgrade"""
    success: bool
    message: str
    payment_id: Optional[str] = None
    new_premium_until: Optional[datetime] = None
    new_limits: Optional[dict] = None