from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from decimal import Decimal
from enum import Enum
from uuid import UUID

class PlanType(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    BUSINESS = "business"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentCreate(BaseModel):
    """Create a new payment record"""
    amount: Decimal
    currency: str = "USD"
    plan_type: PlanType
    duration_days: int
    payment_method: str

class PaymentUpdate(BaseModel):
    """Update payment status"""
    status: PaymentStatus
    processed_at: Optional[datetime] = None
    gateway_response: Optional[str] = None

class PaymentResponse(BaseModel):
    """Payment response"""
    id: str  # Changed from int to str for UUID
    payment_id: str
    user_id: str  # Changed from int to str for UUID
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

class PlanFeatures(BaseModel):
    """Features available in each plan"""
    plan_type: PlanType
    storage_limit: int  # in bytes
    daily_download_limit: int  # in bytes
    max_file_size: int  # in bytes
    concurrent_uploads: int
    custom_urls: bool
    analytics: bool
    priority_support: bool
    api_access: bool
    price_monthly: Decimal
    price_yearly: Decimal

class PlanComparison(BaseModel):
    """Comparison of all available plans"""
    free: PlanFeatures
    premium: PlanFeatures
    business: PlanFeatures