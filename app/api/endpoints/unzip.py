import os
import shutil
from typing import List, Optional, Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException, Form, Response, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from app.utils.logger import logger
from app.utils.downloader import download_file
from app.utils.zipextractor import extract_zip
from app.core.config import settings
from app.utils.filer import remove_pdf_password, split_pdf

router = APIRouter()


# 数据模型
class UnzipRequest(BaseModel):
    task_id: str
    attachment_id: str
    download_url: HttpUrl
    unzip_passwd: Optional[str] = None   # ZIP 文件解压密码（可选）
    pdf_passwd: Optional[List[str]] = None  # PDF 文件解密密码列表（可选）
    split: Optional[List[int]] = None  # split 参数（可选）


class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    split_file_name: Optional[str]
    split_file_size: Optional[int]
    split_file_path: Optional[str]


class UnzipResponse(BaseModel):
    task_id: str
    attachment_id: str
    success: bool
    error: Optional[str] = None
    extracted_files: Optional[List[FileInfo]] = None
    temp_dir: Optional[str] = None
    content: Optional[str] = None


# 用于存储任务状态的简单内存字典
task_status = {}


# 清理临时文件的函数
def cleanup_temp_files(task_dir: str):
    try:
        if os.path.exists(task_dir) and task_dir.startswith(settings.TEMP_DIR):
            shutil.rmtree(task_dir)
            logger.info(f"已清理临时目录: {task_dir}")
            # 从任务状态中移除
            task_id = os.path.basename(task_dir)
            if task_id in task_status:
                del task_status[task_id]
        else:
            logger.warning(f"拒绝清理目录，可能在非法路径: {task_dir}")
    except Exception as e:
        logger.error(f"清理错误: {str(e)}")


# API路由
@router.post("/unzip", response_model=UnzipResponse)
async def unzip_file(request: UnzipRequest, background_tasks: BackgroundTasks):
    """
    下载并解压ZIP文件，并生成点击下载的URL
    """
    logger.info(f"收到解压请求: task_id={request.task_id}, attachment_id={request.attachment_id}")

    # 创建任务目录
    task_dir = os.path.join(settings.TEMP_DIR, request.task_id)
    os.makedirs(task_dir, exist_ok=True)

    # 保存 ZIP 文件路径
    save_filename = f"{request.attachment_id}.zip"
    save_path = os.path.join(task_dir, save_filename)

    # 下载文件
    download_result = await download_file(str(request.download_url), save_path)
    if not download_result["success"]:
        return UnzipResponse(
            task_id=request.task_id,
            attachment_id=request.attachment_id,
            success=False,
            error=download_result["error"]
        )

    # 创建解压目录
    extract_dir = os.path.join(task_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    # 解压文件
    extract_result = extract_zip(save_path, extract_dir, request.unzip_passwd)
    if not extract_result["success"]:
        return UnzipResponse(
            task_id=request.task_id,
            attachment_id=request.attachment_id,
            success=False,
            error=extract_result["error"]
        )

    # 使用 extract_result 中的 final_extract_dir
    extract_dir = extract_result["extracted_dir"]

    # 遍历解压结果文件，处理 PDF 解密(如有)并生成下载链接
    extracted_files_info = []
    for file_data in extract_result["extracted_files"]:
        file_name = file_data["name"]  # 获取文件名
        original_file_path = os.path.join(extract_dir, file_name)  # 解压缩后的文件路径

        # 如果提供了 pdf_passwd 且文件是 PDF，则尝试解密
        if request.pdf_passwd and file_name.lower().endswith('.pdf'):
            output_file_name = f"{os.path.splitext(file_name)[0]}_unlocked.pdf"  # 无密码文件另存为新文件名
            output_file_path = os.path.join(extract_dir, output_file_name)

            # 调用解密函数
            success = remove_pdf_password(original_file_path, output_file_path, request.pdf_passwd)
            if success:
                # 解密成功，使用无密码的文件
                file_name = output_file_name
                file_path = output_file_path
                file_size = os.path.getsize(file_path)  # 更新文件大小
            else:
                # 解密失败，保留原始文件并记录警告
                logger.warning(f"PDF 解密失败: {file_name}")
                file_path = original_file_path
                file_size = file_data["size"]
        else:
            # 非 PDF 文件或未提供密码，直接使用原始文件
            file_path = original_file_path
            file_size = file_data["size"]


        # 构建下载链接
        base_url = os.getenv("BASE_URL", "http://localhost:8000")  # 简化默认值
        download_url = f"{base_url}/api/pdf/download/{request.task_id}/{file_name}"  # 构建API方式下载链接

        # 如果提供了 split 参数，执行拆分
        split_download_url = None
        split_file_name = None
        split_file_size = None
        if request.split:
            split_files = split_pdf(file_path, extract_dir, request.split)
            if split_files:
                # 取第一个拆分文件（假设每次只生成一个拆分文件）
                split_file = split_files[0]
                split_download_url = f"{base_url}/api/pdf/download/{request.task_id}/{split_file['name']}"
                split_file_name = split_file["name"]
                split_file_size = split_file["size"]
            else:
                logger.warning(f"PDF 拆分失败: {file_name}")

        # 构建返回信息
        extracted_files_info.append(FileInfo(
            name=file_name,
            path=download_url,  # 使用下载链接代替物理路径
            size=file_size,
            split_file_name=split_file_name,
            split_file_size=split_file_size,
            split_file_path=split_download_url
        ))

    # 返回最终响应结果
    return UnzipResponse(
        task_id=request.task_id,
        attachment_id=request.attachment_id,
        success=True,
        extracted_files=extracted_files_info,  # 包含了完整的文件列表和下载链接
        temp_dir=task_dir
    )


@router.get("/download/{file_path}")
async def download_final_file(file_path: str):
    # 构造文件的绝对路径 (基于 temp 目录)
    final_file_path = file_path

    # 检查文件是否存在
    if not os.path.exists(final_file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # 返回文件作为下载响应
    return FileResponse(path=final_file_path, media_type="application/octet-stream")


@router.get("/files/{task_id}")
async def get_task_files(task_id: str):
    """
    获取任务的文件列表

    - **task_id**: 任务ID
    """
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在或已被清理")

    task_info = task_status[task_id]
    return {
        "task_id": task_id,
        "attachment_id": task_info["attachment_id"],
        "state": task_info["state"],
        "extracted_files": task_info["extracted_files"]
    }


@router.delete("/cleanup/{task_id}")
async def cleanup_task(task_id: str):
    """
    清理任务的临时文件

    - **task_id**: 任务ID
    """
    task_dir = os.path.join(settings.TEMP_DIR, task_id)

    if not os.path.exists(task_dir):
        return {"message": "任务目录不存在或已被清理"}

    cleanup_temp_files(task_dir)
    return {"message": f"任务 {task_id} 的临时文件已清理"}
