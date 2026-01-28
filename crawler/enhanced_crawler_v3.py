#!/usr/bin/env python3
"""
简化版增强爬虫
"""
import asyncio
import logging
import random
import time
import re
from datetime import datetime
from urllib.parse import quote_plus, urljoin

from pymongo import MongoClient
from playwright.async_api import async_playwright, Page

# ==================== 字段提取 ====================

def extract_document_number(text):
    patterns = [
        r'财[政关税]\s*〔\[]?\s*(\d{4})\s*\]?\s*号',
        r'税\s*总\s*发\s*〔\[]?\s*(\d{4})\s*\]?\s*号',
        r'国家税务总局公告\s*(\d{4})\s*年\s*第\s*(\d{1,3})\s*号',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            result = re.sub(r'\s+', '', match.group(0))
            return result.replace('〔', '[').replace('〕', ']')
    return None

def extract_dates(text):
    result = {'publish_date': None, 'effective_date': None, 'expiry_date': None, 'validity_status': 'unknown'}

    match = re.search(r'成文日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?', text)
    if match:
        try:
            year = int(match.group(1)); month = int(match.group(2)); day = int(match.group(3))
            result['publish_date'] = datetime(year, month, day)
        except: pass

    # 有效期
    match = re.search(r'执行期限[^。]*?(\d{4})[年\-](\d{1,2})[月\-]?\s*(\d{1,2})?日?', text)
    if match:
        try:
            year = int(match.group(1)); month = int(match.group(2)) if match.group(2) else 12
            result['expiry_date'] = datetime(year, month, day)
            result['validity_status'] = 'expired' if datetime(year, month, day) < datetime.now() else 'valid'
        except: pass

    return result

def determine_tax_type(title, content):
    tax_types = []
    combined = f"{title} {content}"
    if '增值税' in combined: tax_types.append('增值税')
    if '企业所得税' in combined or '企税' in combined: tax_types.append('企业所得税')
    if '个人所得税' in combined or '个税' in combined: tax_types.append('个人所得税')
    return tax_types if tax_types else ['其他']

def determine_level(title, content):
    if '中华人民共和国.*?法' in title and '全国人民代表大会' in content: return 1
    if '实施条例' in title and '国务院' in content: return 2
    if '管理办法' in title or '实施细则' in title: return 3
    if '解读' in title: return 5
    return 4

def calculate_quality_score(doc):
    score = 0
    if doc.get('document_number'): score += 10
    if doc.get('publish_date'): score += 10
    if len(doc.get('title', '')) > 20: score += 10
    if len(doc.get('content', '')) > 500: score += 20
    if len(doc.get('content', '')) > 1000: score += 10
    return min(score, 100)

# ==================== 爬虫类 ====================

class EnhancedCrawler:
    BASE_URL = "https://fgk.chinatax.gov.cn"

    def __init__(self):
        mongo_uri = f'mongodb://cfo_user:{quote_plus("840307@whY")}@localhost:27017/shared_cfo?authSource=admin'
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                        handlers=[logging.FileHandler('/opt/shared_cfo/logs/enhanced_crawler.log', encoding='utf-8')])
        self.logger = logging.getLogger(__name__)

        self.client = MongoClient(mongo_uri)
        self.db = self.client['shared_cfo']
        self.collection = self.db['policies']
        self.logger.info('MongoDB连接成功')

    async def crawl(self, limit=30):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                page = await browser.new_page()

                self.logger.info(f'访问: {self.BASE_URL}')
                await page.goto(self.BASE_URL, timeout=30000)
                await asyncio.sleep(3)

                # 获取链接
                links = await page.query_selector_all('a')
                policies = []

                for link in links[:100]:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.get_text()

                        if not href or not text or len(text) < 10:
                            continue

                        if '税' in text or '政策' in text or '公告' in text:
                            if not href.startswith('http'):
                                href = urljoin(self.BASE_URL, href)

                            if 'chinatax.gov.cn' in href:
                                policies.append({'title': text[:100], 'url': href})
                    except:
                        continue

                self.logger.info(f'找到 {len(policies)} 条政策链接')

                # 爬取详情
                success = 0
                for idx, policy in enumerate(policies[:limit], 1):
                    self.logger.info(f'[{idx}/{limit}] {policy["title"][:50]}')

                    try:
                        await page.goto(policy['url'], timeout=15000)
                        await asyncio.sleep(2)

                        content = await page.inner_text('body')

                        # 字段提取
                        doc_number = extract_document_number(content)
                        dates = extract_dates(content)
                        tax_types = determine_tax_type(policy['title'], content)
                        level = determine_level(policy['title'], content)
                        quality = calculate_quality_score({'title': policy['title'], 'content': content})

                        # 插入数据库
                        doc = {
                            'title': policy['title'],
                            'source': '国家税务总局',
                            'url': policy['url'],
                            'content': content[:50000],
                            'policy_level': level,
                            'document_number': doc_number,
                            'publish_date': dates.get('publish_date'),
                            'tax_type': tax_types,
                            'quality_score': quality,
                            'crawled_at': datetime.now(),
                            'region': '全国',
                            'validity_status': dates.get('validity_status'),
                        }

                        self.collection.insert_one(doc)
                        self.logger.info(f'✓ 保存成功 (层级:{level}, 质量:{quality})')
                        success += 1

                    except Exception as e:
                        if 'duplicate' in str(e):
                            self.logger.info('⊗ 重复')
                        else:
                            self.logger.error(f'✗ 失败: {e}')

                self.logger.info(f'完成 - 成功:{success}')
                self.logger.info(f'数据库总数: {self.collection.count_documents({})}')

            finally:
                await browser.close()

        return {'success': success}

if __name__ == '__main__':
    crawler = EnhancedCrawler()
    import asyncio
    try:
        result = asyncio.run(crawler.crawl(30))
        print(f\"完成! 成功爬取{result['success']}条\")
    except Exception as e:
        print(f'错误: {e}')
    finally:
        crawler.client.close()
        print('完成!')
