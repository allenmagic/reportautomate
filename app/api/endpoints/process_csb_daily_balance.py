import re
from pathlib import Path
from typing import List, Optional, Union
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import pandas as pd
from app.utils.logger import logger

# ==============================================================================
# FastAPI 接口定义
# ==============================================================================

router = APIRouter()


# 定义请求模型
class CSBProcessRequest(BaseModel):
    file_path: str = Field(..., description="CSB xlsx文件的本地路径")


# 定义证券交易记录数据模型
class SecurityTransferRecord(BaseModel):
    transaction_date: str = Field(..., alias="Transaction Date", description="交易日期")
    settlement_date: str = Field(..., alias="Settlement Date", description="结算日期")
    currency: str = Field(..., alias="Currency", description="货币代码")
    amount: float = Field(..., alias="Amount", description="交易金额")
    nature: str = Field(..., alias="Nature", description="交易性质/摘要")
    security_code: str = Field(..., alias="Security Code", description="证券代码")
    security_name: str = Field(..., alias="Security Name", description="证券名称")
    quantity: int = Field(..., alias="Quantity", description="成交数量")
    market_price: float = Field(..., alias="Market Price", description="市场价格")
    description: str = Field("", alias="Descrption", description="描述")

    class Config:
        populate_by_name = True


# 定义统一的响应包装模型
class ProcessResponse(BaseModel):
    status: str = Field("success", description="处理状态，success、warning或error")
    message: str = Field("数据处理成功", description="处理结果消息")
    data: Optional[Union[List[SecurityTransferRecord], dict]] = Field(
        None, description="处理结果数据"
    )
    count: int = Field(0, description="数据记录数量")
    error_code: Optional[str] = Field(None, description="错误代码")
    error_details: Optional[str] = Field(None, description="错误详情")


# ==============================================================================
# 工具函数：日期格式验证和转换
# ==============================================================================
def is_valid_date(date_str: str) -> bool:
    """
    检查字符串是否为有效的8位日期格式（YYYYMMDD）。

    Args:
        date_str: 日期字符串

    Returns:
        是否为有效的8位日期格式
    """
    if not isinstance(date_str, str):
        return False
    return bool(re.match(r"^\d{8}$", date_str))


def format_date(date_str: str) -> str:
    """
    将YYYYMMDD格式转换为YYYY-MM-DD格式。

    Args:
        date_str: 8位日期字符串

    Returns:
        格式化后的日期字符串
    """
    if isinstance(date_str, str) and len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str


# ==============================================================================
# 主处理函数
# ==============================================================================
@router.post(
    "/process_csb_daily_balance", response_model=ProcessResponse, tags=["CSB Reports"]
)
async def process_csb_daily_balance(request: CSBProcessRequest):
    """
    处理CSB（券商对账单）文件的API端点。

    1. 从入参提供的文件路径读取xlsx文件
    2. 读取xlsx文件中的对账单部分的数据
    3. 按照发生日期、摘要、证券名称进行分组
    4. 计算发生金额和成交数量的和值，以及加权平均价格
    5. 返回分组后的证券交易记录列表
    """
    try:
        file_path = Path(request.file_path)

        # ======================================================================
        # 1. 验证文件存在
        # ======================================================================
        logger.info(f"开始处理CSB文件: {file_path}")

        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return ProcessResponse(
                status="error",
                message=f"文件不存在: {file_path}",
                error_code="FILE_NOT_FOUND",
            )

        # ======================================================================
        # 2. 读取xlsx文件
        # ======================================================================
        df = None
        read_errors = []

        # 尝试多种读取方式
        read_methods = [
            lambda: pd.read_excel(file_path, engine="openpyxl"),
            lambda: pd.read_excel(str(file_path), engine="openpyxl"),
            lambda: pd.read_excel(file_path),
        ]

        for i, read_method in enumerate(read_methods, 1):
            try:
                df = read_method()
                logger.info(f"使用方法{i}成功读取文件，共 {len(df)} 行")
                break
            except Exception as e:
                read_errors.append(f"方法{i}: {str(e)}")
                logger.warning(f"读取方法{i}失败: {e}")

        if df is None:
            logger.error(f"所有读取方法均失败: {'; '.join(read_errors)}")
            return ProcessResponse(
                status="error",
                message=f"读取Excel文件失败，已尝试{len(read_methods)}种方法",
                error_code="READ_FILE_FAILED",
                error_details=" | ".join(read_errors),
            )

        # ======================================================================
        # 3. 定位对账单数据区域
        # ======================================================================
        # 通过关键词"对账单"定位表头位置
        header_row = None

        for idx, row in df.iterrows():
            # 检查第一列是否包含"对账单"
            first_col_value = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            if "对账单" in first_col_value:
                # 找到"对账单"行，表头应该在其后几行
                # 查找包含"发生日期"的行作为表头
                for header_idx in range(idx + 1, min(idx + 10, len(df))):
                    header_row_content = df.iloc[header_idx].astype(str)
                    if header_row_content.str.contains("发生日期", na=False).any():
                        header_row = header_idx
                        logger.info(
                            f"找到对账单表头在第 {header_row} 行（索引{header_idx}）"
                        )
                        break
                break

        if header_row is None:
            logger.error("无法找到包含'对账单'和'发生日期'的表头行")
            return ProcessResponse(
                status="error",
                message="文件格式错误：无法找到对账单表头",
                error_code="INVALID_FILE_FORMAT",
            )

        if header_row >= len(df) - 1:
            logger.error(f"文件行数不足，表头行 {header_row} 超出文件范围")
            return ProcessResponse(
                status="error",
                message="文件格式错误：表头行超出文件范围",
                error_code="INVALID_FILE_FORMAT",
            )

        # ======================================================================
        # 提取 Currency 信息
        # ======================================================================
        # 从第一行查找"对账单"并提取货币
        currency = "CNY"
        first_row_values = [str(val) if pd.notna(val) else "" for val in df.iloc[0]]

        for value in first_row_values:
            if "对账单" in value:
                value_str = str(value)
                if "人民币" in value_str or "CNY" in value_str:
                    currency = "CNY"
                elif "港币" in value_str or "HKD" in value_str:
                    currency = "HKD"
                elif "美元" in value_str or "USD" in value_str:
                    currency = "USD"
                logger.info(f"从表头提取货币: {currency}")
                break

        # ======================================================================
        # 3.6 提取对账单数据
        # ======================================================================
        statement_data = df.iloc[header_row + 1 :].copy()

        # 重命名列（根据对账单表头）
        statement_data.columns = [
            "Transaction Date",
            "Summary",
            "Account",
            "Security Code",
            "Security Name",
            "Quantity",
            "Share Balance",
            "Price",
            "Amount",
            "Fee",
            "Stamp Tax",
            "Transfer Fee",
            "Commission Fee",
            "Other Fee",
            "Fund Balance",
        ]

        logger.debug(f"对账单数据列名: {statement_data.columns.tolist()}")

        # ======================================================================
        # 4. 清理和过滤数据
        # ======================================================================
        # 移除发生日期为空的行
        statement_data = statement_data[statement_data["Transaction Date"].notna()]
        logger.debug(f"移除空日期后剩余 {len(statement_data)} 行")

        # 转换日期为字符串并清理
        statement_data["Transaction Date"] = (
            statement_data["Transaction Date"].astype(str).str.strip()
        )

        # 只保留有效日期格式（YYYYMMDD）的行
        statement_data = statement_data[
            statement_data["Transaction Date"].apply(is_valid_date)
        ]
        logger.debug(f"过滤有效日期后剩余 {len(statement_data)} 行")

        # 转换数值列
        numeric_columns = ["Quantity", "Price", "Amount"]
        for col in numeric_columns:
            statement_data[col] = pd.to_numeric(
                statement_data[col], errors="coerce"
            ).fillna(0)

        # 过滤出证券交易数据（摘要中包含"证券"字样的）
        securities_data = statement_data[
            statement_data["Summary"].str.contains("证券", na=False)
        ].copy()
        logger.debug(f"证券交易记录数量: {len(securities_data)}")

        # 确保证券代码不为空
        securities_data = securities_data[securities_data["Security Code"].notna()]
        securities_data = securities_data[
            securities_data["Security Code"].astype(str).str.strip() != ""
        ]
        logger.debug(f"过滤有效证券代码后剩余 {len(securities_data)} 行")

        if securities_data.empty:
            logger.warning("未找到有效的证券交易记录")
            return ProcessResponse(
                status="warning", message="处理完成但未找到有效的证券交易记录", count=0
            )

        # ======================================================================
        # 5. 按照发生日期、摘要、证券名称分组
        # ======================================================================
        logger.info("开始分组计算...")

        # 按照发生日期、摘要、证券代码、证券名称分组
        grouped = (
            securities_data.groupby(
                ["Transaction Date", "Summary", "Security Code", "Security Name"]
            )
            .agg({"Amount": "sum", "Quantity": "sum"})
            .reset_index()
        )

        # 计算加权平均价格
        def calculate_weighted_avg_price(group):
            total_amount = (group["Price"] * group["Quantity"]).sum()
            total_quantity = group["Quantity"].sum()
            return total_amount / total_quantity if total_quantity != 0 else 0

        weighted_prices = (
            securities_data.groupby(
                ["Transaction Date", "Summary", "Security Code", "Security Name"],
                group_keys=False,
            )
            .apply(calculate_weighted_avg_price, include_groups=False)
            .reset_index(name="Price")
        )

        # 合并加权平均价格到分组结果
        grouped = grouped.merge(
            weighted_prices,
            on=["Transaction Date", "Summary", "Security Code", "Security Name"],
        )

        logger.info(f"分组完成，共 {len(grouped)} 条记录")

        # ======================================================================
        # 6. 格式化输出数据
        # ======================================================================
        result_records = []

        for _, row in grouped.iterrows():
            transaction_date = format_date(str(row["Transaction Date"]))

            record_dict = {
                "Transaction Date": transaction_date,
                "Settlement Date": transaction_date,
                "Currency": currency,
                "Amount": float(row["Amount"]),
                "Nature": str(row["Summary"]),
                "Security Code": str(row["Security Code"]),
                "Security Name": str(row["Security Name"]),
                "Quantity": int(row["Quantity"]),
                "Market Price": round(float(row["Price"]), 4),
                "Descrption": str(row["Summary"]),
            }

            record = SecurityTransferRecord.model_validate(record_dict)
            result_records.append(record)

        # ======================================================================
        # 7. 返回结果
        # ======================================================================
        logger.info(f"处理成功，共返回 {len(result_records)} 条证券交易记录")

        return ProcessResponse(
            message=f"成功处理 {len(result_records)} 条证券交易记录",
            data={
                "SecurityTransferRecords": [
                    r.model_dump(by_alias=True) for r in result_records
                ]
            },
            count=len(result_records),
        )

    except Exception as e:
        logger.error(f"处理CSB文件时发生未知错误: {e}", exc_info=True)
        return ProcessResponse(
            status="error",
            message=f"处理数据时发生未知错误: {str(e)}",
            error_code="PROCESSING_ERROR",
            error_details=str(e),
        )
