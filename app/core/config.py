import os
from pathlib import Path
from typing import List, Set, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 项目基本信息
    PROJECT_NAME: str = "文件解压和移除PDF密码服务"
    VERSION: str = "1.0.0"

    # 环境设置
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # API设置
    API_KEYS: Dict[str, str] = {
        "anycross_doc": "Cpe123456"  # 默认开发凭证
    }

    # 如果提供了额外的API凭证，添加它们
    EXTRA_API_ID: str = os.getenv("EXTRA_API_ID", "")
    EXTRA_API_SECRET: str = os.getenv("EXTRA_API_SECRET", "")
    if EXTRA_API_ID and EXTRA_API_SECRET:
        API_KEYS[EXTRA_API_ID] = EXTRA_API_SECRET

    # CORS设置
    ALLOWED_ORIGINS: List[str] = ["*"]

    # 目录设置
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    LOG_DIR: Path = BASE_DIR / "logs"
    TEMP_DIR: Path = BASE_DIR / "temp"
    RSCRIPT_DIR: Path = BASE_DIR / "app" / "r_scripts"
    SQL_DIR: Path = BASE_DIR / "r_scripts" / "sql"
    TEMPLATE_DIR: Path = BASE_DIR / "app" / "templates"
    FONT_DIR: Path = BASE_DIR / "resources" / "fonts"

    # 文件下载设置
    DOWNLOAD_TIMEOUT: int = 180  # 下载超时时间(秒)
    MAX_DOWNLOAD_SIZE: int = 1024 * 1024 * 100  # 最大下载大小(100MB)

    # Pydantic配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )


# 创建设置实例
settings = Settings()

# 确保临时目录存在
os.makedirs(settings.TEMP_DIR, exist_ok=True)

# 在开发环境输出警告
if settings.ENVIRONMENT == "dev" and "default-app-id" in settings.API_KEYS:
    import warnings

    warnings.warn("⚠️ 使用默认API凭证，仅用于开发环境")
