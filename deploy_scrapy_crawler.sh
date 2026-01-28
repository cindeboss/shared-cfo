#!/bin/bash
################################################################################
# 共享CFO - Scrapy 爬虫自动部署脚本
# 使用方法: bash deploy_scrapy_crawler.sh
################################################################################

set -e

echo "========================================="
echo "共享CFO - Scrapy 爬虫自动部署"
echo "========================================="
echo ""

# 配置
ECS_IP="120.78.5.4"
ECS_USER="root"
ECS_DIR="/opt/shared_cfo"
SSH_KEY="$HOME/.ssh/id_ed25519"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "配置信息:"
echo "  ECS IP: $ECS_IP"
echo "  部署目录: $ECS_DIR"
echo "  项目目录: $PROJECT_DIR"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 步骤 1: 测试 SSH 连接
echo -e "${YELLOW}[1/8]${NC} 测试 SSH 连接..."
ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
    ${ECS_USER}@${ECS_IP} "echo 'SSH连接成功!' && python3 --version"

# 步骤 2: 准备 ECS 环境
echo ""
echo -e "${YELLOW}[2/8]${NC} 准备 ECS 环境..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
# 创建目录
mkdir -p /opt/shared_cfo
mkdir -p /opt/shared_cfo/logs
mkdir -p /opt/shared_cfo/output
mkdir -p /opt/shared_cfo/crawler

# 检查 MongoDB
echo "检查 MongoDB..."
if ! systemctl is-active --quiet mongod; then
    echo "MongoDB 未运行，尝试启动..."
    systemctl start mongod || systemctl start mongodb
    sleep 3
fi

# 检查 MongoDB 连接
python3 -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017/').admin.command('ping')" || {
    echo "MongoDB 连接失败，请检查安装"
    exit 1
}

echo "MongoDB 运行正常"
ENDSSH

# 步骤 3: 安装 Python 依赖
echo ""
echo -e "${YELLOW}[3/8]${NC} 安装 Python 依赖..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared_cfo

# 更新 pip
pip3 install -q --upgrade pip

# 安装 Scrapy 和依赖
echo "安装 Scrapy 及相关依赖..."
pip3 install -q --upgrade \
    scrapy \
    requests \
    beautifulsoup4 \
    pymongo \
    pydantic \
    python-dotenv \
    lxml

echo "依赖安装完成"
pip3 list | grep -E "scrapy|pymongo|requests"
ENDSSH

# 步骤 4: 上传 Scrapy 爬虫代码
echo ""
echo -e "${YELLOW}[4/8]${NC} 上传 Scrapy 爬虫代码..."

# 打包 Scrapy 项目
echo "打包 Scrapy 项目..."
tar --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='*.log' \
    --exclude='output' \
    --exclude='.scrapy_cache' \
    -czf /tmp/scrapy_crawler.tar.gz \
    -C "$PROJECT_DIR" crawler/scrapy_spider \
    crawler/data_models_v2.py \
    crawler/database_v2.py \
    .env 2>/dev/null || echo "部分文件不存在，继续..."

# 上传
scp -i "$SSH_KEY" /tmp/scrapy_crawler.tar.gz \
    ${ECS_USER}@${ECS_IP}:/tmp/ 2>/dev/null || true

# 解压
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared_cfo
rm -rf crawler/scrapy_spider
tar -xzf /tmp/scrapy_crawler.tar.gz
rm -f /tmp/scrapy_crawler.tar.gz
ls -la crawler/scrapy_spider/
ENDSSH

rm -f /tmp/scrapy_crawler.tar.gz
echo "Scrapy 爬虫代码上传完成"

# 步骤 5: 创建启动脚本
echo ""
echo -e "${YELLOW}[5/8]${NC} 创建启动脚本..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cat > /opt/shared_cfo/run_scrapy.sh << 'EOFSCRIPT'
#!/bin/bash
# Scrapy 爬虫启动脚本

cd /opt/shared_cfo

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 获取参数
CATEGORY=${1:-all}
START_YEAR=${2:-2022}
END_YEAR=${3:-2026}

echo "========================================="
echo "启动 Scrapy 爬虫"
echo "========================================="
echo "分类: $CATEGORY"
echo "年份: $START_YEAR - $END_YEAR"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 运行 Scrapy
scrapy crawl chinatax_policy \
    -a category="$CATEGORY" \
    -a start_year="$START_YEAR" \
    -a end_year="$END_YEAR" \
    -L INFO \
    -o "output/crawl_\$(date +%Y%m%d_%H%M%S).json"

echo ""
echo "爬虫执行完成!"
EOFSCRIPT

chmod +x /opt/shared_cfo/run_scrapy.sh
echo "启动脚本创建完成"
ENDSSH

# 步骤 6: 创建 systemd 服务
echo ""
echo -e "${YELLOW}[6/8]${NC} 创建 systemd 服务..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cat > /etc/systemd/system/shared-cfo-crawler.service << 'EOFSERVICE'
[Unit]
Description=Shared CFO Tax Policy Crawler
After=network.target mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/shared_cfo
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/shared_cfo/run_scrapy.sh all 2022 2026
Restart=on-failure
RestartSec=60
StandardOutput=append:/opt/shared_cfo/logs/crawler.log
StandardError=append:/opt/shared_cfo/logs/crawler_error.log

[Install]
WantedBy=multi-user.target
EOFSERVICE

# 重新加载 systemd
systemctl daemon-reload

echo "systemd 服务创建完成"
ENDSSH

# 步骤 7: 创建定时任务（可选）
echo ""
echo -e "${YELLOW}[7/8]${NC} 配置定时任务..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
# 检查是否已存在定时任务
if ! crontab -l 2>/dev/null | grep -q "run_scrapy.sh"; then
    # 添加定时任务：每天凌晨 2 点运行
    (crontab -l 2>/dev/null; echo "0 2 * * * cd /opt/shared_cfo && bash run_scrapy.sh >> logs/cron.log 2>&1") | crontab -
    echo "定时任务已添加: 每天凌晨 2 点运行"
else
    echo "定时任务已存在，跳过"
fi
ENDSSH

# 步骤 8: 测试运行
echo ""
echo -e "${YELLOW}[8/8]${NC} 测试运行..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared_cfo

echo "运行测试爬取（5页）..."
scrapy crawl chinatax_policy \
    -a category="法律" \
    -s CLOSESPIDER_PAGECOUNT=5 \
    -s LOG_LEVEL=INFO \
    -o output/test.json

echo ""
echo "测试结果:"
if [ -f output/test.json ]; then
    echo "✓ 输出文件已生成"
    echo "  文件大小: $(wc -c < output/test.json) 字节"
    echo "  数据条数: $(python3 -c "import json; print(len(json.load(open('output/test.json'))))") 条"
else
    echo "✗ 输出文件未生成"
fi
ENDSSH

# 部署完成
echo ""
echo "========================================="
echo -e "${GREEN}部署完成!${NC}"
echo "========================================="
echo ""
echo "后续操作:"
echo ""
echo "1. 手动运行爬虫:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP}"
echo "   cd /opt/shared_cfo && bash run_scrapy.sh"
echo ""
echo "2. 启动系统服务（自动运行）:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP} 'systemctl start shared-cfo-crawler'"
echo ""
echo "3. 查看运行状态:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP} 'systemctl status shared-cfo-crawler'"
echo ""
echo "4. 查看日志:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP} 'tail -f /opt/shared_cfo/logs/crawler.log'"
echo ""
echo "5. 查看数据:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP} 'python3 -c \"from pymongo import MongoClient; print(MongoClient(\\\"mongodb://localhost:27017/\\\").shared_cfo.policies.count_documents({}))\"'"
echo ""
