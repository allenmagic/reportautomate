from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional
import urllib.parse
import msal
import requests
import os

# 设置日志
from app.utils.logger import logger

router = APIRouter()


# 定义嵌套模型
class ClientInfo(BaseModel):
    client_id: str = Field(..., description="Microsoft应用程序客户端ID")
    client_secret: str = Field(..., description="Microsoft应用程序客户端密钥")


class TenantInfo(BaseModel):
    tenant_id: str = Field(..., description="Microsoft租户ID")
    tenant_name: str = Field(..., description="Microsoft租户名称")


class UploadFileInfo(BaseModel):
    site_name: str = Field(..., description="SharePoint站点名称")
    folder_path: str = Field(..., description="上传文件的文件夹路径，例如：'香港分公司/Bank/eStatement'")
    file_name: Optional[str] = Field(None, description="文件名称（如果不提供，将使用上传文件的原始名称）")
    local_path: str = Field(..., description="文件在服务器上的本地路径")


# 完整请求模型
class UploadSharepointFileRequest(BaseModel):
    client_info: ClientInfo
    tenant_info: TenantInfo
    upload_info: UploadFileInfo


# 响应模型
class UploadSharepointFileResponse(BaseModel):
    success: bool
    message: str
    file_url: Optional[str] = None
    file_id: Optional[str] = None

# 新的文件移动信息模型
class MoveFileInfo(BaseModel):
    file_id: str = Field(..., description="要移动的文件的 Graph Drive Item ID (从上传接口获取)")
    site_name: str = Field(..., description="SharePoint 站点名称")
    # 注意：新的 target_folder_path 应该是相对路径 (e.g., '新的目录/子目录')
    target_folder_path: str = Field(..., description="目标文件夹的路径（在默认文档库内，例如：'香港分公司/新的目录'）")
    new_file_name: Optional[str] = Field(None, description="移动后重命名的新文件名称（可选，如果不提供，则保留原名）")


# 完整的请求模型
class MoveSharepointFileRequest(BaseModel):
    client_info: ClientInfo
    tenant_info: TenantInfo
    move_info: MoveFileInfo


@router.post("/upload_file_to_sharepoint_simple", response_model=UploadSharepointFileResponse)
async def upload_file_to_sharepoint(
        request: UploadSharepointFileRequest = Body(...)
):
    """
    上传文件到SharePoint指定文件夹

    接收一个JSON对象，包含所有必要参数，包括文件的本地路径
    """
    # 从请求中获取文件路径
    local_path = request.upload_info.local_path

    # 确保文件存在
    if not os.path.exists(local_path):
        error_msg = f"文件不存在: {local_path}"
        logger.error(error_msg)
        return UploadSharepointFileResponse(success=False, message=error_msg)

    # 确定文件名
    file_name = request.upload_info.file_name or os.path.basename(local_path)

    try:
        logger.info(f"准备上传文件到SharePoint: {file_name}")

        # 获取访问令牌
        authority = f"https://login.microsoftonline.com/{request.tenant_info.tenant_id}"
        scope = ["https://graph.microsoft.com/.default"]

        app = msal.ConfidentialClientApplication(
            request.client_info.client_id,
            authority=authority,
            client_credential=request.client_info.client_secret
        )
        result = app.acquire_token_for_client(scopes=scope)
        access_token = result.get("access_token")

        if not access_token:
            error_msg = f"获取令牌失败: {result.get('error_description', '未知错误')}"
            logger.error(error_msg)
            return UploadSharepointFileResponse(success=False, message=error_msg)

        logger.info("成功获取访问令牌")

        # 设置上传请求头
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        upload_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream"
        }

        # 1. 获取站点信息
        logger.info(f"正在获取SharePoint站点信息: {request.upload_info.site_name}")
        graph_site_url = f"https://graph.microsoft.com/v1.0/sites/{request.tenant_info.tenant_name}.sharepoint.com:/sites/{request.upload_info.site_name}"
        site_response = requests.get(graph_site_url, headers=headers)

        if site_response.status_code != 200:
            error_msg = f"获取站点信息失败: {site_response.text}"
            logger.error(error_msg)
            return UploadSharepointFileResponse(success=False, message=error_msg)

        # 解析站点ID
        site_info = site_response.json()
        site_id = site_info.get("id")
        logger.info(f"成功获取站点ID: {site_id}")

        # 2. 获取所有文档库
        logger.info("获取站点的驱动器/文档库")
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        drives_response = requests.get(drives_url, headers=headers)

        if drives_response.status_code != 200:
            error_msg = f"获取文档库失败: {drives_response.text}"
            logger.error(error_msg)
            return UploadSharepointFileResponse(success=False, message=error_msg)

        drives = drives_response.json().get("value", [])

        if not drives:
            error_msg = "未找到任何文档库"
            logger.error(error_msg)
            return UploadSharepointFileResponse(success=False, message=error_msg)

        # 打印所有文档库信息
        for drive in drives:
            logger.info(f"找到文档库: ID={drive.get('id')}, 名称={drive.get('name')}")

        # 选择默认文档库（通常是第一个）
        drive = drives[0]
        drive_id = drive.get("id")
        logger.info(f"使用文档库: {drive.get('name')} (ID: {drive_id})")

        # 3. 处理文件夹路径
        folder_path = request.upload_info.folder_path
        if folder_path.startswith('/'):
            folder_path = folder_path[1:]
        if folder_path.endswith('/'):
            folder_path = folder_path[:-1]

        logger.info(f"上传路径: {folder_path}/{file_name}")

        # 构建上传URL
        upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{folder_path}/{file_name}:/content"
        logger.info(f"上传URL: {upload_url}")

        # 上传文件
        file_size = os.path.getsize(local_path)
        logger.info(f"上传文件大小: {file_size} 字节")

        with open(local_path, "rb") as f:
            logger.debug("发送上传请求...")
            upload_response = requests.put(upload_url, headers=upload_headers, data=f)

        if upload_response.status_code in [200, 201]:
            file_info = upload_response.json()
            file_url = file_info.get("webUrl")
            file_id = file_info.get("id")
            logger.info(f"文件上传成功！访问URL: {file_url}")
            return UploadSharepointFileResponse(
                success=True,
                message="文件上传成功",
                file_url=file_url,
                file_id=file_id
            )
        else:
            error_msg = f"上传失败，状态码：{upload_response.status_code}, 响应：{upload_response.text}"
            logger.error(error_msg)
            return UploadSharepointFileResponse(success=False, message=error_msg)

    except Exception as e:
        error_msg = f"上传过程中发生错误: {str(e)}"
        logger.exception(error_msg)
        return UploadSharepointFileResponse(success=False, message=error_msg)


# ----------------------------------------------------
# 辅助函数：递归创建目标路径
# ----------------------------------------------------

def ensure_path_exists(drive_id: str, access_token: str, folder_path: str) -> tuple[bool, str]:
    """
    检查路径是否存在，如果不存在，则逐级创建路径。

    返回: (是否成功, 最终文件夹ID或错误信息)
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 1. 获取根目录ID作为起点
    root_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root"
    root_response = requests.get(root_url, headers=headers)
    if root_response.status_code != 200:
        return False, f"无法获取驱动器根目录信息: {root_response.text}"

    current_parent_id = root_response.json().get("id")

    # 2. 清理路径并分割组件
    # 移除开头的斜杠，并按斜杠分割。注意：这里假设路径分隔符是 '/'
    cleaned_path = folder_path.strip('/')
    path_segments = cleaned_path.split('/')

    logger.info(f"路径分割组件: {path_segments}")

    # 3. 逐级检查和创建
    for segment in path_segments:
        # 确保路径段非空
        if not segment:
            continue

        # Graph API 要求路径段必须 URL 编码，以防中文或空格
        encoded_segment = urllib.parse.quote(segment)

        # 3.1 检查当前段是否存在于当前父目录下
        check_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{current_parent_id}/children?$filter=name eq '{encoded_segment}'"

        # 注意: Graph API 不支持 name eq '中文' 这种过滤，所以最稳妥的方式是尝试 GET by path
        # 但既然我们正在递归，我们可以简化为：尝试 GET by path，如果 404，则创建

        # 优化：直接尝试通过路径查找当前段（相对于根目录）
        # 这种方式是最好的，但如果路径很深，可能会很慢

        # 重新采用最稳妥的递归创建：
        # 尝试 GET 当前路径 (相对 root)
        current_full_path = "/".join(path_segments[:path_segments.index(segment) + 1])
        encoded_full_path = urllib.parse.quote(current_full_path, safe='')

        check_full_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_full_path}"
        check_response = requests.get(check_full_url, headers=headers)

        if check_response.status_code == 200:
            # 路径已存在，继续下一段
            current_parent_id = check_response.json().get("id")
            logger.info(f"路径段 '{segment}' 已存在，ID: {current_parent_id}")
            continue

        elif check_response.status_code == 404:
            # 路径不存在，需要创建当前段
            create_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{current_parent_id}/children"
            create_body = {
                "name": segment,
                "folder": {}  # 标记这是一个文件夹
            }

            create_response = requests.post(create_url, headers=headers, json=create_body)

            if create_response.status_code in [200, 201]:
                # 创建成功
                current_parent_id = create_response.json().get("id")
                logger.info(f"成功创建路径段 '{segment}', ID: {current_parent_id}")
            else:
                # 创建失败
                error_msg = f"创建文件夹路径段 '{segment}' 失败: {create_response.text}"
                logger.error(error_msg)
                return False, error_msg
        else:
            # 其他错误，如权限问题等
            error_msg = f"检查或创建路径段 '{segment}' 时发生未知错误: {check_response.text}"
            logger.error(error_msg)
            return False, error_msg

    # 4. 循环结束，返回最终的目标文件夹 ID
    return True, current_parent_id


@router.post("/move_file_sharepoint", response_model=UploadSharepointFileResponse)
async def move_file_sharepoint(
        request: MoveSharepointFileRequest = Body(...)
):
    """
    根据文件ID，将文件重命名并移动到SharePoint指定文件夹
    """
    file_id = request.move_info.file_id

    # 提前初始化，确保在 except 块中可以使用 (如果需要)
    drive_id = None

    try:
        logger.info(f"准备移动文件: FileID={file_id}")

        # --- 1. 获取访问令牌 (沿用上传接口逻辑) ---
        authority = f"https://login.microsoftonline.com/{request.tenant_info.tenant_id}"
        scope = ["https://graph.microsoft.com/.default"]

        app = msal.ConfidentialClientApplication(
            request.client_info.client_id,
            authority=authority,
            client_credential=request.client_info.client_secret
        )
        result = app.acquire_token_for_client(scopes=scope)
        access_token = result.get("access_token")

        if not access_token:
            error_msg = f"获取令牌失败: {result.get('error_description', '未知错误')}"
            logger.error(error_msg)
            # 注意: 如果 msal.ConfidentialClientApplication 失败，会抛出异常，因此这里可能不需要返回
            raise Exception(error_msg)

        logger.info("成功获取访问令牌")

        # 设置请求头
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # --- 2. 获取站点和驱动器ID (沿用上传接口逻辑) ---
        # 步骤 2.1: 获取站点信息
        graph_site_url = f"https://graph.microsoft.com/v1.0/sites/{request.tenant_info.tenant_name}.sharepoint.com:/sites/{request.move_info.site_name}"
        site_response = requests.get(graph_site_url, headers=headers)

        if site_response.status_code != 200:
            error_msg = f"获取站点信息失败: {site_response.text}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        site_id = site_response.json().get("id")

        # 步骤 2.2: 获取默认文档库/驱动器ID
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        drives_response = requests.get(drives_url, headers=headers)
        drives = drives_response.json().get("value", [])
        if not drives:
            raise HTTPException(status_code=500, detail="未找到任何文档库")

        # 使用默认文档库
        drive_id = drives[0].get("id")
        logger.info(f"使用文档库: {drives[0].get('name')} (ID: {drive_id})")

        # --- 3. 检查/创建目标文件夹路径 ---
        target_folder_path = request.move_info.target_folder_path
        file_id_to_move = request.move_info.file_id
        new_file_name = request.move_info.new_file_name

        # 假设 ensure_path_exists 函数定义在文件外部
        # 注意: ensure_path_exists 必须被定义为常规函数，而不是 async def
        success, result_id_or_error = ensure_path_exists(
            drive_id=drive_id,
            access_token=access_token,
            folder_path=target_folder_path
        )

        # 4. 如果路径创建/查找失败，则不执行 Move 操作
        if not success:
            logger.error(f"路径准备失败，终止移动操作: {result_id_or_error}")
            return UploadSharepointFileResponse(
                success=False,
                message=f"目标文件夹路径准备失败: {result_id_or_error}"
            )

        target_folder_id = result_id_or_error  # 此时 result_id_or_error 是最终的 target_folder_id
        logger.info(f"目标文件夹ID已确认/创建: {target_folder_id}")

        # --- 5. 构造移动和重命名请求体 ---
        move_body = {
            "parentReference": {
                "id": target_folder_id,
                "driveId": drive_id
            }
        }

        if new_file_name:
            move_body["name"] = new_file_name

        # --- 6. 执行 PATCH 请求 (Move 操作) ---
        # !!! 注意：这部分现在已正确缩进到 try 块内 !!!
        move_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id_to_move}"
        logger.info(f"执行移动操作 URL: {move_url}")

        move_response = requests.patch(move_url, headers=headers, json=move_body)

        if move_response.status_code == 200:
            file_info = move_response.json()
            message = "文件移动和重命名成功" if new_file_name else "文件移动成功"
            logger.info(f"✅ {message}. 新文件 URL: {file_info.get('webUrl')}")

            return UploadSharepointFileResponse(
                success=True,
                message=message,
                file_url=file_info.get("webUrl"),
                file_id=file_info.get("id")
            )
        else:
            error_msg = f"文件移动失败: 状态码 {move_response.status_code}. 响应: {move_response.text}"
            logger.error(f"❌ {error_msg}")
            # 同样抛出异常或返回失败响应
            return UploadSharepointFileResponse(success=False, message=error_msg)

    except HTTPException as e:
        # 捕获我们自己抛出的 HTTPException
        return UploadSharepointFileResponse(success=False, message=e.detail)

    except Exception as e:
        # 捕获所有其他未预期的异常 (如网络错误，msal错误等)
        error_msg = f"移动过程中发生意外错误: {str(e)}"
        logger.exception(error_msg)
        return UploadSharepointFileResponse(success=False, message=error_msg)