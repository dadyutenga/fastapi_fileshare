from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, BigInteger, Text, Enum, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum
import uuid

from .base import Base

# Enums for payment and user types
class PlanType(enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    BUSINESS = "business"

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class User(Base):
    __tablename__ = "users"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, index=True, nullable=False)  # Added length
    hashed_password = Column(String(255), nullable=False)  # Added length for password hash
    
    # Contact information
    email = Column(String(255), unique=True, index=True, nullable=True)  # Email address
    phone_number = Column(String(20), nullable=True)  # Phone number
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Premium/Subscription fields
    plan_type = Column(Enum(PlanType), default=PlanType.FREE)
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)  # When premium expires
    premium_started_at = Column(DateTime, nullable=True)  # When premium started
    
    # New fields for storage and download limits
    storage_limit = Column(BigInteger, default=5 * 1024 * 1024 * 1024)  # 5GB default for free
    daily_download_limit = Column(BigInteger, default=1 * 1024 * 1024 * 1024)  # 1GB/day default
    storage_used = Column(BigInteger, default=0)  # Current storage usage
    last_download_reset = Column(DateTime, default=datetime.utcnow)  # Track daily reset
    daily_downloads_used = Column(BigInteger, default=0)  # Daily download usage

    # Relationships
    files = relationship("File", back_populates="owner")
    payment_history = relationship("PaymentHistory", back_populates="user")
    
    def check_storage_available(self, file_size: int) -> bool:
        """Check if user has enough storage space for a new file"""
        return (self.storage_used + file_size) <= self.storage_limit
    
    def check_download_available(self, download_size: int) -> bool:
        """Check if user has enough daily download quota"""
        # Reset daily download if it's a new day
        if self.last_download_reset.date() < datetime.utcnow().date():
            self.daily_downloads_used = 0
            self.last_download_reset = datetime.utcnow()
        
        return (self.daily_downloads_used + download_size) <= self.daily_download_limit
    
    def add_storage_usage(self, file_size: int):
        """Add to storage usage"""
        self.storage_used += file_size
    
    def remove_storage_usage(self, file_size: int):
        """Remove from storage usage when file is deleted"""
        self.storage_used = max(0, self.storage_used - file_size)

    def add_download_usage(self, download_size: int):
        """Add to daily download usage"""
        # Reset daily download if it's a new day
        if self.last_download_reset.date() < datetime.utcnow().date():
            self.daily_downloads_used = 0
            self.last_download_reset = datetime.utcnow()
        
        self.daily_downloads_used += download_size
    
    def get_storage_percentage(self) -> float:
        """Get storage usage as percentage"""
        if self.storage_limit == 0:
            return 0.0
        return (self.storage_used / self.storage_limit) * 100
    
    def get_daily_download_percentage(self) -> float:
        """Get daily download usage as percentage"""
        # Reset daily download if it's a new day
        if self.last_download_reset.date() < datetime.utcnow().date():
            return 0.0
        
        if self.daily_download_limit == 0:
            return 0.0
        return (self.daily_downloads_used / self.daily_download_limit) * 100
    
    def is_premium_active(self) -> bool:
        """Check if user has active premium subscription"""
        if not self.is_premium or not self.premium_until:
            return False
        return datetime.utcnow() < self.premium_until
    
    def get_premium_days_remaining(self) -> int:
        """Get number of days remaining in premium subscription"""
        if not self.is_premium_active():
            return 0
        return (self.premium_until - datetime.utcnow()).days
    
    def upgrade_to_premium(self, duration_days: int = 30):
        """Upgrade user to premium for specified duration"""
        self.is_premium = True
        self.plan_type = PlanType.PREMIUM
        if not self.premium_started_at:
            self.premium_started_at = datetime.utcnow()
        
        # Extend premium period
        current_time = datetime.utcnow()
        if self.premium_until and self.premium_until > current_time:
            # Extend existing premium
            self.premium_until += timedelta(days=duration_days)
        else:
            # New premium subscription
            self.premium_until = current_time + timedelta(days=duration_days)
        
        # Increase limits for premium users
        self.storage_limit = 50 * 1024 * 1024 * 1024  # 50GB for premium
        self.daily_download_limit = 10 * 1024 * 1024 * 1024  # 10GB/day for premium

class PaymentHistory(Base):
    __tablename__ = "payment_history"
    
    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    
    # Payment details
    payment_id = Column(String(100), unique=True, index=True, nullable=False)  # External payment ID
    amount = Column(Numeric(10, 2), nullable=False)  # Payment amount - using Numeric instead of Decimal
    currency = Column(String(3), default="USD")  # Currency code
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Plan information
    plan_type = Column(Enum(PlanType), nullable=False)
    duration_days = Column(Integer, nullable=False)  # Duration of the plan
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)  # When payment was processed
    expires_at = Column(DateTime, nullable=True)  # When the paid plan expires
    
    # Payment method and gateway info
    payment_method = Column(String(50), nullable=True)  # "stripe", "paypal", etc.
    gateway_response = Column(Text, nullable=True)  # JSON response from payment gateway
    
    # Relationships
    user = relationship("User", back_populates="payment_history")

class File(Base):
    __tablename__ = "files"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), unique=True, index=True, nullable=False)  # Keep this for backward compatibility
    filename = Column(String(255), nullable=False)  # Added length for filename
    original_filename = Column(String(255), nullable=False)  # Added length
    path = Column(Text, nullable=False)  # Use TEXT for potentially long paths
    file_size = Column(BigInteger)
    content_type = Column(String(100), nullable=True)  # Added length for MIME type
    upload_time = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)  # For consistency
    ttl = Column(Integer, default=0)  # 0 means no expiry
    download_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)  # New field for public/private sharing
    owner_id = Column(CHAR(36), ForeignKey("users.id"))
    
    # New field for file hash (SHA-256)
    file_hash = Column(String(64), nullable=True)  # SHA-256 is 64 hex chars

    owner = relationship("User", back_populates="files")
    
    def is_expired(self) -> bool:
        """Check if file has expired based on TTL"""
        if self.ttl == 0:  # 0 means no expiry
            return False
        expiry_time = self.upload_time + timedelta(hours=self.ttl)
        return datetime.utcnow() > expiry_time