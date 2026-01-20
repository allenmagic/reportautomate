# 导入必要的库
from app.utils.logger import logger
from app.core.config import settings
from pathlib import Path
from typing import List, Dict, TypeVar, Generic, Optional
import pandas as pd
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

# ====================================================================
# 1. 基础参数设置
# ====================================================================

# --- 新增：为不同 Sheet 定义固定的列顺序 ---

# Sheet 1: accounting 的列头 (原 TD_ACCOUTING_FIXED_COLUMN_ORDER)
ACCOUNTING_COLUMN_ORDER = [
    "Ledger Code", "Database", "Journal Type", "Journal Type Name", "Reference",
    "Transaction Date", "Period", "A0 Code", "Account", "Account Name", "Description",
    "Base Amount", "Amount (USD)", "Currency Conversion Code", "Other Amount", "T0 Code",
    "T0 Name", "T1 Code", "T1 Name", "T2 Code", "T2 Name", "T3 Code", "T3 Name", "T4 Code",
    "T4 Name", "T5 Code", "T5 Name", "T6 Code", "T6 Name", "T7 Code", "T7 Name", "Transaction Detail"
]

# Sheet 2 & 3: summary 和 flow 的列头 (结构相同)
SUMMARY_FLOW_COLUMN_ORDER = [
    "LogId", "Company Name", "AccountNumber", "BankShortName", "AccountCategoty", "Status",
    "Create Date", "Start Date", "End Date", "Tenor (days)", "Remaining Tenor（days）",
    "Currency", "Exchange Rate", "Principal (Original)", "Principal (USD)", "Interest Rate（%）",
    "Interest (Original)", "Interest (USD)", "P+I (Original)", "P+I (USD)", "Create By", "Remark"
]

# 时区的设定
TARGET_TIMEZONE = "Asia/Shanghai"

# --- 新增：为不同 Sheet 定义需要转换为数值和日期的列 ---

# accounting Sheet 的数值列和日期列
ACCOUNTING_NUMERIC_COLUMNS = ["Base Amount", "Amount (USD)", "Other Amount"]
ACCOUNTING_DATE_COLUMNS = ["Transaction Date"]

# summary & flow Sheet 的数值列和日期列
SUMMARY_FLOW_NUMERIC_COLUMNS = [
    "Principal (Original)", "Interest (Original)", "Interest (USD)", "Exchange Rate",
    "P+I (Original)", "P+I (USD)", "Principal (USD)", "Tenor (days)", "Remaining Tenor（days）"
]
SUMMARY_FLOW_DATE_COLUMNS = ["Create Date", "Start Date", "End Date"]

# ====================================================================
# 2. Pydantic 模型定义
# ====================================================================
# 定义一个类型变量，用于泛型模型
T = TypeVar('T')


# 定义标准泛型的响应模型
class StandardResponse(GenericModel, Generic[T]):
    code: int = Field(0, description="业务状态码, 0 表示成功")
    message: str = Field("success", description="响应消息")
    data: Optional[T] = Field(None, description="具体的业务数据负载")


# GeneratedFileInfo 具体的业务数据模型
class GeneratedFileInfo(BaseModel):
    task_id: str = Field(..., description="与请求中一致的任务ID")
    file_path: Path = Field(..., description="在服务器上创建的文件的绝对路径")


# --- 新增：定义请求体中 data 字段的嵌套结构 ---
class DataPayload(BaseModel):
    accouting: List[Dict] = Field(..., description="会计分录数据")
    summary: List[Dict] = Field(..., description="摘要数据")
    flow: List[Dict] = Field(..., description="流水数据")


# --- 修改：更新 GenerateFileRequest 请求模型以匹配新的数据结构 ---
class GenerateFileRequest(BaseModel):
    task_id: str = Field(..., description="唯一的任务ID", min_length=1)
    ReportDate: str = Field(..., description="年份月份，例如 '202509'", pattern=r"^\d{6}$")
    data: DataPayload = Field(..., description="包含 accouting, summary, flow 的业务数据")


router = APIRouter()


# --- 新增：创建一个辅助函数来处理 DataFrame，以减少代码重复 ---
def process_dataframe(
        data_list: List[Dict],
        column_order: List[str],
        date_columns: List[str],
        numeric_columns: List[str],
        task_id: str
) -> pd.DataFrame:
    """
    将字典列表转换为经过标准化处理的 Pandas DataFrame。

    Args:
        data_list (List[Dict]): 原始数据列表。
        column_order (List[str]): 期望的列顺序。
        date_columns (List[str]): 需要处理为日期的列名列表。
        numeric_columns (List[str]): 需要处理为数值的列名列表。
        task_id (str): 任务ID，用于日志记录。

    Returns:
        pd.DataFrame: 处理完成的 DataFrame。
    """
    if not data_list:
        logger.warning(f"任务 {task_id} 的输入数据列表为空，将创建仅包含表头的空 DataFrame。")
        return pd.DataFrame(columns=column_order)

    df = pd.DataFrame(data_list)

    # 处理日期列：从毫秒时间戳转换为指定时区的日期字符串
    for col in date_columns:
        if col in df.columns:
            # 过滤掉非法的、无法转换的值
            valid_dates = pd.to_datetime(df[col], unit='ms', errors='coerce')
            # 本地化到 UTC，然后转换为目标时区
            dt_series_utc = valid_dates.dt.tz_localize('UTC')
            dt_series_local = dt_series_utc.dt.tz_convert(TARGET_TIMEZONE)
            # 格式化为 'YYYY-MM-DD'，NaT 值会变成 None，最终在Excel中为空白单元格
            df[col] = dt_series_local.dt.strftime('%Y-%m-%d')
            logger.info(f"已成功将 '{col}' 列从 UTC 时间戳转换为 {TARGET_TIMEZONE} 时间字符串。")

    # 强制转换数值类型
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    logger.info(f"已强制转换数值列: {numeric_columns}")

    # 保证列的顺序和完整性，不存在的列会以空列形式添加
    df = df.reindex(columns=column_order)

    return df


@router.post(
    "/generate_account_file",
    response_model=StandardResponse[GeneratedFileInfo],
    status_code=status.HTTP_201_CREATED,
    summary="生成并写入包含多个 Sheet 的 XLSX 文件",
    tags=["Files"],
)
async def generate_account_file(request: GenerateFileRequest) -> StandardResponse:
    """
    接收任务数据，执行以下操作：
    1. 在 'temp' 目录下创建一个以 `task_id` 命名的子目录。
    2. 将请求中 `data` 负载的 `accouting`, `summary`, `flow` 数据分别处理。
    3. 将处理后的三份数据写入一个 XLSX 文件的三个不同工作表（Sheet）中。
    4. 返回创建的文件的绝对路径。
    """
    task_id = request.task_id
    logger.info(f"收到文件生成请求，task_id: {task_id}")

    # 步骤 1: 创建任务子目录
    try:
        task_dir = settings.TEMP_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"任务目录已准备就绪: {task_dir}")
    except OSError as e:
        logger.error(f"创建目录 {task_dir} 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"无法创建任务目录: {e}",
        )

    # 步骤 2: 处理数据并写入 XLSX 文件
    try:
        # --- 使用辅助函数分别处理三份数据 ---
        df_accounting = process_dataframe(
            data_list=request.data.accouting,
            column_order=ACCOUNTING_COLUMN_ORDER,
            date_columns=ACCOUNTING_DATE_COLUMNS,
            numeric_columns=ACCOUNTING_NUMERIC_COLUMNS,
            task_id=task_id
        )

        df_summary = process_dataframe(
            data_list=request.data.summary,
            column_order=SUMMARY_FLOW_COLUMN_ORDER,
            date_columns=SUMMARY_FLOW_DATE_COLUMNS,
            numeric_columns=SUMMARY_FLOW_NUMERIC_COLUMNS,
            task_id=task_id
        )

        df_flow = process_dataframe(
            data_list=request.data.flow,
            column_order=SUMMARY_FLOW_COLUMN_ORDER,
            date_columns=SUMMARY_FLOW_DATE_COLUMNS,
            numeric_columns=SUMMARY_FLOW_NUMERIC_COLUMNS,
            task_id=task_id
        )

        # 定义输出文件名和完整路径
        file_name = f"AccountingReport_{request.ReportDate}.xlsx"
        output_file_path = task_dir / file_name

        # --- 使用 pd.ExcelWriter 将多个 DataFrame 写入不同 Sheet ---
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            df_accounting.to_excel(writer, sheet_name='accounting', index=False)
            logger.info(f"已将 'accounting' 数据写入 Sheet。")

            df_summary.to_excel(writer, sheet_name='summary', index=False)
            logger.info(f"已将 'summary' 数据写入 Sheet。")

            df_flow.to_excel(writer, sheet_name='flow', index=False)
            logger.info(f"已将 'flow' 数据写入 Sheet。")

        logger.info(f"文件已成功创建: {output_file_path}")

    except Exception as e:
        logger.error(f"处理数据或写入 Excel 文件时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件生成失败: {e}",
        )

    # 步骤 3: 返回成功响应
    file_info = GeneratedFileInfo(task_id=task_id, file_path=output_file_path.resolve())
    return StandardResponse(data=file_info)

