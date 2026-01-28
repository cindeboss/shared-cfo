#!/bin/bash
################################################################################
# 将新的共享CFO爬虫系统部署到阿里云ECS
################################################################################

set -e

echo "========================================="
echo "共享CFO爬虫 - 部署到ECS"
echo "========================================="
echo ""

# ECS配置
ECS_IP="120.78.5.4"
ECS_USER="root"
ECS_DIR="/opt/shared-cfo"
SSH_KEY="$HOME/.ssh/id_ed25519"

echo "ECS信息:"
echo "  IP: $ECS_IP"
echo "  用户: $ECS_USER"
echo "  目录: $ECS_DIR"
echo ""

# 测试SSH连接
echo "[1/7] 测试SSH连接..."
ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
    ${ECS_USER}@${ECS_IP} "echo 'SSH连接成功!'" || {
    echo "SSH连接失败，请检查:"
    echo "1. ECS是否运行: ping $ECS_IP"
    echo "2. SSH密钥是否正确: ls -la $SSH_KEY"
    echo "3. 手动测试: ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP}"
    exit 1
}

echo ""
echo "[2/7] 在ECS上准备环境..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << ENDSSH
set -e

# 创建项目目录
mkdir -p /opt/shared-cfo
mkdir -p /opt/shared-cfo/logs
cd /opt/shared-cfo

# 检查Python
echo "检查Python..."
python3 --version || (echo "Python3未安装" && exit 1)

# 安装依赖
echo "安装依赖包..."
pip3 install -q requests beautifulsoup4 pymongo pydantic || pip3 install requests beautifulsoup4 pymongo pydantic

echo "ECS环境准备完成!"
ENDSSH

echo ""
echo "[3/7] 上传爬虫代码..."
# 打包代码（排除不需要的文件）
tar --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='*.log' \
    --exclude='project_status.json' \
    --exclude='project_progress.md' \
    -czf /tmp/shared_cfo_new.tar.gz \
    crawler/ run_crawler.py test_crawl.py .env

# 上传到ECS
scp -i "$SSH_KEY" /tmp/shared_cfo_new.tar.gz \
    ${ECS_USER}@${ECS_IP}:/tmp/

# 在ECS上解压
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared-cfo
tar -xzf /tmp/shared_cfo_new.tar.gz
rm /tmp/shared_cfo_new.tar.gz
ls -la
ENDSSH

rm /tmp/shared_cfo_new.tar.gz
echo "代码上传完成!"

echo ""
echo "[4/7] 配置MongoDB连接..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared-cfo

# 创建环境配置 - 使用ECS自建的MongoDB
cat > .env << 'EOF'
# MongoDB配置 - ECS自建MongoDB
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_USERNAME=
MONGO_PASSWORD=
MONGO_DATABASE=shared_cfo
MONGO_COLLECTION=policies
EOF

echo "环境配置已创建（使用本地MongoDB）"
ENDSSH

echo ""
echo "[5/7] 测试数据库连接..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared-cfo

# 检查MongoDB是否运行
echo "检查MongoDB服务..."
systemctl status mongodb || systemctl status mongod || service mongodb status

# 测试连接
python3 << 'EOPY'
from pymongo import MongoClient

print("连接本地MongoDB...")
try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("数据库连接成功!")

    # 检查/创建数据库
    db = client['shared_cfo']
    total = db['policies'].count_documents({})
    print(f"当前数据库中有 {total} 条政策记录")
except Exception as e:
    print(f"数据库连接失败: {e}")
    print("请确保MongoDB正在运行: systemctl start mongodb")
EOPY
ENDSSH

echo ""
echo "[6/7] 运行爬虫测试..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared-cfo
export $(cat .env | xargs)

# 测试爬虫（不使用数据库的版本）
echo "运行爬虫测试..."
timeout 60 python3 test_crawl_no_db.py || echo "测试完成或超时"
ENDSSH

echo ""
echo "========================================="
echo "部署完成!"
echo "========================================="
echo ""
echo "后续操作:"
echo ""
echo "1. 查看日志:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP} 'tail -f /opt/shared-cfo/logs/*.log'"
echo ""
echo "2. 运行完整爬虫:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP}"
echo "   cd /opt/shared-cfo && python3 run_crawler.py crawl --phase test"
echo ""
echo "3. 查看系统状态:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP}"
echo "   cd /opt/shared-cfo && python3 run_crawler.py status"
echo ""
echo "4. 后台运行:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP}"
echo "   cd /opt/shared-cfo && nohup python3 run_crawler.py crawl --phase test > logs/crawl.out 2>&1 &"
echo ""
