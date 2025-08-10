from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, BigInteger, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta

from .base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)  # Added length
    hashed_password = Column(String(255), nullable=False)  # Added length for password hash
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # New fields for storage and download limits
    storage_limit = Column(BigInteger, default=5 * 1024 * 1024 * 1024)  # 5GB default
    daily_download_limit = Column(BigInteger, default=1 * 1024 * 1024 * 1024)  # 1GB/day default
    storage_used = Column(BigInteger, default=0)  # Current storage usage
    last_download_reset = Column(DateTime, default=datetime.utcnow)  # Track daily reset
    daily_downloads_used = Column(BigInteger, default=0)  # Daily download usage

    files = relationship("File", back_populates="owner")
    
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

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID is 36 chars
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
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # New field for file hash (SHA-256)
    file_hash = Column(String(64), nullable=True)  # SHA-256 is 64 hex chars

    owner = relationship("User", back_populates="files")
    
    def is_expired(self) -> bool:
        """Check if file has expired based on TTL"""
        if self.ttl <= 0:
            return False
        expiry_time = self.upload_time + timedelta(hours=self.ttl)
        return datetime.utcnow() > expiry_time