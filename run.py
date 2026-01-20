import uvicorn
import os
import socket
from app import app
from app.core.config import settings
from dotenv import load_dotenv
from app.utils.logger import logger

# 显式加载环境变量
load_dotenv()

# 打印关键环境变量（调试用）
logger.info(f"EXTRA_API_ID: {os.getenv('EXTRA_API_ID')}")
logger.info(f"ENVIRONMENT: {os.getenv('ENVIRONMENT')}")

if __name__ == "__main__":
    # 默认使用0.0.0.0绑定所有网络接口，也可通过APP_HOST环境变量覆盖
    host = os.getenv("APP_HOST", "0.0.0.0")
    logger.info(f"HOST: {host}")

    port = int(os.getenv("PORT", "8000"))

    logger.info(f"启动解压服务，环境: {settings.ENVIRONMENT}")
    logger.info(f"临时目录: {settings.TEMP_DIR}")
    logger.info(f"监听地址: {host}:{port}")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.DEBUG,
        log_level="info"
    )