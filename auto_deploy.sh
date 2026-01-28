#!/bin/bash
# 共享CFO爬虫自动部署脚本
# 在服务器上执行此脚本

set -e

echo "=========================================="
echo "  共享CFO税务政策爬虫 - 自动部署脚本"
echo "=========================================="
echo ""

PROJECT_DIR="/opt/shared-cfo"
cd "$PROJECT_DIR"

echo "[1/6] 检查Python环境..."
python3 --version

echo ""
echo "[2/6] 检查MongoDB连接..."
python3 << 'EOF'
from pymongo import MongoClient
from urllib.parse import quote_plus

password = quote_plus('840307@whY')
mongo_uri = f'mongodb://root:{password}@dds-wz9acd31e6591e342.mongodb.rds.aliyuncs.com:3717,dds-wz9acd31e6591e341.mongodb.rds.aliyuncs.com:3717/admin?replicaSet=mgset-97608956'

print('连接MongoDB...')
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
client.admin.command('ping')
print('✓ MongoDB连接成功!')
EOF

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

        # 尝试多种方式获取政策
        self.logger.info(f'访问主页查找政策链接...')
        self.delay()

        try:
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            policies = []

            # 查找政策相关链接
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                title = link.get_text(strip=True)

                if not href or not title:
                    continue

                # 过滤政策相关链接
                if any(kw in title for kw in ['政策', '公告', '通知', '税']):
                    if not href.startswith('http'):
                        full_url = urljoin(self.base_url, href)
                    else:
                        full_url = href

                    policies.append({'title': title, 'url': full_url})

            self.logger.info(f'找到 {len(policies)} 条政策链接')

            # 爬取前N条
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
                self.logger.debug(f'⊗ 重复: {url}')
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
echo "[4/6] 运行爬虫测试..."
cd "$PROJECT_DIR"
source venv/bin/activate
python crawler.py

echo ""
echo "[5/6] 查看数据库状态..."
python3 << 'EOF'
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

print('✓ 数据库检查完成')
EOF

echo ""
echo "[6/6] 部署完成！"
echo ""
echo "查看日志: tail -f $PROJECT_DIR/logs/crawler.log"
echo "手动运行: cd $PROJECT_DIR && source venv/bin/activate && python crawler.py"
echo ""
echo "=========================================="
