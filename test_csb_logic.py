import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from app.api.endpoints.process_csb_daily_balance import (
    CSBProcessRequest,
    SecurityTransferRecord,
    is_valid_date,
    format_date,
)

print("Testing CSB processing functions...")

# 测试日期验证函数
test_dates = ["20260115", "2026-01-15", "12345", "", None]
for test_date in test_dates:
    result = is_valid_date(test_date)
    print(f"is_valid_date('{test_date}') = {result}")

# 测试日期格式化函数
test_formats = ["20260115", "20251201"]
for test_date in test_formats:
    result = format_date(test_date)
    print(f"format_date('{test_date}') = '{result}'")

# 测试完整处理逻辑
print("\nTesting full processing logic...")

file_path = "/home/allenmagic/Projects/cash-report/temp/csb_file_template.xlsx"

# 读取数据
df = pd.read_excel(file_path)
header_row = 8
statement_data = df.iloc[header_row + 1 :].copy()

# 重命名列
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

# 过滤数据
statement_data = statement_data[statement_data["Transaction Date"].notna()]
statement_data["Transaction Date"] = (
    statement_data["Transaction Date"].astype(str).str.strip()
)
statement_data = statement_data[statement_data["Transaction Date"].apply(is_valid_date)]

numeric_columns = ["Quantity", "Price", "Amount"]
for col in numeric_columns:
    statement_data[col] = pd.to_numeric(statement_data[col], errors="coerce").fillna(0)

securities_data = statement_data[
    statement_data["Summary"].str.contains("证券", na=False)
].copy()
securities_data = securities_data[securities_data["Security Code"].notna()]
securities_data = securities_data[
    securities_data["Security Code"].astype(str).str.strip() != ""
]

print(f"Total securities records: {len(securities_data)}")

# 分组计算
grouped = (
    securities_data.groupby(
        ["Transaction Date", "Summary", "Security Code", "Security Name"]
    )
    .agg({"Amount": "sum", "Quantity": "sum"})
    .reset_index()
)


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

grouped = grouped.merge(
    weighted_prices,
    on=["Transaction Date", "Summary", "Security Code", "Security Name"],
)

# 创建记录对象
result_records = []
for _, row in grouped.iterrows():
    transaction_date = format_date(str(row["Transaction Date"]))
    record = SecurityTransferRecord(
        transaction_date=transaction_date,
        settlement_date=transaction_date,
        currency="CNY",
        amount=float(row["Amount"]),
        nature=str(row["Summary"]),
        security_code=str(row["Security Code"]),
        security_name=str(row["Security Name"]),
        quantity=int(row["Quantity"]),
        market_price=float(row["Price"]),
        description="",
    )
    result_records.append(record)

# 测试模型序列化
print(f"\nCreated {len(result_records)} SecurityTransferRecord objects")
print("\nFirst record (as dict):")
print(result_records[0].model_dump(by_alias=True))

print("\nAll records:")
for record in result_records:
    print(record.model_dump(by_alias=True))

print("\n✅ All tests passed!")
