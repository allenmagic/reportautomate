import pandas as pd
import re
import io
import csv
from loguru import logger


def process_citibank_report_csv(file_path: str) -> pd.DataFrame:
    """
        处理花旗银行月度交易报告文件

        参数:
            file_path: 花旗银行月度交易报告CSV文件的路径

        返回:
            处理后的交易数据DataFrame，包含以下字段:
            - Bank_Name: 银行名称
            - Customer_Number: 客户编号
            - Customer_Name: 客户名称
            - Branch_Number: 分行编号
            - Branch_Name: 分行名称
            - Acconut_Number: 账户编号
            - Account_Name: 账户名称
            - Account_Currency: 账户货币
            - Account_Type: 账户类型
            - Entry_Date: 交易日期
            - Product_Type: 产品类型
            - Transaction_Description: 交易描述
            - Value_Date: 价值日期
            - Bank_Reference: 银行参考号
            - Customer_Reference: 客户参考号
            - Confirmation_Reference: 确认参考号
            - Beneficiary: 受益人
            - Amount: 交易金额
            - Amount_Currency: 交易货币
            - Credit_Count: 贷记交易笔数
            - Total_Credit_Amount: 贷记总金额
            - Credit_Currency: 贷记货币
            - Debit_Count: 借记交易笔数
            - Total_Debit_Amount: 借记总金额
            - Cheque_Count: 支票交易笔数
            - Cheque_Amount: 支票总金额
            - Net_Amount: 净额
    """

    # 读取CSV文件
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        logger.error(f"文件 {file_path} 不存在")
        raise
    except PermissionError:
        logger.error(f"没有权限读取文件 {file_path}")
        raise
    except UnicodeDecodeError:
        logger.error(f"文件 {file_path} 编码错误，无法以UTF-8解码")
        raise
    except Exception as e:
        logger.error(f"读取文件 {file_path} 时发生未知错误: {str(e)}")
        raise


    # 以Bank Name字符为标记分割整个报告为多个银行账户交易信息，每个银行账户交易信息以Bank Name为标记起始
    # Cross-currency calculations are at indicative rates为标记结束，中间内容为银行账户交易信息
    # 每个银行账户交易信息包括：银行信息、交易信息、汇总信息，分别进行处理
    bank_blocks = re.split(r'Bank Name,', content)[1:]  # 跳过第一个空元素
    logger.info(f"共有 {len(bank_blocks)} 个银行账户交易信息")

    # 处理每个银行账户的交易信息
    all_records = []

    logger.info("开始处理每个银行账户的交易信息...")
    for i, block in enumerate(bank_blocks, 1):
        # 添加回Bank Name前缀，以便后续处理
        block = "Bank Name," + block

        logger.info(f"正在处理第 {i}/{len(bank_blocks)} 个银行账户交易信息")

        # 分割每个银行账户信息，排除Cross-currency calculations部分
        parts = re.split(r'Cross-currency calculations are at indicative rates', block)[0].strip()
        logger.info(f"银行账户交易信息内容:\n{parts}")

        # 进一步分割为三个部分: 银行账户信息、交易信息、汇总信息
        bank_part = ""
        transactions_part = ""
        summary_part = ""

        # 分割出Bank部分的信息（Bank Name到Entry Date之间）
        bank_match = re.search(r'(Bank Name.*?)Entry Date', parts, re.DOTALL)
        logger.info(f"银行账户信息:\n{bank_match.group(1)}")
        if bank_match:
            bank_part = bank_match.group(1)


        # 分割出交易信息（Entry Date到Credit Count之间）
        transactions_match = re.search(r'(Entry Date.*?)Credit Count', parts, re.DOTALL)
        if transactions_match:
            transactions_part = transactions_match.group(1)
        logger.info(f"交易信息:\n{transactions_part}")


        # 分割出汇总信息（Credit Count到结尾）
        summary_match = re.search(r'(Credit Count.*?)$', parts, re.DOTALL)
        if summary_match:
            summary_part = summary_match.group(1)
        logger.info(f"汇总信息: \n{summary_match.group(1)}")

        # 处理头部信息
        bank_info = extract_bank_info(bank_part)
        logger.info(f"提取到的银行账户信息: {bank_info}")

        # 处理交易信息
        transactions = extract_transactions(transactions_part)
        logger.info(f"提取到的交易信息: {transactions}")

        # 处理汇总信息
        summary_info = extract_summary_info(summary_part)
        logger.info(f"提取到的汇总信息: {summary_info}")

        # 如果没有交易记录，跳过此块
        if not transactions:
            continue

        # 为每个交易记录添加银行信息和汇总信息
        for transaction in transactions:
            record = {**bank_info, **transaction, **summary_info}

            # 确保Account_Number字段存在且类型正确
            if 'Account_Number' in record and 'Account_Number' not in record:
                record['Account_Number'] = str(record['Account_Number'])

            # 确保Account_Number非空
            if 'Account_Number' not in record or not record['Account_Number']:
                record['Account_Number'] = "未知账号"

            # 确保Amount为浮点数
            if 'Amount' in record:
                try:
                    record['Amount'] = float(record['Amount'])
                except (ValueError, TypeError):
                    record['Amount'] = 0.00
            else:
                record['Amount'] = 0.00

            all_records.append(record)

    # 创建DataFrame
    df = pd.DataFrame(all_records)

    # 将金额列转换为数值类型
    numeric_columns = ['Amount', 'Total_Credit_Amount', 'Total_Debit_Amount', 'Cheque_Amount', 'Net_Amount']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def process_citibank_report_xls(file_path: str):
    """
        处理花旗银行月度交易报告XLS文件

        参数:
            file_path: 花旗银行月度交易报告XLS文件的路径

        返回:
            处理后的交易数据DataFrame，包含与process_citibank_report_csv相同的字段
    """

    logger.info(f"开始处理花旗银行月度交易账单: {file_path}")

    try:
        # 读取XLS文件并转换为文本内容
        excel_data = pd.read_excel(file_path, sheet_name=0, header=None, engine='xlrd')

        # 将DataFrame转换为CSV格式的字符串
        csv_buffer = io.StringIO()
        excel_data.to_csv(csv_buffer, index=False, header=False)
        content = csv_buffer.getvalue()
        csv_buffer.close()

    except FileNotFoundError:
        logger.error(f"文件 {file_path} 不存在")
        raise
    except PermissionError:
        logger.error(f"没有权限读取文件 {file_path}")
        raise
    except Exception as e:
        logger.error(f"读取XLS文件 {file_path} 时发生未知错误: {str(e)}")
        raise

    # 以Bank Name字符为标记分割整个报告为多个银行账户交易信息
    bank_blocks = re.split(r'Bank Name,', content)[1:]  # 跳过第一个空元素
    logger.info(f"共有 {len(bank_blocks)} 个银行账户交易信息")

    # 处理每个银行账户的交易信息
    all_records = []

    logger.info("开始处理每个银行账户的交易信息...")
    for i, block in enumerate(bank_blocks, 1):
        # 添加回Bank Name前缀，以便后续处理
        block = "Bank Name," + block

        logger.info(f"正在处理第 {i}/{len(bank_blocks)} 个银行账户交易信息")

        # 分割每个银行账户信息，排除Cross-currency calculations部分
        parts = re.split(r'Cross-currency calculations are at indicative rates', block)[0].strip()
        logger.info(f"银行账户交易信息内容:\n{parts}")

        # 进一步分割为三个部分: 银行账户信息、交易信息、汇总信息
        bank_part = ""
        transactions_part = ""
        summary_part = ""

        # 分割出头部信（Bank Name到Entry Date之间）
        bank_match = re.search(r'(Bank Name.*?)Entry Date', parts, re.DOTALL)
        logger.info(f"银行账户信息:\n{bank_match.group(1)}")
        if bank_match:
            bank_part = bank_match.group(1)

        # 分割出交易信息（Entry Date到Credit Count之间）
        transactions_match = re.search(r'(Entry Date.*?)Credit Count', parts, re.DOTALL)
        if transactions_match:
            transactions_part = transactions_match.group(1)
        logger.info(f"交易信息:\n{transactions_part}")

        # 分割出汇总信息（Credit Count到结尾）
        summary_match = re.search(r'(Credit Count.*?)$', parts, re.DOTALL)
        if summary_match:
            summary_part = summary_match.group(1)
        logger.info(f"汇总信息: \n{summary_match.group(1)}")

        # 处理头部信息
        bank_info = extract_bank_info(bank_part)
        logger.info(f"提取到的银行账户信息: {bank_info}")

        # 处理交易信息
        transactions = extract_transactions(transactions_part)
        logger.info(f"提取到的交易信息: {transactions}")

        # 处理汇总信息
        summary_info = extract_summary_info(summary_part)
        logger.info(f"提取到的汇总信息: {summary_info}")

        # 如果没有交易记录，跳过此块
        if not transactions:
            continue

        # 为每个交易记录添加银行信息和汇总信息
        for transaction in transactions:
            record = {**bank_info, **transaction, **summary_info}
            all_records.append(record)

    # 创建DataFrame
    df = pd.DataFrame(all_records)

    # 将金额列转换为数值类型
    numeric_columns = ['Amount', 'Total_Credit_Amount', 'Total_Debit_Amount', 'Cheque_Amount', 'Net_Amount']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def extract_bank_info(bank_text):
    """从头部文本中提取银行和账户信息"""
    logger.info(f"开始提取银行账户信息...")
    # 使用CSV模块正确解析头部信息
    csv_reader = csv.reader(io.StringIO(bank_text))
    lines = list(csv_reader)

    bank_info = {}

    for line in lines:
        if len(line) > 0:
            if line[0] == 'Bank Name' and len(line) > 1:
                bank_info['Bank_Name'] = str(line[1])
                logger.info(f"银行名称: {line[1]}")
            elif line[0] == 'Customer Number / Name' and len(line) > 2:
                bank_info['Customer_Number'] = str(line[1])
                bank_info['Customer_Name'] = str(line[3])
                logger.info(f"客户信息: 客户编号{line[1]}, 客户名称{line[3]}")
            elif line[0] == 'Branch Number / Name' and len(line) > 2:
                bank_info['Branch_Number'] = str(line[1])
                bank_info['Branch_Name'] = str(line[3])
                logger.info(f"分行信息: 分行编号{line[1]}, 分行名称{line[3]}")
            elif line[0] == 'Account Number / Name' and len(line) > 2:
                bank_info['Account_Number'] = str(line[1])
                bank_info['Account_Name'] = str(line[3])
                logger.info(f"账户信息: 账户编号{line[1]}, 账户名称{line[3]}")
            elif line[0] == 'Account Currency / Type' and len(line) > 1:
                bank_info['Account_Currency'] = str(line[1])
                bank_info['Account_Type'] = str(line[3]) if len(line) > 3 else ""
                logger.info(f"账户信息: 账户货币{line[1]}, 账户类型{line[3]}")

    return bank_info


def extract_transactions(transactions_text):
    """从交易文本中提取交易记录"""
    logger.info(f"开始提取交易记录...")
    # 使用CSV模块正确解析交易信息
    csv_reader = csv.reader(io.StringIO(transactions_text))
    lines = list(csv_reader)

    transactions = []
    transaction_count = 0
    header_found = False

    for line in lines:
        if len(line) >= 10:
            if line[0] == 'Entry Date':
                header_found = True
                logger.info(f"识别到交易信息表头")
                continue

            if header_found:
                transaction_count += 1
                transaction = {
                    'Entry_Date': str(line[0]),
                    'Product_Type': str(line[1]),
                    'Transaction_Description': str(line[2]),
                    'Value_Date': str(line[3]),
                    'Bank_Reference': str(line[4]),
                    'Customer_Reference': str(line[5]),
                    'Confirmation_Reference': str(line[6]),
                    'Beneficiary': str(line[7]),
                    'Amount': clean_amount(line[8]),
                    'Currency': line[9]
                }
                logger.info(f"提取到交易记录 {transaction_count}: {transaction}")
                transactions.append(transaction)

    logger.info(f"共提取到 {transaction_count} 条交易记录")
    return transactions


def extract_summary_info(summary_text):
    """从汇总文本中提取汇总信息"""
    logger.info(f"开始提取汇总信息...")
    # 使用CSV模块正确解析汇总信息
    csv_reader = csv.reader(io.StringIO(summary_text))
    lines = list(csv_reader)

    summary_info = {}
    header_found = False
    has_cheque_info = False

    for line in lines:
        if len(line) > 0:
            if line[0] == 'Credit Count':
                header_found = True
                # 判断表头结构，确定是否包含支票信息
                if len(line) > 6 and line[6] == 'Cheque Count':
                    has_cheque_info = True
                logger.info(f"识别到汇总信息表头，{'包含' if has_cheque_info else '不包含'}支票信息")
                continue

            if header_found:
                # 找到表头后的第一行数据即为我们需要的汇总信息
                if len(line) >= 6:
                    summary_info['Credit_Count'] = int(line[0])
                    summary_info['Total_Credit_Amount'] = clean_amount(line[1])
                    summary_info['Credit_Currency'] = line[2]
                    summary_info['Debit_Count'] = int(line[3])
                    summary_info['Total_Debit_Amount'] = clean_amount(line[4])
                    summary_info['Debit_Currency'] = line[5]

                    if has_cheque_info:
                        if len(line) > 9:
                            summary_info['Cheque_Count'] = int(line[6])
                            summary_info['Cheque_Amount'] = clean_amount(line[7])
                            summary_info['Cheque_Currency'] = line[8]
                            summary_info['Net_Amount'] = clean_amount(line[9])
                            summary_info['Net_Currency'] = line[10] if len(line) > 10 else ""
                    else:
                        summary_info['Cheque_Count'] = None
                        summary_info['Cheque_Amount'] = None
                        summary_info['Cheque_Currency'] = ""
                        summary_info['Net_Amount'] = clean_amount(line[6])
                        summary_info['Net_Currency'] = line[7] if len(line) > 7 else ""

                    logger.info(f"提取到汇总信息: {summary_info}")
                    # 找到汇总信息后直接返回，不需要继续循环
                    break

    return summary_info


def clean_amount(amount_str):
    """清理金额字符串，处理格式和负数，并保留两位小数"""
    if not amount_str:
        return ""

    # 检查是否为负数（以减号结尾）
    is_negative = amount_str.endswith('-')

    # 移除减号（如果存在）
    if is_negative:
        amount_cleaned = amount_str[:-1]
    else:
        amount_cleaned = amount_str

    # 移除逗号和引号
    amount_cleaned = amount_cleaned.replace(',', '').replace('"', '')

    try:
        # 转换为浮点数
        amount_float = float(amount_cleaned)
        # 如果是负数，确保值为负
        if is_negative:
            amount_float = -abs(amount_float)

        # 格式化为两位小数的字符串
        return f"{amount_float:.2f}"
    except ValueError:
        # 如果转换失败，返回原始清理后的字符串（或空字符串，或进行错误处理）
        # 这里选择返回原始清理后的字符串，如果需要更严格的错误处理可以修改
        logger.warning(f"无法将 '{amount_str}' 转换为带两位小数的数字，返回清理后的字符串 '{amount_cleaned}'")
        if is_negative:
            return '-' + amount_cleaned
        return amount_cleaned


def process_hsbc_report_csv(file_path: str) -> pd.DataFrame:
    """处理汇丰银行月度对账单CSV文件"""
    logger.info(f"开始处理HSBC月账单文件: {file_path}")
    # 读取CSV文件
    try:
        df = pd.read_csv(file_path, keep_default_na=False, na_values=[])
        logger.info(f"CSV文件读取成功")
    except FileNotFoundError:
        logger.error(f"文件 {file_path} 不存在")
        raise
    except PermissionError:
        logger.error(f"没有权限读取文件 {file_path}")
        raise
    except pd.errors.EmptyDataError:
        logger.error(f"文件 {file_path} 为空")
        raise
    except Exception as e:
        logger.error(f"读取CSV文件 {file_path} 时发生未知错误: {str(e)}")
        raise

    # 重命名列名
    column_mapping = {
        'Account name': 'Account_Name',
        'Account number (preferred / formatted)': 'Account_Number',
        'Country/Territory': 'Country_Territory',
        'Value date': 'Value_Date',
        'Transaction type': 'Transaction_Type',
        'Account currency': 'Currency',
        'Transaction amount': 'Amount',
        'Transaction narrative': 'Transaction_Description',
        'Bank reference': 'Bank_Reference',
        'Customer reference': 'Customer_Reference',
        'Supplementary detail': 'Supplementary_Detail'
    }
    df.rename(columns=column_mapping, inplace=True)
    logger.info(f"重命名列名完成")

    # 处理账号信息，拆分出账户类型
    df['Account_Type'] = df['Account_Number'].apply(lambda x: x.split('/')[-1] if '/' in x else '')
    df['Account_Number'] = df['Account_Number'].apply(lambda x: x.split('/')[0] if '/' in x else x)

    # 清理金额字段
    df['Amount'] = df['Amount'].apply(lambda x: clean_amount(x) if isinstance(x, str) else x)

    # 转换日期格式
    df['Value_Date'] = pd.to_datetime(df['Value_Date'], format='%d/%m/%Y', errors='coerce')

    # 处理字段类型
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').round(2)
    for col in df.columns:
        if col != 'Amount':
            df[col] = df[col].astype(str)

    return df


# 测试函数
if __name__ == "__main__":
    file_path = '../../temp/HSBC_Monthly_statement.CSV'
    df = process_hsbc_report_csv(file_path)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    output_path = f"../../dataroom/hsbc_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
    df.to_excel(output_path, index=False)
    print(df)

