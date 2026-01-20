import os
import re
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_process_csb_daily_balance():
    """
    测试CSB（券商对账单）文件处理接口
    """
    request_json = {
        "file_path": "/home/allenmagic/Projects/cash-report/temp/csb_file_template.xlsx"
    }

    response = client.post("/api/process_csb_daily_balance", json=request_json)

    assert response.status_code == 200, f"接口响应失败: {response.content}"

    resp_json = response.json()
    assert resp_json["status"] == "success"
    assert resp_json["count"] > 0
    assert "data" in resp_json
    assert "SecurityTransferRecords" in resp_json["data"]

    # 验证返回的数据结构
    records = resp_json["data"]["SecurityTransferRecords"]
    assert len(records) > 0

    first_record = records[0]
    required_fields = [
        "Transaction Date",
        "Settlement Date",
        "Currency",
        "Amount",
        "Nature",
        "Security Code",
        "Security Name",
        "Quantity",
        "Market Price",
        "Descrption",
    ]

    for field in required_fields:
        assert field in first_record, f"缺少字段: {field}"

    # 验证数据格式
    assert first_record["Currency"] == "CNY"
    assert isinstance(first_record["Amount"], (int, float))
    assert isinstance(first_record["Quantity"], int)
    assert isinstance(first_record["Market Price"], (int, float))
    assert first_record["Descrption"] == ""

    # 验证日期格式 YYYY-MM-DD
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    assert date_pattern.match(first_record["Transaction Date"])
    assert date_pattern.match(first_record["Settlement Date"])

    print(f"测试通过！共处理 {resp_json['count']} 条记录")
    print(f"第一条记录: {first_record}")
