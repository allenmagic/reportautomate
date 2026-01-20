import os
import aiohttp
import aiofiles
import logging
from typing import Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


async def download_file(url: str, save_path: str) -> Dict:
    """下载文件并保存到指定路径"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # 设置超时
        timeout = aiohttp.ClientTimeout(total=settings.DOWNLOAD_TIMEOUT)

        # 开始下载
        logger.info(f"开始下载文件: {url}")
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"下载失败，HTTP状态码: {response.status}")
                    return {"success": False, "error": f"下载失败，HTTP状态码: {response.status}"}

                # 获取文件大小
                content_length = int(response.headers.get("Content-Length", 0))
                if content_length > settings.MAX_DOWNLOAD_SIZE:
                    logger.error(f"文件大小超过限制: {content_length} > {settings.MAX_DOWNLOAD_SIZE}")
                    return {"success": False, "error": "文件大小超过限制"}

                # 保存文件
                async with aiofiles.open(save_path, "wb") as f:
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(8192):
                        downloaded += len(chunk)
                        await f.write(chunk)

                        # 检查下载大小是否超过限制
                        if downloaded > settings.MAX_DOWNLOAD_SIZE:
                            logger.error(f"下载中止，文件大小超过限制: {downloaded}")
                            await f.close()
                            os.remove(save_path)
                            return {"success": False, "error": "文件大小超过限制"}

        # 检查文件是否存在且大小大于0
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            logger.error(f"下载完成，但文件为空或不存在: {save_path}")
            return {"success": False, "error": "下载的文件为空或不存在"}

        logger.info(f"文件下载完成: {save_path}, 大小: {os.path.getsize(save_path)} 字节")
        return {"success": True, "path": save_path, "size": os.path.getsize(save_path)}

    except aiohttp.ClientError as e:
        logger.error(f"下载出现客户端错误: {str(e)}")
        return {"success": False, "error": f"下载错误: {str(e)}"}
    except Exception as e:
        logger.error(f"下载过程中发生异常: {str(e)}")
        return {"success": False, "error": f"下载异常: {str(e)}"}
