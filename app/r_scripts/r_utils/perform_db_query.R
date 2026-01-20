####################################################################
## 项目名称: 数据库查询功能
## 创建日期: 2024-10-18
## 程序作者: Zheng Youxin
####################################################################

library(DBI)
library(RMySQL)
library(tidyverse)


#' 执行数据库查询
#'
#' @param query_path SQL查询文件路径
#' @param conn_path 数据库连接脚本文件路径
#' @return 查询结果数据框
# 创建perform_db_query函数，两个参数：query_path，以及conn_path文件
perform_db_query <- function(query_path, conn_path) {
  result <- tryCatch({
    # 校验连接文件是否存在
    if (!file.exists(conn_path)) {
      stop(paste("数据库连接文件未找到:", conn_path))
    }
    # 加载数据库连接脚本文件
    source(conn_path)

    # 假设连接脚本定义了 create_db_connection 函数
    # 检查 create_db_connection 函数是否存在
    if (!exists("create_db_connection") || !is.function(create_db_connection)) {
        stop("函数 'create_db_connection' 未在连接脚本中定义或不是一个函数")
    }
    con <- create_db_connection()

    # 确保连接在退出时被关闭
    on.exit(dbDisconnect(con), add = TRUE)

    # 校验 SQL 文件是否存在
    if (!file.exists(query_path)) {
        stop(paste("SQL 文件未找到:", query_path))
    }
    # 读取 SQL 文件内容并确保每行结束都有换行符
    lines <- readLines(query_path, warn = FALSE)
    query <- paste(lines, collapse = "\n")

    # 使用 dbSendQuery 执行查询
    result_set <- dbSendQuery(con, query)

    # 提取所有行到一个data.frame
    data <- as_tibble(dbFetch(result_set, n = -1))

    # 清除结果集资源
    dbClearResult(result_set)

    # 返回提取的数据
    return(data)
  }, error = function(e) {
    # 打印更详细的错误信息，包括调用栈（如果可能）
    cat("数据库查询错误:", conditionMessage(e), "\n")
    # print(sys.calls()) # 可选：打印调用栈帮助调试
    return(NULL) # 或者根据需要处理错误，例如 stop(e)
  })

  return(result)
}

# 示例代码需要更新以传递连接文件路径
test_conn_file <- "app/r_scripts/r_sql/conn/ems_conn.R" # 示例路径，需要根据实际情况调整
test_sql <- "app/r_scripts/r_sql/query/QueryAccount.sql"
if (file.exists(test_conn_file) && file.exists(test_sql)) {
  test_data <- perform_db_query(test_sql, test_conn_file)
  print(test_data)
} else {
  cat("示例文件未找到，无法执行测试。\n")
}