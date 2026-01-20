# User: ZhengYouxin
# Time: 2024-11-26 17:58:39.646723

# The R script is the ems_oversear dbconnection list for MySQL serve
library(DBI)
library(RMySQL)


# 函数返回一个数据库连接对象
create_db_connection <- function() {

  # 创建并返回连接
  con <- dbConnect(
    RMySQL::MySQL(),
    user = "cpe_oversea_prod",
    password = "x7bX!eSUb4",
    dbname = "cpe_oversea",
    host = "10.5.2.63",
    port = 3306
  )

  return(con)
}