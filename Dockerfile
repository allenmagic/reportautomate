FROM docker.io/library/python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    APP_HOST=0.0.0.0 \
    DEBIAN_FRONTEND=noninteractive

# 安装系统依赖（移除 TeX Live）
RUN echo "=== 安装系统依赖 ===" && \
    apt-get update && apt-get install -y --no-install-recommends \
    # 基础编译工具
    build-essential p7zip-full libmariadb-dev-compat \
    # R 语言环境
    r-base r-base-dev r-cran-readxl r-cran-dplyr \
    r-cran-jsonlite r-cran-tidyverse r-cran-readr \
    # 下载工具
    curl ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装 Typst（x86_64 架构）
RUN echo "=== 安装 Typst ===" && \
    TYPST_VERSION="0.14.0" && \
    curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" -o /tmp/typst.tar.xz && \
    tar -xJf /tmp/typst.tar.xz -C /tmp && \
    mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst && \
    chmod +x /usr/local/bin/typst && \
    rm -rf /tmp/typst* && \
    typst --version && \
    echo "✓ Typst 安装成功"

# 创建字体目录
RUN mkdir -p /usr/share/fonts/custom

# 复制字体文件到容器（在 COPY 应用代码之前）
COPY resources/fonts/*.ttf /usr/share/fonts/custom/
COPY resources/fonts/*.ttc /usr/share/fonts/custom/

# 验证字体文件
RUN echo "=== 验证字体文件 ===" && \
    ls -lh /usr/share/fonts/custom/ && \
    fc-cache -fv && \
    echo "✓ 字体文件复制成功"

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 R 包
RUN Rscript -e 'install.packages(c("RMySQL","feather"), repos="http://cran.rstudio.com/")'

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p /app/temp /app/logs /app/rpa_reports

EXPOSE 8000
CMD ["python", "run.py"]
