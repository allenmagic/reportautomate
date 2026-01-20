from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from app.core.config import settings
from app.utils.logger import logger

router = APIRouter()


class FilePathRequest(BaseModel):
    file_path: str


@router.post("/download_by_path")
async def download_by_path(request: FilePathRequest):
    # 1. 将输入的字符串路径转换为 Path 对象
    # 注意：直接拼接路径可能存在安全风险，更好的方式是先解析
    user_path_str = request.file_path

    # 2. 解析为绝对路径并进行安全检查
    try:
        # resolve() 会解析路径，处理 ".." 等，并返回一个唯一的绝对路径
        abs_path = Path(user_path_str).resolve()

        # 【更严谨的安全检查】
        # 检查解析后的路径是否是 TEMP_DIR 的子路径或其本身
        if not abs_path.is_relative_to(settings.TEMP_DIR.resolve()):
            raise SecurityException()  # 抛出一个内部异常，统一处理

    except (FileNotFoundError, SecurityException):
        # 如果路径解析失败或安全检查失败
        logger.warning(
            f"访问被拒绝或路径无效：请求的路径 '{user_path_str}' 无法安全地解析到 '{settings.TEMP_DIR}' 内部。")
        raise HTTPException(status_code=403, detail="访问被拒绝或路径无效")

    # 3. 检查文件是否存在
    if not abs_path.is_file():
        logger.warning(f"请求的路径不是一个文件或文件不存在: {abs_path}")
        raise HTTPException(status_code=404, detail="文件不存在或路径不是文件")

    # 4. 返回文件响应
    # FileResponse 可以直接接受 Path 对象
    logger.info(f"正在提供文件下载: {abs_path}")
    return FileResponse(
        path=abs_path,
        filename=abs_path.name,  # 使用 .name 属性获取文件名
        media_type="application/octet-stream"
    )


# 定义一个内部使用的异常，用于逻辑跳转
class SecurityException(Exception):
    pass