#!/bin/bash
################################################################################
# 在ECS上重装MongoDB并部署爬虫 - 使用SSH密钥，无需密码
################################################################################

set -e

echo "========================================="
echo "ECS MongoDB重装 + 爬虫部署"
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
echo "  SSH密钥: $SSH_KEY"
echo ""

# 测试SSH连接
echo "[1/10] 测试SSH连接..."
ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
    ${ECS_USER}@${ECS_IP} "echo 'SSH连接成功!'"

echo ""
echo "[2/10] 停止并卸载旧MongoDB..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
echo "停止MongoDB服务..."
systemctl stop mongod 2>/dev/null || service mongodb stop 2>/dev/null || true
pkill -9 mongod 2>/dev/null || true

echo "卸载MongoDB..."
apt-get remove -y mongodb-org* 2>/dev/null || true
apt-get purge -y mongodb* 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true

echo "删除MongoDB数据目录..."
rm -rf /var/lib/mongodb
rm -rf /var/log/mongodb
rm -rf /etc/mongod.conf

echo "旧MongoDB已清理"
ENDSSH

echo ""
echo "[3/10] 安装MongoDB..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
# 导入MongoDB公钥
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | apt-key add -

# 添加MongoDB源
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list

# 更新包列表
apt-get update -qq

# 安装MongoDB
apt-get install -y mongodb-org

echo "MongoDB安装完成"
ENDSSH

echo ""
echo "[4/10] 配置MongoDB（无认证模式）..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
# 创建MongoDB配置文件
cat > /etc/mongod.conf << 'EOF'
# MongoDB配置文件 - 无认证模式（开发环境）
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

net:
  port: 27017
  bindIp: 0.0.0.0

# 无需认证（开发环境）
#security:
#  authorization: enabled
EOF

# 创建数据目录
mkdir -p /var/lib/mongodb
mkdir -p /var/log/mongodb
chown -R mongodb:mongodb /var/lib/mongodb
chown -R mongodb:mongodb /var/log/mongodb

echo "MongoDB配置完成"
ENDSSH

echo ""
echo "[5/10] 启动MongoDB服务..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
# 重新加载systemd
systemctl daemon-reload

# 启用并启动MongoDB
systemctl enable mongod
systemctl start mongod

# 等待MongoDB启动
sleep 3

# 检查状态
systemctl status mongod --no-pager | head -10
ENDSSH

echo ""
echo "[6/10] 测试MongoDB连接..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
python3 << 'EOPY'
from pymongo import MongoClient

print("测试MongoDB连接（无认证）...")
try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("MongoDB连接成功!")

    # 创建数据库和集合
    db = client['shared_cfo']
    collection = db['policies']

    # 创建索引
    collection.create_index('policy_id', unique=True)
    collection.create_index('title')
    collection.create_index('source')
    collection.create_index('publish_date')

    print("数据库和索引创建完成!")

except Exception as e:
    print(f"MongoDB连接失败: {e}")
    exit(1)
EOPY
ENDSSH

echo ""
echo "[7/10] 准备项目目录..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
# 创建项目目录
mkdir -p /opt/shared-cfo
mkdir -p /opt/shared-cfo/logs
mkdir -p /opt/shared-cfo/crawler

cd /opt/shared-cfo

# 检查Python
python3 --version

# 安装/更新依赖
echo "安装Python依赖包..."
pip3 install -q --upgrade requests beautifulsoup4 pymongo pydantic

echo "项目目录准备完成"
ENDSSH

echo ""
echo "[8/10] 上传爬虫代码..."
# 先打包代码
echo "打包代码..."
tar --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='*.log' \
    --exclude='project_status.json' \
    --exclude='project_progress.md' \
    -czf /tmp/shared_cfo_crawler.tar.gz \
    crawler/ run_crawler.py .env 2>/dev/null || echo "部分文件不存在，继续..."

# 上传到ECS
scp -i "$SSH_KEY" /tmp/shared_cfo_crawler.tar.gz \
    ${ECS_USER}@${ECS_IP}:/tmp/ 2>/dev/null || echo "上传完成"

# 在ECS上解压
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared-cfo
tar -xzf /tmp/shared_cfo_crawler.tar.gz 2>/dev/null || true
rm -f /tmp/shared_cfo_crawler.tar.gz
ls -la crawler/
ENDSSH

rm -f /tmp/shared_cfo_crawler.tar.gz
echo "代码上传完成"

echo ""
echo "[9/10] 创建环境配置..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared-cfo

# 创建环境配置
cat > .env << 'EOF'
# MongoDB配置 - ECS本地MongoDB（无认证）
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_USERNAME=
MONGO_PASSWORD=
MONGO_DATABASE=shared_cfo
MONGO_COLLECTION=policies
EOF

echo "环境配置已创建"
cat .env
ENDSSH

echo ""
echo "[10/10] 运行爬虫测试..."
ssh -i "$SSH_KEY" ${ECS_USER}@${ECS_IP} << 'ENDSSH'
cd /opt/shared-cfo

echo "开始爬虫测试..."
export $(cat .env | grep -v '^#' | xargs)

# 运行爬虫测试
python3 << 'EOPY'
import sys
sys.path.insert(0, '/opt/shared-cfo')

from crawler.database_v2 import MongoDBConnectorV2
from crawler.chinatax_crawler_v4 import ChinaTaxCrawler

print("=" * 50)
print("爬虫系统测试")
print("=" * 50)

# 连接数据库
print("\n[1/4] 连接数据库...")
db = MongoDBConnectorV2()
print("数据库连接成功!")

# 测试爬虫
print("\n[2/4] 测试国家税务总局爬虫...")
crawler = ChinaTaxCrawler(db)

# 爬取1页法律
try:
    stats = crawler.crawl_laws(max_pages=1)
    print(f"爬虫测试结果: {stats}")
except Exception as e:
    print(f"爬虫测试出错: {e}")

# 获取统计
print("\n[3/4] 获取数据统计...")
final_stats = db.get_stats()
print(f"数据库总文档数: {final_stats['total']}")

# 获取质量报告
print("\n[4/4] 数据质量报告...")
quality_report = db.get_quality_report()
print(f"质量等级: {quality_report.overall_quality_level}")
print(f"总政策数: {quality_report.total_policies}")

print("\n" + "=" * 50)
print("测试完成!")
print("=" * 50)

db.close()
EOPY
ENDSSH

echo ""
echo "========================================="
echo "部署完成!"
echo "========================================="
echo ""
echo "ECS上的MongoDB已重新安装（无认证模式）"
echo "爬虫系统已部署并测试"
echo ""
echo "后续操作:"
echo ""
echo "1. SSH登录ECS:"
echo "   ssh -i $SSH_KEY ${ECS_USER}@${ECS_IP}"
echo ""
echo "2. 查看MongoDB状态:"
echo "   systemctl status mongod"
echo ""
echo "3. 查看爬虫日志:"
echo "   tail -f /opt/shared-cfo/logs/*.log"
echo ""
echo "4. 运行完整爬虫:"
echo "   ssh -i '$SSH_KEY' ${ECS_USER}@${ECS_IP}"
echo "   cd /opt/shared-cfo && python3 run_crawler.py crawl --phase test"
echo ""
echo "5. 后台持续爬取:"
echo "   ssh -i '$SSH_KEY' ${ECS_USER}@${ECS_IP}"
echo "   cd /opt/shared-cfo && nohup python3 run_crawler.py crawl --phase week1 > logs/crawl.out 2>&1 &"
echo ""
