library(stringr)
library(readr)
library(stringi)

file_path <- ""

# 2. 检查文件编码
encoding <- guess_encoding(file_path)$encoding[1]

# 3. 读取文件二进制内容
binary_content <- readBin(file_path, "raw", file.info(file_path)$size)

# 4. 使用iconv将二进制内容转换为UTF-8编码
utf8_content <- iconv(list(binary_content), from = encoding, to = "UTF-8")