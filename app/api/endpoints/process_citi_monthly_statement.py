import os
from typing import List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel, Field
from app.utils.logger import logger
import pandas as pd
from app.utils.import_monthly_file import process_citibank_report_csv,process_citibank_report_xls

# 定义API应用
router = APIRouter()


# 定义请求模型
class ProcessRequest(BaseModel):
    email_id: str = Field(..., description="邮件ID")
    file_path: str = Field(..., description="花旗银行月度交易文件路径")


# 定义数据模型 - 根据R脚本处理后的字段定义
class CitiMonthlyTransactionData(BaseModel):
    Bank_Name: Optional[str] = Field(None, description="银行名称")
    Customer_Number: Optional[str] = Field(None, description="客户编号")
    Customer_Name: Optional[str] = Field(None, description="客户名称")
    Branch_Number: Optional[str] = Field(None, description="分支机���编号")
    Branch_Name: Optional[str] = Field(None, description="分支机构名称")
    Account_Number: str = Field(..., description="账户号码")
    Account_Name: Optional[str] = Field(None, description="账户名称")
    Account_Currency: Optional[str] = Field(None, description="账户货币")
    Account_Type: Optional[str] = Field(None, description="账户类型")
    Entry_Date: Optional[str] = Field(None, description="交易日期")
    Product_Type: Optional[str] = Field(None, description="产品类型")
    Transaction_Description: Optional[str] = Field(None, description="交易描述")
    Value_Date: Optional[str] = Field(None, description="数据日期")
    Bank_Reference: Optional[str] = Field(None, description="银行参考")
    Customer_Reference: Optional[str] = Field(None, description="客户参考")
    Confirmation_Reference: Optional[str] = Field(None, description="确认参考")
    Beneficiary: Optional[str] = Field(None, description="受益人")
    Amount: float = Field(..., description="交易金额")
    Currency: Optional[str] = Field(None, description="交易货币")
    Credit_Count: Optional[int] = Field(None, description="贷记次数")
    Total_Credit_Amount: Optional[float] = Field(None, description="贷记总金额")
    Credit_Currency: Optional[str] = Field(None, description="贷记货币")
    Debit_Count: Optional[int] = Field(None, description="借记次数")
    Total_Debit_Amount: Optional[float] = Field(None, description="借记总金额")
    Cheque_Count: Optional[int] = Field(None, description="支票次数")
    Cheque_Amount: Optional[float] = Field(None, description="支票金额")
    Net_Amount: Optional[float] = Field(None, description="净金额")
    Net_Currency: Optional[str] = Field(None, description="净金额货币")


# 定义响应包装模型
class ProcessResponse(BaseModel):
    status: str = Field("success", description="处理状态，success或error")
    message: str = Field("数据处理成功", description="处理结果消息")
    data: Optional[Union[List[CitiMonthlyTransactionData], Any]] = Field(None, description="处理结果数据")
    count: int = Field(0, description="数据记录数量")
    error_code: Optional[str] = Field(None, description="错误代码")
    error_details: Optional[Any] = Field(None, description="错误详情")


@router.post("/process_citi_monthly_statement", response_model=ProcessResponse)
async def process_citi_monthly_statement(request: ProcessRequest):
    """处理花旗银行月度交易报表的API端点"""
    # 验证文件路径
    if not os.path.exists(request.file_path):
        return ProcessResponse(
            status="error",
            message=f"文件不存在: {request.file_path}",
            error_code="FILE_NOT_FOUND"
        )

    try:
        # 根据文件扩展名选择处理函数
        file_ext = os.path.splitext(request.file_path)[1].lower()
        if file_ext in ['.csv', '.CSV']:
            df = process_citibank_report_csv(request.file_path)
        elif file_ext in ['.xls', '.xlsx', '.XLS', '.XLSX']:
            df = process_citibank_report_xls(request.file_path)
        else:
            return ProcessResponse(
                status="error",
                message=f"不支持的文件格式: {file_ext}",
                error_code="UNSUPPORTED_FILE_FORMAT"
            )

        # 直接从处理后的DataFrame创建数据对象列表
        data_list = []
        errors = []

        for _, row in df.iterrows():
            try:
                # 处理数据类型和缺失值
                row_dict = {}
                for key, value in row.to_dict().items():
                    # 空值处理为None（除了Account_Number和Amount）
                    if pd.isna(value):
                        row_dict[key] = None
                    else:
                        row_dict[key] = value

                # 创建响应数据对象
                item = CitiMonthlyTransactionData(**row_dict)
                data_list.append(item)
            except Exception as e:
                errors.append(f"行处理错误: {str(e)}, 数据: {row_dict}")
                logger.warning(f"跳过无效数据行: {str(e)}")
                continue

        if not data_list:
            logger.warning(f"处理完成但没有有效数据，可能的错误: {errors[:5]}")
            return ProcessResponse(
                status="warning",
                message="处理完成但没有有效数据，请检查数据格式",
                error_details=errors[:5],
                count=0
            )

        return ProcessResponse(
            message=f"成功处理 {len(data_list)} 条花旗银行月度交易数据",
            data=data_list,
            count=len(data_list)
        )

    except Exception as e:
        logger.error(f"处理花旗银行月度交易数据时出错: {str(e)}")
        return ProcessResponse(
            status="error",
            message=f"处理数据出错: {str(e)}",
            error_code="PROCESSING_ERROR"
        )