import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from app.core.config import settings
from app.utils.cleaner import cleanup_old_temp_files
from app.utils.downloader import download_file
from app.utils.filer import (extract_attachments_from_pdf, remove_pdf_password, split_pdf)
from app.utils.logger import logger
from app.utils.zipextractor import extract_zip

router = APIRouter()


# --- 数据模型 (无变化) ---
class ProcessRequest(BaseModel):
    task_id: str
    attachment_id: str
    download_url: HttpUrl
    attachment_name: Optional[str] = None
    unzip: Optional[bool] = False
    unzip_passwd: Optional[str] = None
    pdf_passwd: Optional[List[str]] = None
    split: Optional[List[int]] = None
    split_each_page: Optional[bool] = False
    with_attachments: Optional[bool] = False
    with_passwd: Optional[List[str]] = None


class FileInfo(BaseModel):
    file_id: str
    name: str
    path: str  # 注意：这里存储的是路径字符串，Path对象会被自动转换
    size: int


class ProcessedResponse(BaseModel):
    task_id: str
    attachment_id: str
    success: bool
    error: Optional[str] = None
    original_files: Optional[List[FileInfo]] = None
    unzip_files: Optional[List[FileInfo]] = None
    unlocked_files: Optional[List[FileInfo]] = None
    split_files: Optional[List[FileInfo]] = None
    attachment_files: Optional[List[FileInfo]] = None
    upload_files: Optional[List[FileInfo]] = None
    final_files: Optional[List[FileInfo]] = None


# --- API路由 ---
@router.post("/process_attachment", response_model=ProcessedResponse)
async def process_attachment(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    下载文件，并根据设置条件执行任务
    1. 下载文件
    2. 解压缩文件（unzip = True）
    3. 移除 PDF 密码（如果需要）
    4. 分割文件（如果需要）- 按照指定页数分割（split = [1, 2, 3]），或者按每页分割（split_each_page = True）
    5. 提取文档中的附件（如果需要）
    根据实际执行的任务返回相应结果，final_files 包含最终处理结果
    """

    # 1. 添加后台清理任务
    background_tasks.add_task(cleanup_old_temp_files)
    logger.debug("已添加后台清理任务")

    # 2. 主要业务逻辑
    logger.info(f"收到附件处理请求: task_id={request.task_id}, attachment_id={request.attachment_id}")

    # 【优化 1】使用 pathlib 创建任务目录
    task_dir: Path = settings.TEMP_DIR / request.task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"任务目录已准备就绪: {task_dir}")

    result_files = {
        "original_files": [], "unzip_files": [], "unlocked_files": [],
        "attachment_files": [], "split_files": []
    }

    # 1. 下载文件
    original_filename = request.attachment_name or f"{request.attachment_id}{'.zip' if request.unzip else ''}"
    logger.info(f"附件文件名称: {original_filename}")

    # 【优化 2】使用 pathlib 构建文件路径
    original_filepath: Path = task_dir / original_filename
    download_result = await download_file(str(request.download_url), original_filepath)

    if not download_result["success"]:
        logger.error(f"文件下载失败: {download_result['error']}")
        return ProcessedResponse(task_id=request.task_id, attachment_id=request.attachment_id, success=False,
                                 error=download_result["error"])

    logger.info(f"文件下载成功: {original_filepath}, 大小: {download_result['size']} 字节")
    original_filesize = download_result["size"]
    original_file_id = str(uuid.uuid4())
    logger.info(f"为原始文件生成 file_id: {original_file_id}")

    # 【优化 3】Pydantic模型会自动将Path对象转换为字符串
    result_files["original_files"].append(FileInfo(
        name=original_filename, path=str(original_filepath), size=original_filesize, file_id=original_file_id
    ))

    process_files = [{"filename": original_filename, "filepath": original_filepath, "filesize": original_filesize,
                      "file_id": original_file_id}]

    # 2. 处理解压缩
    if request.unzip:
        logger.info(f"开始解压文件: {original_filename}")
        extract_dir: Path = task_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)
        logger.info(f"创建解压目录: {extract_dir}")

        extract_result = extract_zip(original_filepath, extract_dir, request.unzip_passwd)
        if not extract_result["success"]:
            logger.error(extract_result["error"])
            return ProcessedResponse(task_id=request.task_id, attachment_id=request.attachment_id, success=False,
                                     error=extract_result["error"])

        logger.info(f"文件解压完成，共 {len(extract_result['extracted_files'])} 个文件")
        process_files = []
        for file_info in extract_result["extracted_files"]:
            # 假设 extract_zip 返回的 'unzip_filepath' 是相对于 extract_dir 的路径
            absolute_path: Path = extract_dir / file_info["unzip_filepath"]
            file_id = str(uuid.uuid4())
            result_files["unzip_files"].append(FileInfo(
                name=file_info["unzip_filename"], path=str(absolute_path), size=file_info["unzip_filesize"],
                file_id=file_id
            ))
            process_files.append({
                "filename": file_info["unzip_filename"], "filepath": absolute_path,
                "filesize": file_info["unzip_filesize"], "file_id": file_id
            })
        logger.info(f"添加解压文件, 共计 {len(result_files['unzip_files'])} 个文件")

    # 3. 处理PDF解密
    if request.pdf_passwd:
        logger.info(f"开始处理PDF解密...")
        unlocked_files = []
        unlocked_dir: Path = task_dir / 'unlocked'
        unlocked_dir.mkdir(exist_ok=True)

        for file_info in process_files:
            input_path = Path(file_info["filepath"])
            if input_path.suffix.lower() == '.pdf':
                # 【优化 4】使用 pathlib 的 .stem 和 .with_suffix() 优雅地构建新文件名
                output_name = f"{input_path.stem}_unlocked.pdf"
                output_path: Path = unlocked_dir / output_name

                if remove_pdf_password(input_path, output_path, request.pdf_passwd):
                    # 【优化 5】使用 pathlib 获取文件大小
                    file_size = output_path.stat().st_size
                    file_id = str(uuid.uuid4())
                    result_files["unlocked_files"].append(
                        FileInfo(name=output_name, path=str(output_path), size=file_size, file_id=file_id))
                    unlocked_files.append(
                        {"filename": output_name, "filepath": output_path, "filesize": file_size, "file_id": file_id})
                    logger.info(f"PDF解密成功: {input_path.name} -> {output_name}")
                else:
                    logger.warning(f"PDF 解密失败: {input_path.name}")
                    unlocked_files.append(file_info)
            else:
                unlocked_files.append(file_info)
        process_files = unlocked_files

    # 4. 处理文档中的附件
    if request.with_attachments:
        logger.info(f"开始提取PDF附件...")
        attachment_dir: Path = task_dir / 'attachments'
        attachment_dir.mkdir(exist_ok=True)
        logger.info(f"创建附件提取目录: {attachment_dir}")

        extracted_attachment_files = []
        for file_info in process_files:
            input_path = Path(file_info["filepath"])
            if input_path.suffix.lower() == '.pdf':
                logger.info(f"处理PDF文件以提取附件: {input_path.name}")
                try:
                    extracted = extract_attachments_from_pdf(input_path, attachment_dir, request.with_passwd)
                    if extracted:
                        logger.info(f"从 {input_path.name} 成功提取了 {len(extracted)} 个附件")
                        for attachment in extracted:
                            result_files["attachment_files"].append(FileInfo(**attachment))
                            extracted_attachment_files.append({
                                "filename": attachment["name"], "filepath": Path(attachment["path"]),
                                "filesize": attachment["size"], "file_id": attachment["file_id"]
                            })
                    else:
                        logger.info(f"{input_path.name} 中未发现附件")
                        extracted_attachment_files.append(file_info)
                except Exception as e:
                    logger.error(f"处理文件 {input_path.name} 提取附件时出错: {e}", exc_info=True)
                    extracted_attachment_files.append(file_info)
            else:
                extracted_attachment_files.append(file_info)
        process_files = extracted_attachment_files

    # 记录用于最终归档的文件
    upload_files = [FileInfo(name=f["filename"], path=str(f["filepath"]), size=f["filesize"], file_id=f["file_id"]) for
                    f in process_files]
    logger.info(f"记录用于上传的文件: 共计 {len(upload_files)} 个")

    # 5. 处理PDF分割
    if request.split or request.split_each_page:
        logger.info("开始处理PDF分割")
        split_files_list = []
        split_dir: Path = task_dir / 'split'
        split_dir.mkdir(exist_ok=True)

        for file_info in process_files:
            input_path = Path(file_info["filepath"])
            if input_path.suffix.lower() == '.pdf':
                pages = []
                split_each_page_mode = False
                if request.split:
                    pages = request.split
                    logger.info(f"使用指定页面分割模式 - 文件: {input_path.name}, 页面范围: {pages}")
                elif request.split_each_page:
                    try:
                        from PyPDF2 import PdfReader
                        reader = PdfReader(input_path)
                        pages = [0, len(reader.pages)]
                        split_each_page_mode = True
                        logger.info(f"使用每页分割模式 - 文件: {input_path.name}, 总页数: {pages[1]}")
                    except Exception as e:
                        logger.error(f"读取PDF文件 {input_path.name} 失败: {e}")
                        split_files_list.append(file_info)
                        continue

                split_result = split_pdf(input_pdf=input_path, output_dir=split_dir, pages=pages,
                                         split_each_page=split_each_page_mode)
                if split_result:
                    logger.info(f"PDF 分割成功 - 文件: {input_path.name}, 生成 {len(split_result)} 个文件")
                    for split_file in split_result:
                        file_id = str(uuid.uuid4())
                        result_files["split_files"].append(
                            FileInfo(name=split_file["name"], path=split_file["path"], size=split_file["size"],
                                     file_id=file_id))
                        split_files_list.append({"filename": split_file["name"], "filepath": Path(split_file["path"]),
                                                 "filesize": split_file["size"], "file_id": file_id})
                else:
                    logger.warning(f"PDF 分割失败: {input_path.name}")
                    split_files_list.append(file_info)
            else:
                split_files_list.append(file_info)
        process_files = split_files_list

    # 生成最终文件列表
    final_files = [FileInfo(name=f["filename"], path=str(f["filepath"]), size=f["filesize"], file_id=f["file_id"]) for f
                   in process_files]
    logger.info(f"最终可用于AI解析的文件共 {len(final_files)} 个")

    # 返回处理结果
    return ProcessedResponse(
        task_id=request.task_id, attachment_id=request.attachment_id, success=True,
        original_files=result_files["original_files"], unzip_files=result_files["unzip_files"],
        attachment_files=result_files["attachment_files"], unlocked_files=result_files["unlocked_files"],
        split_files=result_files["split_files"], upload_files=upload_files, final_files=final_files
    )
