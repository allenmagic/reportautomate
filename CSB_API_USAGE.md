# CSB 处理接口使用说明

## 接口概述
该接口用于处理券商对账单（CSB）Excel文件，提取证券交易记录并按照日期、摘要、证券名称进行分组汇总。

## 接口地址
`POST /api/process_csb_daily_balance`

## 请求参数

```json
{
  "file_path": "/path/to/csb_file.xlsx"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | 是 | CSB xlsx文件的本地路径 |

## 响应格式

### 成功响应
```json
{
  "status": "success",
  "message": "成功处理 2 条证券交易记录",
  "data": {
    "SecurityTransferRecords": [
      {
        "Transaction Date": "2026-01-15",
        "Settlement Date": "2026-01-15",
        "Currency": "CNY",
        "Amount": 3705592.31,
        "Nature": "证券卖出",
        "Security Code": "600361",
        "Security Name": "创新新材",
        "Quantity": 822100,
        "Market Price": 4.51,
        "Descrption": ""
      },
      {
        "Transaction Date": "2026-01-15",
        "Settlement Date": "2026-01-15",
        "Currency": "CNY",
        "Amount": 9986462.05,
        "Nature": "证券卖出",
        "Security Code": "688114",
        "Security Name": "华大智造",
        "Quantity": 137961,
        "Market Price": 72.43,
        "Descrption": ""
      }
    ]
  },
  "count": 2,
  "error_code": null,
  "error_details": null
}
```

### 错误响应
```json
{
  "status": "error",
  "message": "文件不存在: /path/to/file.xlsx",
  "data": null,
  "count": 0,
  "error_code": "FILE_NOT_FOUND",
  "error_details": null
}
```

## 数据处理逻辑

### 1. 文件读取
- 从提供的文件路径读取 xlsx 文件
- 定位对账单表头（通常在第8行）

### 2. 数据提取
- 提取对账单数据区域
- 重命名列为：发生日期、摘要、股东账号、证券代码、证券名称、成交股数、股份余额、成交价格、发生金额、手续费、印花税、过户费、委托费、其他费、资金余额

### 3. 数据过滤
- 移除发生日期为空的行
- 只保留日期格式为 YYYYMMDD（8位数字）的记录
- 只保留摘要包含"证券"字样的记录
- 确保证券代码不为空

### 4. 分组计算
按照以下字段分组：
- Transaction Date (发生日期)
- Summary (摘要)
- Security Code (证券代码)
- Security Name (证券名称)

对每组计算：
- Amount: 发生金额之和
- Quantity: 成交股数之和
- Price: 加权平均价格 = (Price × Quantity).sum() / Quantity.sum()

### 5. 数据格式化
- 日期格式从 YYYYMMDD 转换为 YYYY-MM-DD
- 结算日期默认等于发生日期
- 货币代码固定为 CNY
- 数量取整
- 描述字段为空字符串

## 使用示例

### curl 命令
```bash
curl -X POST "http://localhost:8000/api/process_csb_daily_balance" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/home/user/csb_report.xlsx"
  }'
```

### Python 请求
```python
import requests

url = "http://localhost:8000/api/process_csb_daily_balance"
payload = {
    "file_path": "/home/user/csb_report.xlsx"
}

response = requests.post(url, json=payload, params={
    "anycross_doc": "your_api_key"  # API认证参数
})

result = response.json()
if result["status"] == "success":
    records = result["data"]["SecurityTransferRecords"]
    for record in records:
        print(f"{record['Security Name']}: {record['Amount']}")
```

### JavaScript/Node.js 请求
```javascript
const axios = require('axios');

async function processCSB(filePath) {
  const response = await axios.post(
    'http://localhost:8000/api/process_csb_daily_balance?anycross_doc=your_api_key',
    {
      file_path: filePath
    }
  );

  const result = response.data;
  if (result.status === 'success') {
    console.log(`处理了 ${result.count} 条记录`);
    result.data.SecurityTransferRecords.forEach(record => {
      console.log(`${record['Security Name']}: ${record.Amount}`);
    });
  }
}

processCSB('/home/user/csb_report.xlsx');
```

## 注意事项

1. **文件格式**：必须为 Excel (.xlsx) 格式，且包含对账单数据
2. **文件路径**：必须是服务器上的绝对路径
3. **API认证**：所有接口需要通过 `anycross_doc` 参数进行认证
4. **日期格式**：输入文件中的日期应为 YYYYMMDD 格式（如 20260115）
5. **数据完整性**：确保 Excel 文件中的对账单表头和数据完整

## 错误代码

| 错误代码 | 说明 |
|---------|------|
| FILE_NOT_FOUND | 文件不存在 |
| READ_FILE_FAILED | 读取Excel文件失败 |
| INVALID_FILE_FORMAT | 文件格式错误，无法找到对账单表头 |
| PROCESSING_ERROR | 处理数据时发生未知错误 |

## 示例输出

使用测试文件 `temp/csb_file_template.xlsx` 处理的输出示例：

```json
{
  "status": "success",
  "message": "成功处理 2 条证券交易记录",
  "data": {
    "SecurityTransferRecords": [
      {
        "Transaction Date": "2026-01-15",
        "Settlement Date": "2026-01-15",
        "Currency": "CNY",
        "Amount": 3705592.31,
        "Nature": "证券卖出",
        "Security Code": "600361",
        "Security Name": "创新新材",
        "Quantity": 822100,
        "Market Price": 4.510161780805255,
        "Descrption": ""
      },
      {
        "Transaction Date": "2026-01-15",
        "Settlement Date": "2026-01-15",
        "Currency": "CNY",
        "Amount": 9986462.05,
        "Nature": "证券卖出",
        "Security Code": "688114",
        "Security Name": "华大智造",
        "Quantity": 137961,
        "Market Price": 72.42927428771029,
        "Descrption": ""
      }
    ]
  },
  "count": 2
}
```
