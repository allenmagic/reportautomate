import os
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_render_payment_form(tmp_path):
    # 假定你的 settings.TEMP_DIR 和 settings.TEMPLATE_DIR 可写且有有效模板
    # 你可以用 mock 或测试专用 settings 覆盖设置。这里以直接调用为例。

    # 构造示例请求体
    request_json = {
        "task_id": "test-task-001",
        "record_id": "rec-001",
        "data": {
            "order_id": "O20250728001",
            "oa_no": "OA2025072801",
            "prf_date": "2025-07-28",
            "oa_applicant": "张三",
            "payer": "Test Payer",
            "payee": "Test Payee",
            "description": "测试付款",
            "payment_reason": "业务需求",
            "department": "技术部",
            "project_name": "AI开发",
            "project_code": "AI2025X",
            "currency": "CNY",
            "amount": 99999.99,
            "cheque_no": None,
            "bank_settled": None,
            "book_keep": "2025-07-28",
            "attachments": [],
            "remarks": "",
            "oa_url": "https://oa.example.com/form/OA2025072801"
        }
    }

    response = client.post("/render_payment_form", json=request_json)
    assert response.status_code == 200, f"接口响应失败: {response.content}"
    resp_json = response.json()
    assert resp_json["task_id"] == request_json["task_id"]
    assert resp_json["record_id"] == request_json["record_id"]
    assert resp_json["pdf"].endswith(".pdf")

    # 检查 PDF 文件实际存在
    pdf_path = resp_json["pdf"]
    assert os.path.exists(pdf_path), f"PDF未生成于：{pdf_path}"

    # 清理测试生成的文件（可选）
    os.remove(pdf_path)
    tex_path = pdf_path.rsplit("_payment_form.pdf", 1)[0] + ".tex"
    if os.path.exists(tex_path):
        os.remove(tex_path)
