import os
import pandas as pd
import requests
from typing import List, Optional, Any, Union
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.utils.logger import logger

# ==============================================================================
# FastAPI 接口定义 (支持本地路径和URL)
# ==============================================================================

router = APIRouter()


# 定义请求模型
class DailyBalanceProcessRequest(BaseModel):
    file_path: str = Field(..., description="文件的本地路径或可直接下载的URL")


# 定义返回的数据模型 (修改余额字段类型为 float)
class CitiDailyBalanceData(BaseModel):
    Customer_Name: Optional[str] = Field(None, description="客户名称")
    Account_Number: str = Field(..., description="账户号码")
    Account_Name: Optional[str] = Field(None, description="账户名称")
    Currency: Optional[str] = Field(None, description="账户货币")
    Statement_Date: Optional[str] = Field(None, description="报表日期")
    Closing_Ledger_Balance: Optional[float] = Field(None, description="期末总账余额（数值）")


# 定义统一的响应包装模型
class ProcessResponse(BaseModel):
    status: str = Field("success", description="处理状态，success、warning或error")
    message: str = Field("数据处理成功", description="处理结果消息")
    data: Optional[Union[List[CitiDailyBalanceData], Any]] = Field(None, description="处理结果数据")
    count: int = Field(0, description="数据记录数量")
    error_code: Optional[str] = Field(None, description="错误代码")
    error_details: Optional[Any] = Field(None, description="错误详情")


# ==============================================================================
# 工具函数：解析余额数值
# ==============================================================================
def parse_balance_value(value_str: str) -> Optional[float]:
    """
    解析余额字符串为浮点数，支持以下格式：
    - 标准格式: "100.98", "-100.98"
    - 后置负号: "100.98-" → -100.98
    - 带千分位: "1,234.56" → 1234.56

    Args:
        value_str: 原始余额字符串

    Returns:
        解析后的浮点数，解析失败返回 None
    """
    if not value_str or not isinstance(value_str, str):
        return None

    # 去除首尾空格
    value_str = value_str.strip()

    # 检查是否为空
    if not value_str:
        return None

    try:
        # 移除千分位逗号
        value_str = value_str.replace(',', '')

        # 处理后置负号（如 "100.98-"）
        is_negative = False
        if value_str.endswith('-'):
            is_negative = True
            value_str = value_str[:-1].strip()

        # 转换为浮点数
        result = float(value_str)

        # 应用负号
        if is_negative:
            result = -result

        return result

    except (ValueError, AttributeError) as e:
        logger.warning(f"无法解析余额值 '{value_str}': {e}")
        return None


@router.post("/process_citi_daily_balance", response_model=ProcessResponse, tags=["Citibank Reports"])
async def process_citi_daily_balance(request: DailyBalanceProcessRequest):
    """
    处理花旗银行每日余额报告 (Balance Summary Report) 的API端点。
    支持本地文件路径和远程文件URL。
    """

    content: str = ""
    encoding = 'utf-16-be'
    source = request.file_path

    # ======================================================================
    # 1. 从文件源（本地文件或者URL地址）读取文件内容
    # ======================================================================
    try:
        # 获取文件内容 (根据输入类型选择方式)
        if source.startswith(('http://', 'https://')):
            # --- 处理URL ---
            logger.info(f"检测到输入为URL，正在从 {source} 获取内容...")
            try:
                response = requests.get(source, timeout=60)
                response.raise_for_status()

                # 获取原始字节并用指定编码手动解码
                content = response.content.decode(encoding)
                logger.info(f"已成功从URL下载并以 '{encoding}' 解码内容。")

            except requests.exceptions.RequestException as e:
                logger.error(f"从URL获取文件失败: {e}", exc_info=True)
                return ProcessResponse(
                    status="error",
                    message=f"无法从指定的URL获取文件: {source}",
                    error_code="URL_FETCH_FAILED",
                    error_details=str(e)
                )
        else:
            # --- 处理本地文件路径 ---
            logger.info(f"检测到输入为本地路径: {source}")
            if not os.path.exists(source):
                logger.warning(f"文件不存在: {source}")
                return ProcessResponse(
                    status="error",
                    message=f"文件不存在: {source}",
                    error_code="FILE_NOT_FOUND"
                )

            logger.info(f"正在使用编码 '{encoding}' 读取文件: {source}")
            with open(source, mode='r', encoding=encoding) as infile:
                content = infile.read()
            logger.info("文件内容已成功读取并正确解码。")

        # ======================================================================
        # 2. 核心解析逻辑 (处理文件内容)
        # ======================================================================

        fields = content.split('","')
        if fields:
            fields[0] = fields[0].lstrip('"')
            fields[-1] = fields[-1].rstrip('"')

        extracted_records = []
        current_customer_name = None

        CUSTOMER_MARKER = "Customer Number / Name"
        ACCOUNT_MARKER = "Account Number / Name"
        CURRENCY_MARKER = "Account Currency / Type"
        BALANCE_DATE_MARKER = "="

        i = 0
        while i < len(fields):
            field = fields[i].strip()

            if field == CUSTOMER_MARKER:
                if i + 2 < len(fields):
                    current_customer_name = fields[i + 2].strip()
                i += 1
                continue

            if field == ACCOUNT_MARKER:
                try:
                    # 提取原始余额字符串
                    balance_index = fields.index(BALANCE_DATE_MARKER, i + 3) + 4
                    raw_balance = fields[balance_index].strip()

                    # 使用新函数解析余额
                    parsed_balance = parse_balance_value(raw_balance)

                    record = {
                        'Customer_Name': current_customer_name,
                        'Account_Number': fields[i + 1].strip(),
                        'Account_Name': fields[i + 2].strip(),
                        'Currency': fields[fields.index(CURRENCY_MARKER, i + 3) + 1].strip(),
                        'Statement_Date': fields[fields.index(BALANCE_DATE_MARKER, i + 3) + 1].strip(),
                        'Closing_Ledger_Balance': parsed_balance  # 使用解析后的数值
                    }
                    extracted_records.append(record)
                    i = balance_index
                except (ValueError, IndexError) as e:
                    logger.warning(f"提取记录时在索引 {i} 处出错: {e}. 跳过此潜在记录。")
                    i += 1
            else:
                i += 1

        df = pd.DataFrame(extracted_records)

        # ======================================================================
        # 3. 处理结果并返回响应
        # ======================================================================

        if df.empty:
            logger.warning(f"文件 '{source}' 处理完成，但未提取到任何有效数据。")
            return ProcessResponse(
                status="warning",
                message="处理完成但没有有效数据，请检查文件内容或格式是否符合预期",
                count=0
            )

        data_list = [CitiDailyBalanceData(**row) for row in df.to_dict(orient='records')]

        return ProcessResponse(
            message=f"处理 {len(data_list)} 条活期余额数据",
            data=data_list,
            count=len(data_list)
        )

    except Exception as e:
        logger.error(f"处理报告 '{source}' 时发生未知错误: {e}", exc_info=True)
        return ProcessResponse(
            status="error",
            message=f"处理数据时发生未知错误: {str(e)}",
            error_code="PROCESSING_ERROR",
            error_details=str(e)
        )
