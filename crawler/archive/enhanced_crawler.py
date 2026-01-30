#!/usr/bin/env python3
"""
升级版Playwright税务政策爬虫
支持层级识别、字段提取、质量评分
"""
import asyncio
import logging
import random
import time
from datetime import datetime
from urllib.parse import urljoin, quote_plus
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup

# 字段提取类和策略（内联版本）
import re
from datetime import datetime
from typing import Optional, List, Tuple
from enum import Enum


class EnhancedTaxCrawler:
    """增强版税务政策爬虫"""

    BASE_URL = "https://fgk.chinatax.gov.cn"

    # 爬取目标配置
    TARGET_SOURCES = {
        'chinatax': {
            'name': '国家税务总局政策法规库',
            'url': 'https://fgk.chinatax.gov.cn',
            'priority': 1,
            'max_policies': 100,
        },
    }

    def __init__(self):
        self.mongo_uri = f'mongodb://cfo_user:{quote_plus("840307@whY")}@localhost:27017/shared_cfo?authSource=admin'

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/opt/shared-cfo/logs/enhanced_crawler.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # 初始化字段提取器
        self.extractor = FieldExtractor()

        # 连接MongoDB
        self.logger.info('连接MongoDB...')
        self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=10000)
        self.db = self.client['shared_cfo']
        self.collection = self.db['policies']
        self.client.admin.command('ping')
        self.logger.info('MongoDB连接成功')

    async def delay(self, min_sec=2.0, max_sec=5.0):
        """异步延迟"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def crawl_chinatax(self, limit: int = 50) -> Dict[str, Any]:
        """爬取国家税务总局政策"""
        async with async_playwright() as p:
            self.logger.info('启动浏览器...')

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            page = await context.new_page()

            stats = {
                'total': 0,
                'success': 0,
                'duplicate': 0,
                'error': 0,
                'by_level': {},
                'by_quality': {}
            }

            try:
                # 访问主页
                self.logger.info(f'访问: {self.BASE_URL}')
                await page.goto(self.BASE_URL, wait_until='networkidle', timeout=60000)
                await self.delay(3, 6)

                # 获取所有政策链接
                self.logger.info('查找政策链接...')
                links = await page.query_selector_all('a')

                policies = []

                for link in links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.inner_text()

                        if not href or not text:
                            continue

                        text = text.strip()

                        # 过滤政策相关链接
                        if (len(text) > 10 and len(text) < 200 and
                            any(kw in text for kw in ['税', '政策', '公告', '通知', '增值税', '所得税', '所得', '法', '条例', '办法'])):

                            if not href.startswith('http'):
                                full_url = urljoin(self.BASE_URL, href)
                            else:
                                full_url = href

                            # 只收录站内链接
                            if 'chinatax.gov.cn' in full_url:
                                # 去重
                                if not any(p['url'] == full_url for p in policies):
                                    policies.append({
                                        'title': text[:100],
                                        'url': full_url
                                    })

                                    if len(policies) >= limit * 2:
                                        break

                    except Exception:
                        continue

                self.logger.info(f'找到 {len(policies)} 条政策链接')

                # 爬取详情
                for idx, policy in enumerate(policies[:limit], 1):
                    self.logger.info(f'[{idx}/{min(limit, len(policies))}] {policy["title"][:60]}')

                    result = await self.crawl_detail(page, policy['url'], policy['title'])

                    stats['total'] += 1
                    if result == 'success':
                        stats['success'] += 1
                    elif result == 'duplicate':
                        stats['duplicate'] += 1
                    else:
                        stats['error'] += 1

            finally:
                await browser.close()

        # 输出统计
        self.logger.info('=' * 50)
        self.logger.info(f'爬取完成 - 成功:{stats["success"]}, 重复:{stats["duplicate"]}, 失败:{stats["error"]}')
        self.logger.info(f'数据库总数: {self.collection.count_documents({})}')
        self.logger.info('=' * 50)

        return stats

    async def crawl_detail(self, page: Page, url: str, title: str = None) -> str:
        """爬取政策详情"""
        try:
            await self.delay(2, 4)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self.delay(1, 2)

            # 获取页面内容
            content_text = await page.inner_text('body')

            if not title:
                try:
                    title_elem = await page.query_selector('h1')
                    if title_elem:
                        title = await title_elem.inner_text()
                except:
                    title = url.split('/')[-1]

            # 使用字段提取器提取所有信息
            extracted = self.extractor.extract_all_fields(
                title=title,
                content=content_text,
                url=url,
                source='国家税务总局'
            )

            # 构造文档
            doc_id = f"chinatax_{int(time.time())}_{random.randint(1000, 9999)}"

            doc = {
                '_id': doc_id,
                'policy_id': extracted.get('document_number') or doc_id,

                # 基础信息
                'title': extracted.get('title'),
                'source': '国家税务总局',
                'url': url,

                # 层级与效力信息
                'policy_level': extracted.get('policy_level'),
                'document_number': extracted.get('document_number'),
                'issuing_authority': extracted.get('issuing_authority'),
                'authority_type': extracted.get('authority_type'),

                # 时效信息
                'publish_date': extracted.get('publish_date'),
                'effective_date': extracted.get('effective_date'),
                'expiry_date': extracted.get('expiry_date'),
                'validity_status': extracted.get('validity_status'),

                # 税种信息
                'tax_type': extracted.get('tax_type'),

                # 内容信息
                'content': content_text[:50000],
                'key_points': extracted.get('key_points'),

                # 元数据
                'document_type': extracted.get('document_type'),
                'region': '全国',
                'tags': [],

                # 质量信息
                'content_length': extracted.get('content_length'),
                'quality_score': extracted.get('quality_score'),
                'quality_level': extracted.get('quality_level'),

                # 爬取信息
                'crawled_at': datetime.now(),
                'crawl_source': 'chinatax',
            }

            # 保存到数据库
            self.collection.insert_one(doc)
            self.logger.info(f'✓ 保存成功 (层级: {extracted.get("policy_level")}, 质量: Lv{extracted.get("quality_level")}, 分数: {extracted.get("quality_score")})')
            return 'success'

        except Exception as e:
            error_str = str(e).lower()

            # 检查是否是重复错误
            if 'duplicate' in error_str or 'E11000' in error_str:
                return 'duplicate'

            self.logger.error(f'✗ 失败: {e}')
            return 'error'

    async def crawl(self, limit: int = 50) -> Dict[str, Any]:
        """主爬取方法"""
        self.logger.info('=' * 60)
        self.logger.info('增强版税务政策爬虫启动')
        self.logger.info('=' * 60)

        stats = await self.crawl_chinatax(limit)

        # 输出质量统计
        self._log_quality_stats()

        return stats

    def _log_quality_stats(self):
        """输出质量统计"""
        pipeline = [
            {'$group': {'level': '$policy_level'}},
            {'$count': {'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]

        level_counts = {}
        for doc in self.collection.aggregate(pipeline):
            level = doc.get('_id', 0)
            level_counts[f"Level {level}"] = doc['count']

        self.logger.info('层级分布:')
        for level, count in sorted(level_counts.items()):
            self.logger.info(f'  {level}: {count}条')

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


if __name__ == '__main__':
    import time

    crawler = EnhancedTaxCrawler()
    try:
        asyncio.run(crawler.crawl(limit=50))
    except KeyboardInterrupt:
        print('\n用户中断')
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        crawler.close()
        print('完成!')
