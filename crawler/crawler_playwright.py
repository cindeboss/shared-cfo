#!/usr/bin/env python3
"""
使用Playwright的税务政策爬虫
可以绕过大多数反爬虫机制
"""
import asyncio
import logging
import random
import time
from datetime import datetime
from urllib.parse import urljoin, quote_plus

from pymongo import MongoClient
from playwright.async_api import async_playwright, Browser
from bs4 import BeautifulSoup


class PlaywrightTaxCrawler:
    """使用Playwright的爬虫"""

    def __init__(self):
        self.mongo_uri = f'mongodb://cfo_user:{quote_plus("840307@whY")}@localhost:27017/shared_cfo?authSource=admin'

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/opt/shared-cfo/logs/crawler_playwright.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # 连接MongoDB
        self.logger.info('连接MongoDB...')
        self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=10000)
        self.db = self.client['shared_cfo']
        self.collection = self.db['policies']
        self.client.admin.command('ping')
        self.logger.info('MongoDB连接成功')

    async def delay(self, min_sec=2, max_sec=5):
        """异步延迟"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def crawl_chinatax(self, limit=20):
        """爬取国家税务总局"""
        async with async_playwright() as p:
            self.logger.info('启动浏览器...')

            # 使用更真实的浏览器配置
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

            all_policies = []

            try:
                # 访问主页
                self.logger.info('访问国家税务总局...')
                await page.goto('https://fgk.chinatax.gov.cn', wait_until='networkidle', timeout=60000)
                await self.delay(3, 6)

                # 查找所有链接
                self.logger.info('查找政策链接...')

                links = await page.query_selector_all('a')
                self.logger.info(f'页面共有 {len(links)} 个链接')

                for link in links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.inner_text()

                        if not href or not text:
                            continue

                        text = text.strip()

                        # 过滤政策链接
                        if (len(text) > 10 and len(text) < 200 and
                            any(kw in text for kw in ['税', '政策', '公告', '通知', '增值税', '所得税', '所得'])):

                            # 构造完整URL
                            if not href.startswith('http'):
                                full_url = urljoin('https://fgk.chinatax.gov.cn', href)
                            else:
                                full_url = href

                            # 只收录站内链接
                            if 'chinatax.gov.cn' in full_url:
                                # 去重
                                if not any(p['url'] == full_url for p in all_policies):
                                    all_policies.append({
                                        'title': text[:100],
                                        'url': full_url
                                    })

                                    if len(all_policies) >= limit:
                                        break

                    except Exception as e:
                        continue

                self.logger.info(f'找到 {len(all_policies)} 条政策链接')

                # 爬取详情
                success = duplicate = error = 0

                for idx, policy in enumerate(all_policies[:limit], 1):
                    self.logger.info(f'[{idx}/{min(limit, len(all_policies))}] {policy["title"][:50]}')

                    result = await self.crawl_detail(page, policy['url'], policy['title'])
                    if result == 'success':
                        success += 1
                    elif result == 'duplicate':
                        duplicate += 1
                    else:
                        error += 1

                self.logger.info(f'完成 - 成功:{success}, 重复:{duplicate}, 失败:{error}')

            finally:
                await browser.close()

            return success

    async def crawl_detail(self, page, url, title=None):
        """爬取详情页"""
        try:
            await self.delay(2, 4)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self.delay(1, 2)

            # 获取页面内容
            content = await page.inner_text('body')

            if not title:
                try:
                    title_elem = await page.query_selector('h1')
                    if title_elem:
                        title = await title_elem.inner_text()
                except:
                    title = url.split('/')[-1]

            # 清理内容
            lines = [line.strip() for line in content.split('\n') if line.strip() and len(line) > 5]
            content = '\n'.join(lines[:500])  # 限制行数

            # 生成ID
            policy_id = url.split('/')[-1].replace('.shtml', '').replace('.htm', '')

            # 检测税种
            tax_types = []
            full_text = title + content
            if '增值税' in full_text:
                tax_types.append('增值税')
            if '企业所得税' in full_text or '企业所得税' in title:
                tax_types.append('企业所得税')
            if '个人所得税' in full_text or '个税' in full_text:
                tax_types.append('个人所得税')

            # 构造文档
            doc = {
                'policy_id': policy_id or f"doc_{int(time.time())}",
                'title': title.strip() if title else '未知标题',
                'source': '国家税务总局',
                'url': url,
                'content': content[:50000],
                'crawled_at': datetime.now(),
                'region': '全国',
                'document_type': '政策',
                'tax_type': tax_types if tax_types else ['其他'],
            }

            self.collection.insert_one(doc)
            self.logger.info(f'✓ 保存成功')
            return 'success'

        except Exception as e:
            if 'duplicate' in str(e).lower() or 'E11000' in str(e):
                return 'duplicate'
            self.logger.error(f'✗ 失败: {e}')
            return 'error'

    async def crawl_local_bureaus(self, limit=15):
        """爬取地方税务局"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()

            # 各地方税务局URL
            bureau_urls = [
                ('北京', 'http://beijing.chinatax.gov.cn/bjswj/sszc/zcjd/'),
                ('上海', 'https://shanghai.chinatax.gov.cn/zcfw/zcjd/'),
            ]

            all_policies = []
            success = 0

            for region, url in bureau_urls:
                try:
                    self.logger.info(f'访问{region}税务: {url}')
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await self.delay(2, 4)

                    # 查找政策链接
                    links = await page.query_selector_all('a')

                    for link in links[:30]:  # 限制检查数量
                        try:
                            href = await link.get_attribute('href')
                            text = await link.inner_text()

                            if not href or not text or len(text) < 8:
                                continue

                            if any(kw in text for kw in ['税', '政策', '公告', '通知']):
                                if not href.startswith('http'):
                                    full_url = urljoin(url, href)
                                else:
                                    full_url = href

                                if not any(p['url'] == full_url for p in all_policies):
                                    all_policies.append({
                                        'title': text[:100],
                                        'url': full_url,
                                        'region': region
                                    })

                                    if len(all_policies) >= limit:
                                        break

                        except:
                            continue

                    if len(all_policies) >= limit:
                        break

                except Exception as e:
                    self.logger.warning(f'访问{region}税务失败: {e}')

            self.logger.info(f'找到 {len(all_policies)} 条地方政策')

            # 爬取详情
            for idx, policy in enumerate(all_policies[:limit], 1):
                self.logger.info(f'[{idx}/{min(limit, len(all_policies))}] {policy["title"][:50]}')

                result = await self.crawl_detail_local(page, policy['url'], policy['title'], policy['region'])
                if result == 'success':
                    success += 1

            await browser.close()
            return success

    async def crawl_detail_local(self, page, url, title, region):
        """爬取地方政策详情"""
        try:
            await self.delay(1, 3)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            content = await page.inner_text('body')
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            content = '\n'.join(lines[:300])

            policy_id = url.split('/')[-1].replace('.shtml', '').replace('.htm', '')

            doc = {
                'policy_id': policy_id or f"local_{int(time.time())}",
                'title': title,
                'source': f'{region}税务局',
                'url': url,
                'content': content[:50000],
                'crawled_at': datetime.now(),
                'region': region,
                'document_type': '政策',
                'tax_type': ['其他'],
            }

            self.collection.insert_one(doc)
            self.logger.info(f'✓ 保存成功')
            return 'success'

        except Exception as e:
            if 'duplicate' in str(e).lower():
                return 'duplicate'
            return 'error'

    async def crawl(self, limit=30):
        """主爬取方法"""
        self.logger.info('=' * 50)
        self.logger.info('Playwright爬虫启动')
        self.logger.info('=' * 50)

        # 爬取总局
        count1 = await self.crawl_chinatax(limit)

        # 爬取地方
        count2 = await self.crawl_local_bureaus(limit // 2)

        total = count1 + count2
        self.logger.info(f'数据库总数: {self.collection.count_documents({})}')
        self.logger.info(f'本次爬取: {total} 条')
        self.logger.info('=' * 50)

        return total

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


if __name__ == '__main__':
    crawler = PlaywrightTaxCrawler()
    try:
        asyncio.run(crawler.crawl(limit=30))
    except KeyboardInterrupt:
        print('\n用户中断')
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        crawler.close()
        print('完成!')
