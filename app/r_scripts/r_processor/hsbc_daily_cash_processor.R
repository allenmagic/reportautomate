# 只加载必要的库
suppressPackageStartupMessages({
  library(readxl)     # 用于读取Excel文件
  library(dplyr)      # 用于数据处理
  library(jsonlite)   # 用于JSON转换
  library(magrittr)
  library(feather)
})

#' 读取HSBC的Excel文件
#' @param file_path Excel文件路径
#' @param sheet_index 工作表索引，默认为1
#' @param has_header 是否有表头，默认为TRUE
#' @return 读取Excel的数据框
read_excel_file <- function(file_path, sheet_index = 1, has_header = TRUE) {
  if (!file.exists(file_path)) {
    stop(paste("错误: 文件不存在:", file_path))
  }

  tryCatch({
    df <- read_excel(file_path, sheet = sheet_index, col_names = has_header)
    return(df)
  }, error = function(e) {
    stop(paste("读取Excel文件失败:", e$message))
  })
}


#' 执行数据库查询
#' @param query_path SQL查询文件路径
#' @param conn_path 数据库连接文件路径
#' @return 查询结果数据框
execute_db_query <- function(query_path, conn_path) {

  # 使用固定路径进行检查
  if (!file.exists(query_path)) {
    stop(paste("错误: SQL查询文件不存在:", query_path))
  }

  if (!file.exists(conn_path)) {
    stop(paste("错误: 数据库连接文件不存在:", conn_path))
  }

  tryCatch({
    # 加载包含 perform_db_query 的脚本
    source('app/r_scripts/r_utils/perform_db_query.R')
    # 调用 perform_db_query 时传递 query_path 和 conn_path 参数
    # 注意：假设 perform_db_query 的参数名是 query_path 和 conn_path
    df <- perform_db_query(query_path = query_path, conn_path = conn_path)
    return(df)
  }, error = function(e) {
    # 改进错误消息，包含原始错误
    stop(paste("数据库查询失败:", e$message))
  })
}

#' 处理HSBC账户数据
#' @param hsbc_data HSBC源数据框
#' @param account_data 账户数据框
#' @param bank_name 银行名称
#' @return 处理后的数据框
process_hsbc_account_data <- function(hsbc_data, account_data,
                                      bank_name = "The Hongkong and Shanghai Banking Corporation Limited") {
  # 入参数据类型检查
  if (!is.data.frame(hsbc_data)) {
    stop("错误: hsbc_data 必须是数据框(data.frame)类型")
  }

  if (!is.data.frame(account_data)) {
    stop("错误: account_data 必须是数据框(data.frame)类型")
  }

  # 过滤特定银行的账户
  account_data_filtered <- account_data %>%
    filter(BankBrokerName == bank_name)

  if (nrow(account_data_filtered) == 0) {
    warning(paste("警告: 未找到指定银行的账户:", bank_name))
  }

  # 处理HSBC数据
  tryCatch({
    df_hsbc <- hsbc_data %>%
      select('Currency', 'Account number', 'Current available', 'As at date / time') %>%
      rename(
        account_currency = 'Currency',
        account_number = 'Account number',
        account_balance = 'Current available',
        account_date = 'As at date / time'
      ) %>%
      mutate(
        account_number = gsub("^\\s*(.*?)\\s*/.*$", "\\1", account_number),
        account_balance = as.numeric(gsub(",", "", account_balance)),
        account_date = as.Date(account_date, format = "%d/%m/%Y")  # 转换为Date类型而非POSIXct
      ) %>%
      group_by(account_number,account_currency) %>%
      summarise(
        account_balance = sum(account_balance, na.rm = TRUE),
        account_date = max(account_date),
        .groups = "drop"
      ) %>%
      ungroup()

    # 合并数据
    result_df <- df_hsbc %>%
      left_join(account_data_filtered, by = c("account_number" = "AccountNumber"))

    # 检查是否有缺失值
    missing_rows <- result_df %>% filter(if_any(everything(), is.na))
    if (nrow(missing_rows) > 0) {
      warning(paste("警告: 有", nrow(missing_rows), "行数据包含缺失值"))
    }

    # 最终处理 - 重命名字段以匹配Python模型
    final_df <- result_df %>%
      filter(!if_any(everything(), is.na)) %>%   # 去除所有包含NA的行
      distinct() %>%  # 去除重复记录
      select(
        account_number = 'account_number',
        account_currency = 'account_currency',
        account_balance = 'account_balance',
        account_date = 'account_date',
        bank_short_name = 'ShortName',
        bank_location = 'Location'
      )

    return(final_df)

  }, error = function(e) {
    stop(paste("处理HSBC数据失败:", e$message))
  })
}

#' 主函数：处理HSBC账户数据的完整流程
#' @param file_path HSBC数据文件路径
#' @param config_path 配置文件路径
#' @param conn_path 数据库连接文件路径
#' @param query_path SQL查询文件路径
#' @param bank_name 银行名称
#' @param output_dir 输出目录，默认为"dataroom"
#' @return 处理后的数据框
#' @export
process_hsbc_data_main <- function(file_path, conn_path, query_path,
                                  bank_name = "The Hongkong and Shanghai Banking Corporation Limited",
                                  output_dir = "dataroom") {
  # 读取Excel文件
  hsbc_source_data <- read_excel_file(file_path)

  # 执行数据库查询
  source('app/r_scripts/r_utils/perform_db_query.R')
  account_list_data <- perform_db_query(query_path, conn_path)

  # 处理数据
  result <- process_hsbc_account_data(hsbc_source_data, account_list_data, bank_name)

  # 创建输出目录（如果不存在）
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # 生成输出文件名（基于当前日期时间）
  timestamp <- format(Sys.time(), "%Y%m%d_%H%M%S")
  output_file <- file.path(output_dir, paste0("hsbc_daily_cash_", timestamp, ".feather"))

  # 将结果保存为feather格式
  write_feather(result, output_file)

  # 输出保存信息
  message(paste("数据已保存到:", output_file))

  return(result)
}
