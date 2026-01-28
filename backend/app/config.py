"""
应用配置文件
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_NAME: str = "共享CFO API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MongoDB配置
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_USERNAME: str = ""
    MONGO_PASSWORD: str = ""
    MONGO_DATABASE: str = "shared_cfo"
    MONGO_COLLECTION: str = "policies"

    # Qdrant配置
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "tax_policies"
    QDRANT_API_KEY: Optional[str] = None

    # GLM配置
    GLM_API_KEY: str = ""
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4/"
    GLM_MODEL: str = "glm-4-flash"
    GLM_EMBEDDING_MODEL: str = "embedding-2"

    # CORS配置
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # JWT配置（预留）
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def mongo_url(self) -> str:
        """MongoDB连接URL"""
        if self.MONGO_USERNAME and self.MONGO_PASSWORD:
            return f"mongodb://{self.MONGO_USERNAME}:{self.MONGO_PASSWORD}@{self.MONGO_HOST}:{self.MONGO_PORT}"
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}"

    @property
    def qdrant_url(self) -> str:
        """Qdrant连接URL"""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 全局配置实例
settings = get_settings()
