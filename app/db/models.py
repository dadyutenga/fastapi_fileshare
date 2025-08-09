from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    files = relationship("File", back_populates="owner")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    path = Column(String, nullable=False)
    file_size = Column(BigInteger)
    content_type = Column(String)
    upload_time = Column(DateTime, default=datetime.utcnow)
    ttl = Column(Integer, default=0)  # 0 means no expiry
    download_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)  # New field for public/private sharing
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="files")