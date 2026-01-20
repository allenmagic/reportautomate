from fastapi import HTTPException, Header, Depends
from starlette.status import HTTP_403_FORBIDDEN
from typing import Optional
from app.core.config import settings
from app.utils.logger import logger


async def verify_api_auth(
        x_app_id: Optional[str] = Header(None),
        x_app_secret: Optional[str] = Header(None)
):
    """验证API凭证"""
    logger.debug(f"收到API认证请求: App ID: {x_app_id}")
    logger.debug(f"可用的App ID列表: {list(settings.API_KEYS.keys())}")

    if not x_app_id or not x_app_secret:
        logger.warning("请求缺少API凭证")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="缺少API凭证，请提供X-App-ID和X-App-Secret请求头"
        )

    # 验证凭证
    if x_app_id in settings.API_KEYS and settings.API_KEYS[x_app_id] == x_app_secret:
        logger.debug(f"API凭证验证成功: {x_app_id}")
        return True

    # 记录更详细的错误信息
    if x_app_id not in settings.API_KEYS:
        logger.warning(f"未知的App ID: {x_app_id}")
    else:
        logger.warning(f"App ID存在但Secret不匹配: {x_app_id}")

    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN,
        detail="无效的API凭证"
    )
