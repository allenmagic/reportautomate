#!/bin/bash

set -e

# 配置变量
DOCKER_IMAGE_PROD="statement"
DOCKER_IMAGE_DEV="statement_test"
PORT_PROD="8000"
PORT_DEV="8001"

ENVIRONMENT=$1
DOCKER_TAG=${2:-latest}

if [ -z "$ENVIRONMENT" ]; then
    echo "用法: $0 [dev|prod] [tag]"
    exit 1
fi

# 设置环境变量
case $ENVIRONMENT in
    "prod")
        DOCKER_IMAGE=$DOCKER_IMAGE_PROD
        PORT=$PORT_PROD
        ;;
    "dev")
        DOCKER_IMAGE=$DOCKER_IMAGE_DEV
        PORT=$PORT_DEV
        ;;
    *)
        echo "错误: 无效环境 $ENVIRONMENT"
        exit 1
        ;;
esac

# 记录开始时间
START_TIME=$(date +%s)
DEPLOY_TIME=$(date '+%Y-%m-%d %H:%M:%S')

echo "=== 开始部署 ==="
echo "服务器: $(hostname)"
echo "工作目录: $(pwd)"
echo "环境: $ENVIRONMENT"
echo "镜像: $DOCKER_IMAGE:$DOCKER_TAG"
echo "端口: $PORT"
echo "开始时间: $DEPLOY_TIME"

# 创建/更新环境变量文件
echo "更新环境变量文件..."
cat > .env << EOF
DOCKER_IMAGE=$DOCKER_IMAGE
DOCKER_TAG=$DOCKER_TAG
PORT=$PORT
ENVIRONMENT=$ENVIRONMENT
BUILD_TIME=$DEPLOY_TIME
EOF

# 初始化结果文件
cat > deploy-result.txt << EOF
DEPLOY_STATUS=running
DEPLOY_ENV=$ENVIRONMENT
DEPLOY_TAG=$DOCKER_TAG
DEPLOY_TIME=$DEPLOY_TIME
DEPLOY_SERVER=$(hostname)
EOF

# 1. 构建新镜像
echo "构建镜像 $DOCKER_IMAGE:$DOCKER_TAG ..."
if podman build -t $DOCKER_IMAGE:$DOCKER_TAG .; then
    echo "✅ 镜像构建成功"
    BUILD_STATUS="success"
else
    echo "❌ 镜像构建失败"
    cat > deploy-result.txt << EOF
DEPLOY_STATUS=failed
DEPLOY_ENV=$ENVIRONMENT
DEPLOY_TAG=$DOCKER_TAG
DEPLOY_TIME=$DEPLOY_TIME
BUILD_STATUS=failed
ERROR_STAGE=build
EOF
    exit 1
fi

# 2. 重启容器使用新镜像
echo "重启容器使用新镜像..."
if podman-compose up -d --force-recreate; then
    echo "✅ 容器重启成功"
    DEPLOY_STATUS="success"
else
    echo "❌ 容器重启失败"
    cat > deploy-result.txt << EOF
DEPLOY_STATUS=failed
DEPLOY_ENV=$ENVIRONMENT
DEPLOY_TAG=$DOCKER_TAG
DEPLOY_TIME=$DEPLOY_TIME
BUILD_STATUS=$BUILD_STATUS
ERROR_STAGE=restart
EOF
    exit 1
fi

# 3. 等待容器稳定
echo "等待容器稳定..."
sleep 5

# 4. 检查容器状态
echo "检查容器状态..."
CONTAINER_STATUS=$(podman-compose ps --format "table {{.Status}}" | grep -v STATUS | head -1 || echo "unknown")
echo "容器状态: $CONTAINER_STATUS"

# 计算执行时间
END_TIME=$(date +%s)
EXECUTION_TIME=$((END_TIME - START_TIME))

echo "=== 部署完成 ==="
echo "访问地址: http://localhost:$PORT"
echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "执行时间: ${EXECUTION_TIME}秒"

# 生成最终结果文件
cat > deploy-result.txt << EOF
DEPLOY_STATUS=success
DEPLOY_ENV=$ENVIRONMENT
DEPLOY_TAG=$DOCKER_TAG
DEPLOY_TIME=$DEPLOY_TIME
DEPLOY_SERVER=$(hostname)
BUILD_STATUS=$BUILD_STATUS
CONTAINER_STATUS=$CONTAINER_STATUS
EXECUTION_TIME=${EXECUTION_TIME}s
DEPLOY_URL=http://localhost:$PORT
COMPLETION_TIME=$(date '+%Y-%m-%d %H:%M:%S')
EOF

echo "部署结果已保存到 deploy-result.txt"
echo "部署结果内容:"
cat deploy-result.txt

echo "🎉 部署成功完成！"
exit 0