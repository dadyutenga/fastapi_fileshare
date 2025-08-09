from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "sqlite:///./file_share.db"  # SQLite for simple deployment
    
    # Upload settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 524288000  # 500MB (500 * 1024 * 1024)
    CHUNK_SIZE: int = 2097152  # 2MB chunks for better performance
    ALLOWED_EXTENSIONS: str = ".jpg,.jpeg,.png,.gif,.bmp,.tiff,.webp,.svg,.ico,.pdf,.txt,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.rar,.mp4,.7z,.tar,.gz,.mp3,.mp4,.avi,.mov,.wmv,.flv,.mkv,.webm,.wav,.ogg,.aac,.csv,.json,.xml,.html,.css,.js,.py,.java,.cpp,.c,.h,.php,.sql,.md,.rtf,.odt,.ods,.odp,.epub,.mobi,.psd,.ai,.eps,.dwg,.dxf,.stl,.obj,.fbx,.blend,.iso,.dmg,.exe,.msi,.deb,.rpm,.tar.xz,.tar.bz2,.avi,.mkv,.m4v,.3gp,.flac,.m4a,.wma"
    
    # App settings
    APP_NAME: str = "FileShare Portal"
    APP_VERSION: str = "2.0.0"

    class Config:
        env_file = ".env"
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

settings = Settings()