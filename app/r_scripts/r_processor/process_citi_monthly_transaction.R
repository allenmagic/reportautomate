library(stringr)
library(readr)
library(stringi)

## 读取CSV文件
process_special_csv <- function(file_path) {
  # 1. 检查文件是否存在
  if (!file.exists(file_path)) {
    stop(paste("文件未找到:", file_path))
  }

  # 2. 检查文件编码
  encoding <- guess_encoding(file_path)$encoding[1]
  # 检查编码是否有效
  if (is.na(encoding)) {
    stop("无法确定文件编码，请检查文件格式")
  }
  message(paste("检测到文件编码为:", encoding))

  # 3.检查编码是否支持转换
  if (!encoding %in% iconvlist()) {
    stop(paste("不支持的编码格式:", encoding))
  }

  # 4.读取文件二进制内容
  tryCatch({
    binary_content <- readBin(file_path, "raw", file.info(file_path)$size)
    message("成功读取文件二进制内容")
    print(paste("读取到", length(binary_content), "字节数据"))
  }, error = function(e) {
    stop(paste("读取文件二进制内容时出错:", e$message))
  })

  # 5. 使用iconv将二进制内容转换为UTF-8编码文本内容
  raw_text <- iconv(list(binary_content), from = encoding, to = "UTF-8")

  # 6. 合并为单个字符串
  full_text <- paste(raw_text, collapse = " ")

  # 7. 使用正则表达式提取每条记录，每条记录以"CITIBANK"开始
  records <- unlist(strsplit(full_text, '"CITIBANK'))

  # 8. 移除第一个元素（如果它是空的）
  if (records[1] == "") {
    records <- records[-1]
  }

  # 9. 为每条记录重新添加"CITIBANK"前缀
  records <- paste0('"CITIBANK', records)

  # 10. 预分配结果列表
  parsed_records <- list()

  # 11. 遍历每条记录
  for (i in seq_along(records)) {
    # 提取双引号之间的内容
    fields <- gregexpr('"[^"]*"', records[i])
    field_contents <- regmatches(records[i], fields)[[1]]

    # 移除双引号
    field_contents <- gsub('"', '', field_contents)

    # 添加到结果列表
    parsed_records[[i]] <- field_contents
  }

  # 12. 确定最大字段数
  max_fields <- max(sapply(parsed_records, length))

  # 13. 创建数据框
  result_df <- data.frame(matrix(NA, nrow = length(parsed_records), ncol = max_fields))

  # 14. 填充数据框
  for (i in seq_along(parsed_records)) {
    result_df[i, 1:length(parsed_records[[i]])] <- parsed_records[[i]]
  }

  # 15. 设置列名
  colnames(result_df) <- paste0("Field", 1:max_fields)

  # 16. 读取字段映射文件并应用列名
  field_mappings <- read.table("app/r_scripts/r_processor/fields_mapping.txt", sep = "=",
                              stringsAsFactors = FALSE, strip.white = TRUE,
                              col.names = c("original", "mapped"))

  # 创建一个新的数据框来存储合并后的结果
  merged_df <- data.frame(row.names = 1:nrow(result_df))

  # 找出所有唯一的映射目标列名
  unique_mapped_names <- unique(field_mappings$mapped[!is.na(field_mappings$mapped) &
                                                    field_mappings$mapped != "drop" &
                                                    field_mappings$mapped != "Drop"])

  # 对每个唯一的映射名称进行处理
  for (target_name in unique_mapped_names) {
    # 找出所有映射到此名称的原始列
    source_cols <- field_mappings$original[field_mappings$mapped == target_name &
                                           field_mappings$original %in% colnames(result_df)]

    if (length(source_cols) == 0) {
      next  # 如果没有找到匹配的列，跳过
    } else if (length(source_cols) == 1) {
      # 只有一个源列，直接复制
      merged_df[[target_name]] <- result_df[[source_cols]]
    } else {
      # 有多个源列，需要合并它们的值
      merged_col <- rep(NA, nrow(result_df))

      for (row_idx in 1:nrow(result_df)) {
        for (col_name in source_cols) {
          val <- result_df[row_idx, col_name]
          if (!is.na(val) && nchar(trimws(val)) > 0) {
            # 如果找到非空值，使用它并停止寻找
            merged_col[row_idx] <- val
            break
          }
        }
      }

      merged_df[[target_name]] <- merged_col
    }
  }

  # 将合并后的数据框替换原来的结果
  result_df <- merged_df
  
  return(result_df)

}

extract_citi_transactions <- function(file_path) {
  # 读取为字符向量
  lines <- readLines(file_path, encoding = "UTF-8")

  # 要输出的结果
  result_list <- list()

  # 当前账户头信息
  acc_info <- list()

  i <- 1
  while(i <= length(lines)) {
    line <- lines[i]
    fields <- strsplit(line, ",")[[1]]
    # 判断是否为账户头的几个关键字行
    if(startsWith(line, "Bank Name")) {
      acc_info$Bank_Name <- fields[2]
      i <- i + 1; fields <- strsplit(lines[i], ",")[[1]]
      acc_info$Customer_Number <- fields[2]
      acc_info$Customer_Name <- fields[4]
      i <- i + 1; fields <- strsplit(lines[i], ",")[[1]]
      acc_info$Branch_Number <- fields[2]
      acc_info$Branch_Name <- fields[4]
      i <- i + 1; fields <- strsplit(lines[i], ",")[[1]]
      acc_info$Acconut_Number <- fields[2]
      acc_info$Account_Name <- fields[4]
      i <- i + 1; fields <- strsplit(lines[i], ",")[[1]]
      acc_info$Account_Currency <- fields[2]
      acc_info$Account_Type <- trimws(ifelse(length(fields) >= 4, fields[4], ""))
      # 跳过表头和空行
      i <- i + 2
      # 遇到交易表头
      trx_header <- strsplit(lines[i], ",")[[1]]
      i <- i + 1
      # 开始逐条读取明细行，直到遇到Credit Count或下一个Bank Name
      while(i <= length(lines)) {
        thisline <- lines[i]
        thisfields <- strsplit(thisline, ",")[[1]]
        if(startsWith(thisline, "Credit Count")) {
          # 读取汇总行
          credit <- as.integer(thisfields[2])
          credit_amt <- as.numeric(gsub("[\",]", "", thisfields[3]))
          credit_currency <- thisfields[4]
          debit <- as.integer(thisfields[5])
          debit_amt <- as.numeric(gsub("[\",]", "", thisfields[6]))
          debit_currency <- thisfields[7]
          cheque_count <- ifelse(length(thisfields) >= 9, as.integer(thisfields[8]), NA)
          cheque_amt <- ifelse(length(thisfields) >= 10, as.numeric(gsub("[\",]", "", thisfields[9])), NA)
          cheque_ccy <- ifelse(length(thisfields) >= 11, thisfields[10], NA)
          net_amt <- as.numeric(gsub("[\",]", "", thisfields[11]))
          net_ccy <- ifelse(length(thisfields) >= 12, thisfields[12], NA)
          # 汇总行存入当前账户头信息
          acc_info$Credit_Count <- credit
          acc_info$Total_Credit_Amount <- credit_amt
          acc_info$Credit_Currency <- credit_currency
          acc_info$Debit_Count <- debit
          acc_info$Total_Debit_Amount <- debit_amt
          acc_info$Cheque_Count <- cheque_count
          acc_info$Cheque_Amount <- cheque_amt
          acc_info$Net_Amount <- net_amt
          # 跳过若干非交易内容行
          while(i+1 <= length(lines) && !startsWith(lines[i+1], "Bank Name")) i <- i + 1
          break
        }
        # 跳过空白行
        if(sum(trimws(thisfields) != "") == 0) {
          i <- i + 1
          next
        }
        # 以明细行输出
        if(!startsWith(thisline, "Cross-currency")) {
          # 明细字段解析
          Entry_Date <- thisfields[1]
          Product_Type <- thisfields[2]
          Transaction_Description <- thisfields[3]
          Value_Date <- thisfields[4]
          Bank_Reference <- thisfields[5]
          Customer_Reference <- thisfields[6]
          Confirmation_Reference <- thisfields[7]
          Beneficiary <- thisfields[8]
          Amount_raw <- gsub("[\",]", "", thisfields[9])
          # 金额及币种
          Amount <- suppressWarnings(as.numeric(Amount_raw))
          Currency <- thisfields[10]

          # 写入结果列表
          res <- data.frame(
            Bank_Name = acc_info$Bank_Name,
            Customer_Number = acc_info$Customer_Number,
            Customer_Name = acc_info$Customer_Name,
            Branch_Number = acc_info$Branch_Number,
            Branch_Name = acc_info$Branch_Name,
            Acconut_Number = acc_info$Acconut_Number,
            Account_Name = acc_info$Account_Name,
            Account_Type = acc_info$Account_Type,
            Account_Currency = acc_info$Account_Currency,
            Entry_Date = Entry_Date,
            Product_Type = Product_Type,
            Transaction_Description = Transaction_Description,
            Value_Date = Value_Date,
            Bank_Reference = Bank_Reference,
            Customer_Reference = Customer_Reference,
            Confirmation_Reference = Confirmation_Reference,
            Beneficiary = Beneficiary,
            Amount = Amount,
            Currency = Currency,
            Credit_Count = NA,
            Total_Credit_Amount = NA,
            Credit_Currency = NA,
            Debit_Count = NA,
            Total_Debit_Amount = NA,
            Cheque_Count = NA,
            Cheque_Amount = NA,
            Net_Amount = NA,
            stringsAsFactors = FALSE
          )
          result_list[[length(result_list) + 1]] <- res
        }
        i <- i + 1
      }
    }
    i <- i + 1
  }
  # 合并所有结果
  do.call(rbind, result_list)
}


# 使用示例
df <- process_special_csv("temp/MonthlyTransaction_ALL.csv")



