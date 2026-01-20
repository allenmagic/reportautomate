# utils/cleaner.py

import os
import time
import shutil
import glob
from datetime import datetime, timedelta
from app.core.config import settings
from app.utils.logger import logger


def cleanup_old_temp_files(max_age_hours: int = 24):
    """
    清理超过指定小时数的临时文件（后台任务）

    Args:
        max_age_hours: 文件保留时长（小时），默认24小时

    Returns:
        dict: 包含删除数量和错误数量的字典
    """
    temp_dir = settings.TEMP_DIR
    current_time = time.time()
    cutoff_time = current_time - (max_age_hours * 3600)

    deleted_count = 0
    error_count = 0

    logger.info(f"[后台任务] 开始清理 {max_age_hours} 小时前的临时文件...")

    try:
        # 确保临时目录存在
        if not os.path.exists(temp_dir):
            logger.warning(f"临时目录不存在: {temp_dir}")
            return {"deleted": 0, "errors": 0}

        # 遍历temp目录下的所有子目录和文件
        for entry in os.listdir(temp_dir):
            entry_path = os.path.join(temp_dir, entry)

            # 跳过.gitkeep文件
            if entry == '.gitkeep':
                continue

            try:
                # 获取文件/目录的最后修改时间
                mtime = os.path.getmtime(entry_path)

                # 如果文件/目录太旧，删除它
                if mtime < cutoff_time:
                    if os.path.isdir(entry_path):
                        shutil.rmtree(entry_path)
                        logger.debug(f"[后台任务] 删除过期临时目录: {entry_path}")
                    else:
                        os.remove(entry_path)
                        logger.debug(f"[后台任务] 删除过期临时文件: {entry_path}")
                    deleted_count += 1

            except PermissionError as e:
                error_count += 1
                logger.error(f"[后台任务] 权限不足，无法删除 {entry_path}: {str(e)}")
            except Exception as e:
                error_count += 1
                logger.error(f"[后台任务] 清理 {entry_path} 时出错: {str(e)}")

    except Exception as e:
        logger.error(f"[后台任务] 清理临时文件时发生异常: {str(e)}", exc_info=True)
        return {"deleted": deleted_count, "errors": error_count + 1}

    logger.info(f"[后台任务] 临时文件清理完成: 删除了 {deleted_count} 个项目, 有 {error_count} 个错误")
    return {"deleted": deleted_count, "errors": error_count}


def cleanup_feather_files(directory="dataroom", days_to_keep=7):
    """清理指定目录下超过一定天数的feather文件"""
    try:
        # 获取当前时间
        now = datetime.now()
        # 查找目录下所有feather文件
        pattern = os.path.join(directory, "citi_monthly_statement_*.feather")
        feather_files = glob.glob(pattern)

        deleted_count = 0
        for file_path in feather_files:
            # 获取文件的修改时间
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            # 如果文件超过指定天数，则删除
            if now - file_mtime > timedelta(days=days_to_keep):
                os.remove(file_path)
                deleted_count += 1
                logger.info(f"已删除过期feather文件: {file_path}")

        return deleted_count
    except Exception as e:
        logger.error(f"清理feather文件时出错: {str(e)}")
        return 0