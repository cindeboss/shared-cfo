#!/bin/bash
################################################################################
# 共享CFO爬虫 - 阿里云ECS部署脚本
################################################################################

set -e

echo "========================================="
echo "共享CFO爬虫 - ECS部署"
echo "========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量（需要根据实际情况修改）
ECS_IP="YOUR_ECS_IP_HERE"          # 请修改为你的ECS公网IP
ECS_USER="root"                    # ECS用户名
ECS_PORT="22"                      # SSH端口
PROJECT_DIR="/home/shared_cfo"     # ECS上的项目目录
MONGO_HOST="localhost"             # 如果MongoDB在同一台ECS上
MONGO_PORT="27017"
MONGO_USER="cfo_user"
MONGO_PASS="YOUR_MONGO_PASSWORD"   # 请修改为你的MongoDB密码

echo ""
echo -e "${YELLOW}[步骤 1/6] 检查本地文件...${NC}"
if [ ! -d "crawler" ]; then
    echo -e "${RED}错误: 请在项目根目录运行此脚本${NC}"
    exit 1
fi
echo -e "${GREEN}OK${NC}"

echo ""
echo -e "${YELLOW}[步骤 2/6] 打包项目文件...${NC}"
tar --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='*.log' \
    --exclude='project_status.json' \
    --exclude='project_progress.md' \
    -czf shared_cfo_crawler.tar.gz crawler/ *.py .env 2>/dev/null || echo "部分文件可能不存在"
echo -e "${GREEN}OK${NC}"

echo ""
echo -e "${YELLOW}[步骤 3/6] 上传到ECS...${NC}"
echo "目标: ${ECS_USER}@${ECS_IP}:${PROJECT_DIR}"
scp -P ${ECS_PORT} shared_cfo_crawler.tar.gz ${ECS_USER}@${ECS_IP}:/tmp/
echo -e "${GREEN}OK${NC}"

echo ""
echo -e "${YELLOW}[步骤 4/6] 在ECS上安装依赖...${NC}"
ssh -p ${ECS_PORT} ${ECS_USER}@${ECS_IP} << 'ENDSSH'
set -e

# 创建项目目录
mkdir -p /home/shared_cfo
cd /home/shared_cfo

# 解压项目
tar -xzf /tmp/shared_cfo_crawler.tar.gz
rm /tmp/shared_cfo_crawler.tar.gz

# 检查Python版本
echo "检查Python..."
python3 --version || (echo "Python3未安装，请先安装Python3" && exit 1)

# 安装依赖
echo "安装Python依赖包..."
pip3 install -q requests beautifulsoup4 pymongo pydantic

# 创建日志目录
mkdir -p logs

echo "ECS端准备完成!"
ENDSSH
echo -e "${GREEN}OK${NC}"

echo ""
echo -e "${YELLOW}[步骤 5/6] 配置环境变量...${NC}"
ssh -p ${ECS_PORT} ${ECS_USER}@${ECS_IP} << ENDSSH
cat > /home/shared_cfo/.env << EOF
# MongoDB配置
MONGO_HOST=${MONGO_HOST}
MONGO_PORT=${MONGO_PORT}
MONGO_USERNAME=${MONGO_USER}
MONGO_PASSWORD=${MONGO_PASS}
MONGO_DATABASE=shared_cfo
MONGO_COLLECTION=policies
EOF

echo "环境变量已配置"
ENDSSH
echo -e "${GREEN}OK${NC}"

echo ""
echo -e "${YELLOW}[步骤 6/6] 运行爬虫测试...${NC}"
read -p "是否立即运行爬虫测试? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ssh -p ${ECS_PORT} ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /home/shared_cfo
export $(cat .env | xargs)
nohup python3 test_crawl.py > logs/crawler.log 2>&1 &
echo "爬虫已在后台运行，PID: $!"
echo "查看日志: tail -f logs/crawler.log"
ENDSSH
fi

echo ""
echo "========================================="
echo -e "${GREEN}部署完成!${NC}"
echo "========================================="
echo ""
echo "后续操作:"
echo "1. SSH登录ECS: ssh -p ${ECS_PORT} ${ECS_USER}@${ECS_IP}"
echo "2. 查看日志: tail -f /home/shared_cfo/logs/crawler.log"
echo "3. 运行爬虫: cd /home/shared_cfo && python3 run_crawler.py crawl --phase test"
echo ""
