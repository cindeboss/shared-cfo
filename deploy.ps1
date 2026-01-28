# 共享CFO爬虫 - PowerShell自动化部署脚本
# 请在PowerShell中运行此脚本

$ServerIP = "120.78.5.4"
$Username = "root"
$Password = "840307@whY"

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "   共享CFO爬虫 - 自动部署" -ForegroundColor Yellow
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# 读取部署脚本内容
$deployScript = @'
#!/bin/bash
set -e

echo "=========================================="
echo "  共享CFO税务政策爬虫 - 自动部署"
echo "=========================================="

PROJECT_DIR="/opt/shared-cfo"
cd "$PROJECT_DIR"

echo "[1/6] 检查Python环境..."
python3 --version

echo ""
echo "[2/6] 检查MongoDB连接..."
python3 -c "
from pymongo import MongoClient
from urllib.parse import quote_plus

password = quote_plus('840307@whY')
mongo_uri = f'mongodb://root:{password}@dds-wz9acd31e6591e342.mongodb.rds.aliyuncs.com:3717,dds-wz9acd31e6591e341.mongodb.rds.aliyuncs.com:3717/admin?replicaSet=mgset-97608956'

print('连接MongoDB...')
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
client.admin.command('ping')
print('✓ MongoDB连接成功!')
"

echo ""
echo "[3/6] 创建爬虫代码..."
cat > "$PROJECT_DIR/crawler.py" << 'EOFPY'
#!/usr/bin/env python3
import requests, time, random, logging, re
from datetime import datetime
from pymongo import MongoClient
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

class TaxCrawler:
    def __init__(self):
        self.base_url = 'https://fgk.chinatax.gov.cn'
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

        password = quote_plus('840307@whY')
        mongo_uri = f'mongodb://root:{password}@dds-wz9acd31e6591e342.mongodb.rds.aliyuncs.com:3717,dds-wz9acd31e6591e341.mongodb.rds.aliyuncs.com:3717/admin?replicaSet=mgset-97608956'

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
            handlers=[logging.FileHandler('/opt/shared-cfo/logs/crawler.log'), logging.StreamHandler()])
        self.logger = logging.getLogger(__name__)
        self.logger.info('Connecting to MongoDB...')
        self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
        self.db = self.client['shared_cfo']
        self.collection = self.db['policies']
        self.client.admin.command('ping')
        self.logger.info('✓ MongoDB连接成功')

    def delay(self):
        time.sleep(random.uniform(2.0, 4.0))

    def crawl(self, limit=5):
        self.logger.info(f'开始爬取，目标: {limit}条')

        self.logger.info(f'访问主页查找政策链接...')
        self.delay()

        try:
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            policies = []

            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                title = link.get_text(strip=True)

                if not href or not title:
                    continue

                if any(kw in title for kw in ['政策', '公告', '通知', '税']):
                    if not href.startswith('http'):
                        full_url = urljoin(self.base_url, href)
                    else:
                        full_url = href

                    policies.append({'title': title, 'url': full_url})

            self.logger.info(f'找到 {len(policies)} 条政策链接')

            success = 0
            for idx, policy in enumerate(policies[:limit], 1):
                title = policy['title']
                url = policy['url']
                self.logger.info(f'[{idx}/{limit}] {title[:50]}')

                if self.crawl_detail(url, title) == 'success':
                    success += 1

            self.logger.info(f'完成 - 成功: {success}')
            return success

        except Exception as e:
            self.logger.error(f'爬取失败: {e}', exc_info=True)
            return 0

    def crawl_detail(self, url, title=None):
        try:
            self.delay()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            if not title:
                title_elem = soup.find('h1') or soup.find('title')
                title = title_elem.get_text(strip=True) if title_elem else url

            content_div = soup.find('div', class_='content') or soup.find('div', class_='article-content') or soup.find('body')
            content = content_div.get_text(separator='\n', strip=True) if content_div else ''

            policy_id = url.split('/')[-1].replace('.shtml', '').replace('.htm', '')

            doc = {
                'policy_id': policy_id,
                'title': title,
                'source': '国家税务总局',
                'url': url,
                'content': content[:50000],
                'crawled_at': datetime.now(),
                'region': '全国'
            }
            self.collection.insert_one(doc)
            self.logger.info(f'✓ 保存成功')
            return 'success'
        except Exception as e:
            if 'duplicate' in str(e).lower():
                return 'duplicate'
            self.logger.error(f'✗ 失败: {e}')
            return 'error'

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.info('=' * 40)
    logger.info('共享CFO税务政策爬虫')
    logger.info('=' * 40)
    crawler = TaxCrawler()
    count = crawler.crawl(limit=3)
    logger.info(f'数据库总数: {crawler.collection.count_documents({})}')
    logger.info('完成!')
EOFPY

chmod +x "$PROJECT_DIR/crawler.py"
echo "✓ 爬虫代码已创建"

echo ""
echo "[4/6] 运行爬虫..."
cd "$PROJECT_DIR"
source venv/bin/activate
python crawler.py

echo ""
echo "[5/6] 验证数据..."
python3 -c "
from pymongo import MongoClient
from urllib.parse import quote_plus

password = quote_plus('840307@whY')
mongo_uri = f'mongodb://root:{password}@dds-wz9acd31e6591e342.mongodb.rds.aliyuncs.com:3717,dds-wz9acd31e6591e341.mongodb.rds.aliyuncs.com:3717/admin?replicaSet=mgset-97608956'

client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
db = client['shared_cfo']

total = db['policies'].count_documents({})
print(f'数据库总文档数: {total}')

if total > 0:
    sample = db['policies'].find_one()
    print(f'示例文档标题: {sample.get(\"title\", \"N/A\")}')
    print(f'示例文档URL: {sample.get(\"url\", \"N/A\")}')
else:
    print('数据库暂无数据，请检查爬虫日志')

print('✓ 数据库检查完成')
"

echo ""
echo "=========================================="
echo "🎉 部署完成！"
echo ""
echo "查看日志: ssh $Username@$ServerIP 'tail -f /opt/shared-cfo/logs/crawler.log'"
echo "手动运行: ssh $Username@$ServerIP 'cd /opt/shared-cfo && source venv/bin/activate && python crawler.py'"
echo "=========================================="
'@

# 将脚本上传到服务器并执行
$createCommand = @"
cd /opt && cat > deploy.sh << 'EOSSH'
$deployScript
EOSSH

bash deploy.sh
"@

Write-Host "正在上传并执行部署脚本..." -ForegroundColor Yellow

# 使用sshpass执行（如果可用）或提示用户
try {
    $sshpass = Get-Command sshpass -ErrorAction SilentlyContinueContinue
    $sshCommandWithPassword = "echo $Password | ssh $Username@$ServerIP """ + $createCommand + """
"""

    # 尝试直接执行（需要用户已保存SSH密钥）
    $result = Invoke-Expression $sshCommandWithPassword 2>&1

    Write-Host $result

} catch {
    Write-Host "====================================" -ForegroundColor Red
    Write-Host "SSH自动化连接失败" -ForegroundColor Red
    Write-Host "====================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "请手动执行以下步骤：" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. 打开PowerShell/CMD，执行: ssh root@120.78.5.4" -ForegroundColor White
    Write-Host "2. 输入密码: 840307@whY" -ForegroundColor White
    Write-Host "3. 连接成功后，执行以下命令：" -ForegroundColor White
    Write-Host ""
    Write-Host "cd /opt && curl -fsSL https://raw.githubusercontent.com/cindeeman/notes/main/auto_deploy.sh -o deploy.sh && bash deploy.sh" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "或者直接复制粘贴脚本内容执行" -ForegroundColor Gray
    Write-Host ""
    Write-Host "====================================" -ForegroundColor Cyan
}
