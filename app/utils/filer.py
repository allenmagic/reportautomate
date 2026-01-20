import os
import re
import traceback
from datetime import datetime
from PyPDF2 import PdfReader, PdfWriter
from typing import Optional, List, Union, BinaryIO, Dict
import zipfile
import uuid
import pikepdf


from app.utils.logger import logger


def sanitize_filename(filename: str) -> str:
    """清理文件名，去除非法字符并限制长度。

    Args:
        filename: 原始文件名。

    Returns:
        清理后的安全文件名，如果无效返回空字符串。
    """
    if not filename:
        return ""

    # 移除非法字符（仅保留字母、数字、下划线、连字符和点）
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', filename.strip())
    # 替换空格为下划线
    safe_name = safe_name.replace(' ', '_')
    # 限制文件名长度（例如 255 个字符，考虑文件系统限制）
    safe_name = safe_name[:255]

    # 检查是否为空或仅包含点
    if not safe_name or safe_name.startswith('.') or safe_name == '.':
        return ""

    return safe_name


def save_attachment(folder: str, filename: str, content: Union[bytes, BinaryIO]) -> Optional[str]:
    """保存附件到指定文件夹，如果文件名存在则添加时间戳和计数器后缀。

    该函数将给定的二进制内容保存为文件，支持文件名清理。如果目标目录不存在，将自动创建。
    如果文件已存在，会添加时间戳后缀；如果时间戳文件名仍重复，则追加计数器，确保文件名唯一。

    Args:
        folder (str): 目标文件夹路径（相对或绝对路径）。
        filename (str): 附件文件名。
        content (Union[bytes, BinaryIO]): 文件内容，可以是字节数据或二进制文件对象。

    Returns:
        str or None: 保存成功的文件完整路径，失败返回 None。

    Raises:
        PermissionError: 如果无权限访问目录或文件。
        IOError: 如果写入文件时发生IO错误。

    """
    # 检查输入参数
    if not folder or not filename:
        logger.error("文件夹或文件名不能为空")
        return None

    # 清理文件名
    original_filename = filename
    sanitized_filename = sanitize_filename(filename)
    if not sanitized_filename:
        logger.warning(f"文件名无效: {repr(original_filename)}，无法保存")
        return None
    if sanitized_filename != original_filename:
        logger.warning(f"文件名已清理: '{original_filename}' -> '{sanitized_filename}'")

    # 构造目标路径
    target_dir = os.path.normpath(os.path.abspath(folder))
    base_filepath = os.path.join(target_dir, sanitized_filename)

    try:
        # 创建目录（如果不存在）
        os.makedirs(target_dir, exist_ok=True)
        logger.debug(f"确保目标目录存在: {target_dir}")

        # 检查文件是否已存在，并生成唯一文件名
        filepath = base_filepath
        if os.path.exists(filepath):
            base, ext = os.path.splitext(sanitized_filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')
            counter = 0
            new_filename = f"{base}_{timestamp}{ext}"
            filepath = os.path.join(target_dir, new_filename)

            # 如果时间戳文件名也存在，追加计数器
            while os.path.exists(filepath):
                counter += 1
                new_filename = f"{base}_{timestamp}_{counter}{ext}"
                filepath = os.path.join(target_dir, new_filename)

            logger.info(f"文件 '{sanitized_filename}' 已存在，重命名为: {new_filename}")

        # 保存文件
        if isinstance(content, bytes):
            with open(filepath, 'wb') as f:
                f.write(content)
        elif hasattr(content, 'read'):
            with open(filepath, 'wb') as f:
                f.write(content.read())
        else:
            logger.error(f"无效的内容类型: {type(content)}，必须是 bytes 或 BinaryIO")
            return None

        logger.info(f"文件已保存至: {filepath}")
        return filepath

    except PermissionError as e:
        logger.error(f"权限错误: 无法写入文件 {filepath}: {str(e)}")
        return None
    except IOError as e:
        logger.error(f"IO错误: {str(e)}，问题文件: {filepath}")
        return None
    except Exception as e:
        logger.error(f"保存附件时发生未知错误: {str(e)}")
        logger.debug(f"异常堆栈: {traceback.format_exc()}")
        return None


def remove_pdf_password(input_pdf: str, output_pdf: str, passwords: Union[str, List[str]]) -> bool:
    """尝试使用多个密码解密 PDF 文档，成功后保存为无密码 PDF 文件。

    该函数支持处理加密的 PDF 文件，使用提供的密码列表逐一尝试解密。如果解密成功，将生成一个无密码的 PDF 文件。
    如果输入 PDF 未加密，则直接复制内容到输出文件。函数会记录详细的日志，包括解密过程和错误信息。

    Args:
        input_pdf (str): 加密的 PDF 文件路径。
        output_pdf (str): 解密后保存的无密码文件路径。
        passwords (Union[str, List[str]]): 密码，可以是单个字符串或字符串列表。
            如果为空列表，将尝试使用空密码解密。

    Returns:
        bool: 解密成功返回 True，失败返回 False。

    Raises:
        FileNotFoundError: 如果输入 PDF 文件不存在。
        PermissionError: 如果无权限访问文件。

    """
    # 检查输入文件是否存在
    if not os.path.isfile(input_pdf):
        logger.error(f"输入 PDF 文件不存在: {input_pdf}")
        return False

    # 规范化密码参数为列表
    if isinstance(passwords, str):
        passwords = [passwords]
    elif not isinstance(passwords, list):
        logger.warning(f"密码参数类型无效: {type(passwords)}，转换为列表")
        passwords = [str(passwords)]

    # 如果密码列表为空，尝试空密码
    if not passwords:
        passwords = ['']
        logger.debug("密码列表为空，将尝试使用空密码解密")

    logger.info(f"开始处理 PDF 文件: {input_pdf}，尝试使用 {len(passwords)} 个密码")

    try:
        # 加载 PDF 文件
        reader = PdfReader(input_pdf)

        # 检查是否加密
        if reader.is_encrypted:
            logger.info(f"检测到 {input_pdf} 是加密文件，开始解密尝试...")

            password_found = False
            for i, password in enumerate(passwords, 1):
                try:
                    if reader.decrypt(password):
                        logger.info(f"密码尝试 {i}/{len(passwords)}: 使用 '{password}' 成功解密 PDF")
                        password_found = True
                        break
                except Exception as e:
                    logger.debug(f"密码尝试 {i}/{len(passwords)}: '{password}' 失败: {str(e)}")

            if not password_found:
                logger.error("无法使用提供的任何密码解密 PDF，解密失败")
                return False
        else:
            logger.info(f"PDF 文件 {input_pdf} 未加密，无需解密")

        # 创建无密码的 PDF
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_pdf) or '.', exist_ok=True)

        # 保存无密码 PDF
        with open(output_pdf, "wb") as f:
            writer.write(f)

        logger.info(f"已成功移除密码，保存到: {output_pdf}")
        return True

    except PermissionError as e:
        logger.error(f"权限错误，无法处理 PDF 文件: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"处理 PDF 解密时发生错误: {str(e)}")
        logger.debug(f"异常堆栈: {traceback.format_exc()}")
        return False


def split_pdf(input_pdf: str, output_dir: str, pages: List[int], split_each_page: bool = False) -> List[dict]:
    """
    拆分 PDF 文件到指定页面范围
    :param input_pdf: 输入 PDF 文件路径
    :param output_dir: 输出目录
    :param pages: 页面范围列表，例如 [1, 3], [1], [-1], [-3, -6]
    :param split_each_page: 是否将每个页面分割成单独的文件，默认 False
    :return: 拆分后的文件信息列表 [{name, path, size}]
    """
    try:
        logger.info(f"开始拆分 PDF 文件: {input_pdf}")
        logger.info(f"目标输出目录: {output_dir}")
        logger.info(f"指定页面范围: {pages}")
        logger.info(f"每页单独分割: {split_each_page}")

        # 读取 PDF 文件
        logger.debug(f"正在读取 PDF 文件: {input_pdf}")
        reader = PdfReader(input_pdf)
        total_pages = len(reader.pages)
        logger.info(f"PDF 文件总页数: {total_pages}")

        # 解析页面范围
        logger.debug(f"解析页面范围: {pages}")
        if len(pages) == 1:
            start = end = pages[0]
            logger.info(f"单页模式: 起始页 = 结束页 = {start}")
        elif len(pages) == 2:
            start, end = pages
            logger.info(f"范围模式: 起始页 = {start}, 结束页 = {end}")
        else:
            raise ValueError("pages 参数必须为 1 或 2 个元素")

        # 处理负数索引（倒数页面）
        if start < 0:
            original_start = start
            start = total_pages + start
            logger.info(f"处理负数索引: {original_start} -> {start}")
        if end < 0:
            original_end = end
            end = total_pages + end
            logger.info(f"处理负数索引: {original_end} -> {end}")

        # 确保范围有效
        logger.debug(f"调整页面范围: start={start}, end={end}, total_pages={total_pages}")
        start = max(0, min(start, total_pages - 1))  # 从 0 开始计数
        end = max(0, min(end, total_pages - 1))
        if start > end:
            start, end = end, start  # 如果顺序反了，交换
            logger.info(f"页面顺序调整: start={start}, end={end}")
        logger.info(f"最终页面范围: {start + 1} 至 {end + 1} (索引 {start} 至 {end})")

        # 拆分 PDF
        split_files = []
        base_name = os.path.splitext(os.path.basename(input_pdf))[0]

        if split_each_page:
            # 每个页面分割成单独的文件
            logger.info("开始按页面单独分割")
            for i in range(start, end + 1):
                writer = PdfWriter()
                writer.add_page(reader.pages[i])

                # 生成单页输出文件名
                output_file = os.path.join(output_dir, f"{base_name}_page_{i + 1}.pdf")
                logger.debug(f"生成单页文件: {output_file}")

                # 写入单页文件
                with open(output_file, 'wb') as f:
                    writer.write(f)
                file_size = os.path.getsize(output_file)
                logger.info(f"单页文件完成: {output_file}, 大小: {file_size} 字节")

                # 添加到结果列表
                split_files.append({
                    "name": os.path.basename(output_file),
                    "path": output_file,
                    "size": file_size
                })
        else:
            # 原有逻辑：将指定范围合并为一个文件
            writer = PdfWriter()
            logger.debug(f"开始拆分页面: {start} 至 {end}")
            for i in range(start, end + 1):
                writer.add_page(reader.pages[i])
                logger.debug(f"添加页面: {i + 1} (索引 {i})")

            # 生成输出文件名
            output_file = os.path.join(output_dir, f"{base_name}_split_{start + 1}-{end + 1}.pdf")
            logger.info(f"生成输出文件路径: {output_file}")

            # 写入文件
            logger.debug(f"正在写入拆分后的 PDF 文件: {output_file}")
            with open(output_file, 'wb') as f:
                writer.write(f)
            file_size = os.path.getsize(output_file)
            logger.info(f"拆分完成，文件大小: {file_size} 字节")

            # 返回拆分文件信息
            split_files.append({
                "name": os.path.basename(output_file),
                "path": output_file,
                "size": file_size
            })

        logger.debug(f"返回拆分文件信息: {split_files}")
        return split_files

    except Exception as e:
        logger.error(f"PDF 拆分失败: {e}", exc_info=True)  # 打印异常堆栈
        return []


def extract_attachments_from_pdf(pdf_path: str, output_folder: str, password: Optional[Union[str, List[str]]] = None) -> \
List[Dict]:
    """
    从PDF文件中提取附件，支持加密和非加密的PDF

    :param pdf_path: PDF文件的路径
    :param output_folder: 提取的附件保存的文件夹路径
    :param password: PDF文件的密码，如果PDF受密码保护则需提供，可以是单个字符串或密码列表，默认为None
    :return: 包含提取附件信息的字典列表，每个字典包含file_id, name, path, size等信息
    """
    # 确保输出文件夹存在
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"创建输出文件夹：{output_folder}")

    # 初始化结果列表
    result = []
    pdf = None

    try:
        # 尝试打开PDF文件
        try:
            # 首先尝试无密码打开
            pdf = pikepdf.Pdf.open(pdf_path)
        except pikepdf.PasswordError:
            # 如果需要密码
            if password is not None:
                # 处理密码列表
                if isinstance(password, list):
                    # 逐一尝试每个密码
                    for pwd in password:
                        try:
                            pdf = pikepdf.Pdf.open(pdf_path, password=pwd)
                            print(f"使用密码 '{pwd}' 成功打开PDF文件")
                            break
                        except pikepdf.PasswordError:
                            continue

                    if pdf is None:
                        raise pikepdf.PasswordError("所有提供的密码均无法打开PDF文件")
                else:
                    # 单个密码
                    pdf = pikepdf.Pdf.open(pdf_path, password=password)
            else:
                raise pikepdf.PasswordError("PDF文件受密码保护，但未提供密码")

        # 检查PDF是否有附件
        if not hasattr(pdf, 'attachments') or not pdf.attachments:
            print(f"PDF文件 {pdf_path} 没有附件")
            return result

        # 遍历PDF文档中的所有附件
        for attachment_name, attachment in pdf.attachments.items():
            # 获取原始文件名
            file_name = attachment.filename
            output_path = os.path.join(output_folder, file_name)

            # 确保文件名不重复
            if os.path.exists(output_path):
                base_name, extension = os.path.splitext(file_name)
                counter = 1
                while os.path.exists(output_path):
                    new_name = f"{base_name}_{counter}{extension}"
                    output_path = os.path.join(output_folder, new_name)
                    counter += 1
                file_name = os.path.basename(output_path)

            # 提取并保存附件内容
            with open(output_path, "wb") as f:
                file_content = attachment.get_file().read_bytes()
                f.write(file_content)

            # 获取文件大小
            file_size = os.path.getsize(output_path)

            # 生成唯一ID
            file_id = str(uuid.uuid4())

            # 添加到结果列表
            result.append({
                "file_id": file_id,
                "name": file_name,
                "path": output_path,
                "size": file_size
            })

            print(f"附件 '{file_name}' 已提取并保存到：{output_path}，大小：{file_size} 字节")

    except pikepdf.PasswordError as e:
        print(f"PDF密码错误: {e}")
        raise
    except pikepdf.PdfError as e:
        print(f"处理PDF文件时出错: {e}")
        raise
    except Exception as e:
        print(f"提取附件时发生未知错误: {e}")
        raise
    finally:
        # 确保PDF文件被关闭
        if pdf is not None:
            pdf.close()

    return result