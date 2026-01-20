import json
import os
from typing import List
from datetime import date, datetime
from fastapi import FastAPI, HTTPException,APIRouter
from pydantic import BaseModel, Field
from rpy2.robjects import r
from app.core.config import settings
from app.utils.logger import logger
import pandas as pd
from app.utils.cleaner import cleanup_feather_files

# 定义API应用
router = APIRouter()

# 固定配置值
CONN_PATH = os.path.join(settings.RSCRIPT_DIR, "r_sql", "conn","ems_conn.R")
QUERY_PATH = os.path.join(settings.RSCRIPT_DIR, "r_sql", "query","QueryAccount.sql")
BANK_NAME = "The Hongkong and Shanghai Banking Corporation Limited"

# 定义请求模型
class ProcessRequest(BaseModel):
    email_id: str = Field(..., description="邮件ID")
    file_path: str = Field(..., description="HSBC数据文件路径")


# 定义数据模型
class DailyCashData(BaseModel):
    account_number: str
    account_currency: str
    account_balance: float
    account_date: date
    bank_short_name: str
    bank_location: str


# 定义响应包装模型
class ProcessResponse(BaseModel):
    status: str = "success"
    message: str = "数据处理成功"
    data: List[DailyCashData]
    count: int


# 加载R脚本
try:
    r_script_path = "app/r_scripts/r_processor/hsbc_daily_cash_processor.R"
    logger.info(f"尝试加载R脚本: {r_script_path}")
    r['source'](r_script_path)
    logger.info("R脚本加载成功")
except Exception as e:
    error_msg = f"加载R脚本失败: {str(e)}"
    logger.error(error_msg)
    raise Exception(error_msg)


@router.post("/process_hsbc_daily_cash", response_model=ProcessResponse)
async def process_hsbc_daily_cash(request: ProcessRequest):
    """处理HSBC数据的API端点"""
    # 验证文件路径
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.file_path}")

    try:
        # 调用R函数处理数据并保存为feather文件
        r['process_hsbc_data_main'](request.file_path, CONN_PATH, QUERY_PATH, BANK_NAME)

        # 构建feather文件名前缀
        feather_pattern = "dataroom/hsbc_daily_cash_"

        # 查找最新的feather文件
        dataroom_files = [f for f in os.listdir("dataroom") if
                          f.startswith("hsbc_daily_cash_") and f.endswith(".feather")]
        if not dataroom_files:
            raise HTTPException(status_code=404, detail="未找到处理后的数据文件")

        # 获取最新的文件（按文件名排序，文件名包含时间戳）
        latest_file = sorted(dataroom_files)[-1]
        feather_path = os.path.join("dataroom", latest_file)

        # 使用pandas读取feather文件
        df = pd.read_feather(feather_path)

        # 删除7天前的数据
        cleanup_feather_files(days_to_keep=7)

        # 转换为API响应格式
        data_list = []
        for _, row in df.iterrows():
            item = {
                "account_number": row.get("account_number", ""),
                "account_currency": row.get("account_currency", ""),
                "account_balance": float(row.get("account_balance", 0.0)),
                "account_date": row.get("account_date").date() if isinstance(row.get("account_date"),
                                                                             datetime) else date.fromisoformat(
                    str(row.get("account_date"))),
                "bank_short_name": row.get("bank_short_name", ""),
                "bank_location": row.get("bank_location", "")
            }
            data_list.append(DailyCashData(**item))

        # 构建响应
        response = ProcessResponse(
            message=f"成功处理 {len(data_list)} 条HSBC账户活期余额数据",
            data=data_list,
            count=len(data_list)
        )

        # 删除处理完成后的feather文件
        try:
            if os.path.exists(feather_path):
                os.remove(feather_path)
                logger.info(f"已删除处理完成的feather文件: {feather_path}")
        except Exception as e:
            logger.warning(f"删除feather文件时出错: {str(e)}")

        return response

    except Exception as e:
        logger.error(f"处理HSBC数据时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理HSBC数据时出错: {str(e)}")
