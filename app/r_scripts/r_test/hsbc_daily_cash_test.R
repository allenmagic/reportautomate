####################################################################
## 项目名称: 汇丰银行现金报告活期余额数据处理测试用例
## 创建日期: 2025-05-07
## 程序作者: Zheng Youxin
####################################################################

source("app/r_scripts/r_processor/hsbc_daily_cash_processor.R")

# 测试用例：如果此脚本直接运行（而不是被导入），则执行测试
if (sys.nframe() == 0) {
  cat("运行 hsbc_daily_cash_processor.R 测试...\n")

  # 定义测试文件路径
  test_file_path <- "temp/AIBLSTPRINT2025-05-21-15.30.33.092000.xlsx"
  test_conn_path <- "app/r_scripts/r_sql/conn/ems_conn.R"
  test_query_path <- "app/r_scripts/r_sql/query/QueryAccount.sql"

  # 定义输出目录和文件名
  output_dir <- "dataroom"
  current_date <- format(Sys.Date(), "%Y%m%d")
  output_file <- paste0(output_dir, "/hsbc_daily_cash_", current_date, ".xlsx")

  # 创建输出目录(如果不存在)
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
    cat(paste("创建输出目录:", output_dir, "\n"))
  }

  # 检查测试文件是否存在
  if (!file.exists(test_file_path)) {
    warning(paste("测试文件不存在:", test_file_path, "- 跳过测试"))
  } else if (!file.exists(test_conn_path)) {
    warning(paste("数据库连接文件不存在:", test_conn_path, "- 跳过测试"))
  } else if (!file.exists(test_query_path)) {
    warning(paste("SQL查询文件不存在:", test_query_path, "- 跳过测试"))
  } else {
    # 执行测试
    tryCatch({
      # 添加必要的库
      if (!requireNamespace("RMySQL", quietly = TRUE)) {
        warning("缺少RMySQL包，尝试安装...")
        install.packages("RMySQL", repos="https://cran.r-project.org")
      }
      library(RMySQL)

      # 检查是否安装了writexl包
      if (!requireNamespace("writexl", quietly = TRUE)) {
        warning("缺少writexl包，尝试安装...")
        install.packages("writexl", repos="https://cran.r-project.org")
      }
      library(writexl)

      cat("开始测试 process_hsbc_data_main 函数...\n")
      test_result <- process_hsbc_data_main(
        file_path = test_file_path,
        conn_path = test_conn_path,
        query_path = test_query_path
      )

      cat("处理结果数据框：\n")
      print(head(test_result))
      cat(paste("总行数:", nrow(test_result), "\n"))

      # 导出处理结果为Excel文件
      cat(paste("正在导出结果到Excel文件:", output_file, "\n"))
      writexl::write_xlsx(test_result, output_file)
      cat(paste("Excel文件已成功导出到:", output_file, "\n"))

      cat("测试完成！\n")
    }, error = function(e) {
      cat(paste("测试失败:", e$message, "\n"))
    })
  }
}