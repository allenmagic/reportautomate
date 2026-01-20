from loguru import logger
from app.core.config import settings
import sys


def setup_logger():
    """
    打印程序执行的日志记录。

    Args:
        None

    Returns:
        str: 各种执行打印的信息。

    Examples:
        logger.debug("这是一条调试信息")  # 不会显示，因为级别是 INFO
        logger.info("这是一条信息")
        logger.warning("这是一条警告")
        logger.error("这是一条错误")

        Result
        2025-03-06 12:00:00.123 - INFO - 这是一条信息
        2025-03-06 12:00:00.124 - WARNING - 这是一条警告
        2025-03-06 12:00:00.125 - ERROR - 这是一条错误

    """

    logger.remove()  # 移除默认处理器

    # 配置日志格式，包含文件名、函数名和行号
    log_format = "{time} - {level} - {file}:{function}:{line} - {message}"

    logger.add(sys.stdout, format=log_format, level="DEBUG")
    logger.add(f"{settings.LOG_DIR}/statement.log", format=log_format, level="INFO", encoding="utf-8")

    return logger


logger = setup_logger()
