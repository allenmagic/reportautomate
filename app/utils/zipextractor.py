import os
import zipfile
import logging
import subprocess
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def decode_filename(file_info) -> str:
    """尝试解码文件名，返回解码后的文件名"""
    try:
        filename = file_info.filename
        logger.debug(f"尝试以utf-8解码文件名: {filename}")
        filename.encode('utf-8').decode('utf-8')
    except UnicodeDecodeError:
        try:
            logger.debug(f"utf-8解码失败，尝试以gbk解码文件名: {filename}")
            filename = file_info.filename.encode('cp437').decode('gbk')
        except UnicodeDecodeError:
            logger.debug(f"gbk解码失败，尝试以utf-8替换解码文件名: {filename}")
            filename = file_info.filename.encode('cp437').decode('utf-8', 'replace')
    return filename

def find_files_dir(directory: str) -> str:
    """递归查找包含文件的目录，返回包含文件的目录路径"""
    logger.debug(f"查找目录中的文件: {directory}")
    entries = os.listdir(directory)
    if not entries:
        logger.debug(f"目录为空: {directory}")
        return directory

    has_files = False
    subdirs = []

    for entry in entries:
        full_path = os.path.join(directory, entry)
        if os.path.isfile(full_path):
            has_files = True
            logger.debug(f"找到文件: {full_path}")
        elif os.path.isdir(full_path):
            subdirs.append(full_path)
            logger.debug(f"找到子目录: {full_path}")

    if has_files:
        return directory

    if len(subdirs) == 1:
        return find_files_dir(subdirs[0])

    return directory


def extract_zip(zip_path: str, extract_dir: str, password: Optional[str] = None) -> Dict:
    """解压ZIP文件到指定目录，优先用zipfile，失败时自动用7z再试"""
    try:
        logger.info(f"开始解压文件: {zip_path} 到 {extract_dir}")
        os.makedirs(extract_dir, exist_ok=True)
        logger.info(f"创建解压目录: {extract_dir}")

        pwd = password.encode('utf-8') if password else None

        # 优先尝试标准zipfile
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                if any(info.flag_bits & 0x1 for info in zip_ref.infolist()) and not pwd:
                    logger.error("ZIP文件受密码保护，但未提供密码")
                    return {"success": False, "error": "ZIP文件受密码保护，请提供密码"}
                logger.debug(f"解压所有文件到: {extract_dir}")
                zip_ref.extractall(path=extract_dir, pwd=pwd)
        except (RuntimeError, zipfile.BadZipFile, NotImplementedError, OSError) as e:
            logger.warning(f"标准库zipfile解压失败，尝试使用7z工具处理。错误信息: {e}")
            # 组装7z命令
            cmd = ['7z', 'x', '-y', f'-o{extract_dir}']
            if password:
                cmd.append(f'-p{password}')
            cmd.append(zip_path)
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.debug(f"7z输出: {result.stdout}")
            if result.returncode != 0:
                logger.error(f"7z解压失败: {result.stderr.strip()}")
                return {"success": False, "error": f"7z解压失败: {result.stderr.strip()}"}

        # 检查解压目录，收集所有文件
        final_extract_dir = find_files_dir(extract_dir)
        logger.debug(f"最终解压目录: {final_extract_dir}")

        extracted_files = []
        for root, _, files in os.walk(final_extract_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, extract_dir)
                extracted_files.append({
                    "unzip_filename": file,
                    "unzip_filepath": relative_path,
                    "unzip_filesize": os.path.getsize(file_path)
                })

        logger.info(f"文件解压完成，共 {len(extracted_files)} 个文件")
        return {
            "success": True,
            "extracted_dir": final_extract_dir,
            "extracted_files": extracted_files
        }

    except Exception as e:
        logger.error(f"解压过程中发生异常: {str(e)}")
        return {"success": False, "error": f"解压异常: {str(e)}"}