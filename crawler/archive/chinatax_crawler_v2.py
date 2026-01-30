#!/usr/bin/env python3
"""
国家税务总局政策爬虫 - 使用Playwright处理动态页面
"""
import asyncio
import logging
import random
import time
from datetime import datetime
from urllib.parse import urljoin

from pymongo import MongoClient
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright未安装，将使用requests作为备用方案")

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TaxCrawler:
    def __init__(self):
        self.base_url = 'https://fgk.chinatax.gov.cn'
        self.mongo_uri = f'mongodb://cfo_user:{quote_plus("840307@whY")}@localhost:27017/shared_cfo?authSource=admin'

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/opt/shared-cfo/logs/crawler.log', encoding='utf-8'),
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

        # 配置requests会话
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def delay(self, min_sec=2.0, max_sec=5.0):
        """随机延迟"""
        time.sleep(random.uniform(min_sec, max_sec))

    def crawl_with_playwright(self, limit=10):
        """使用Playwright爬取"""
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.warning("Playwright不可用，使用requests方法")
            return self.crawl_with_requests(limit)

        async def _crawl():
            async with async_playwright() as p:
                # 启动浏览器
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                policies_found = []
                success = duplicate = error = 0

                try:
                    # 访问主页
                    self.logger.info(f'访问: {self.base_url}')
                    await page.goto(self.base_url, wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(random.uniform(2, 4))

                    # 查找政策链接
                    self.logger.info('查找政策链接...')

                    # 等待页面加载
                    await page.wait_for_selector('a', timeout=10000)

                    # 获取所有链接
                    links = await page.query_selector_all('a')

                    for link in links[:50]:  # 限制检查数量
                        try:
                            href = await link.get_attribute('href')
                            text = await link.inner_text()

                            if not href or not text:
                                continue

                            # 过滤政策相关链接
                            text_clean = text.strip()
                            if (any(kw in text_clean for kw in ['税', '政策', '公告', '通知', '增值税', '所得税', '个人所得税']) and
                                ('.shtml' in href or '.htm' in href)):

                                # 构造完整URL
                                if not href.startswith('http'):
                                    full_url = urljoin(self.base_url, href)
                                else:
                                    full_url = href

                                policies_found.append({
                                    'title': text_clean[:100],
                                    'url': full_url
                                })

                                if len(policies_found) >= limit * 2:  # 多获取一些
                                    break

                        except Exception as e:
                            continue

                    self.logger.info(f'找到 {len(policies_found)} 条政策链接')

                    # 爬取详情
                    for idx, policy in enumerate(policies_found[:limit], 1):
                        self.logger.info(f'[{idx}/{limit}] {policy["title"][:50]}')
                        self.delay(2, 4)

                        result = await self.crawl_detail_with_playwright(page, policy['url'], policy['title'])
                        if result == 'success':
                            success += 1
                        elif result == 'duplicate':
                            duplicate += 1
                        else:
                            error += 1

                finally:
                    await browser.close()

                self.logger.info(f'完成 - 成功:{success}, 重复:{duplicate}, 失败:{error}')
                return success

        return asyncio.run(_crawl())

    def crawl_with_requests(self, limit=10):
        """使用requests爬取（备用方案）"""
        self.logger.info('使用requests方法爬取...')

        # 尝试多个可能的列表页
        list_pages = [
            'https://fgk.chinatax.gov.cn/',
            'https://fgk.chinatax.gov.cn/zcfgk/c100006/',
        ]

        all_policies = []

        for page_url in list_pages:
            self.logger.info(f'访问: {page_url}')
            self.delay()

            try:
                response = self.session.get(page_url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找所有链接
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    title = link.get_text(strip=True)

                    if not href or not title:
                        continue

                    # 过滤条件
                    if (any(kw in title for kw in ['税', '政策', '公告', '通知', '增值税', '所得税', '所得']) and
                        ('.shtml' in href or '.htm' in href or '/zcfgk/' in href)):

                        if not href.startswith('http'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href

                        # 去重
                        if not any(p['url'] == full_url for p in all_policies):
                            all_policies.append({'title': title[:100], 'url': full_url})

                            if len(all_policies) >= limit * 2:
                                break

                if len(all_policies) >= limit:
                    break

            except Exception as e:
                self.logger.warning(f'访问 {page_url} 失败: {e}')

        self.logger.info(f'找到 {len(all_policies)} 条政策链接')

        # 爬取详情
        success = duplicate = error = 0
        for idx, policy in enumerate(all_policies[:limit], 1):
            self.logger.info(f'[{idx}/{limit}] {policy["title"][:50]}')
            result = self.crawl_detail(policy['url'], policy['title'])
            if result == 'success':
                success += 1
            elif result == 'duplicate':
                duplicate += 1
            else:
                error += 1

        self.logger.info(f'完成 - 成功:{success}, 重复:{duplicate}, 失败:{error}')
        return success

    async def crawl_detail_with_playwright(self, page, url, title=None):
        """使用Playwright爬取详情页"""
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(1, 2))

            # 获取页面内容
            content = await page.inner_text('body')

            if not title:
                try:
                    title_elem = await page.query_selector('h1')
                    if title_elem:
                        title = await title_elem.inner_text()
                except:
                    title = url.split('/')[-1]

            # 构造文档
            policy_id = url.split('/')[-1].replace('.shtml', '').replace('.htm', '')
            doc = {
                'policy_id': policy_id,
                'title': title.strip() if title else 'Unknown',
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

    def crawl_detail(self, url, title=None):
        """使用requests爬取详情页"""
        try:
            self.delay(1, 3)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            if not title:
                title_elem = soup.find('h1') or soup.find('title')
                title = title_elem.get_text(strip=True) if title_elem else url.split('/')[-1]

            # 尝试多种内容提取方式
            content_div = (
                soup.find('div', class_='content') or
                soup.find('div', class_='article-content') or
                soup.find('div', id='content') or
                soup.find('div', class_='txt') or
                soup.find('article')
            )

            if content_div:
                content = content_div.get_text(separator='\n', strip=True)
            else:
                # 备用：获取body内容
                content = soup.get_text(separator='\n', strip=True)

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
            if 'duplicate' in str(e).lower() or 'E11000' in str(e):
                return 'duplicate'
            self.logger.error(f'✗ 失败: {e}')
            return 'error'

    def crawl(self, limit=10, use_playwright=True):
        """主爬取方法"""
        self.logger.info('=' * 50)
        self.logger.info('共享CFO税务政策爬虫启动')
        self.logger.info('=' * 50)

        if use_playwright and PLAYWRIGHT_AVAILABLE:
            return self.crawl_with_playwright(limit)
        else:
            return self.crawl_with_requests(limit)

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


if __name__ == '__main__':
    crawler = None
    try:
        crawler = TaxCrawler()
        count = crawler.crawl(limit=10, use_playwright=False)  # 先用requests
        print(f'\n数据库总数: {crawler.collection.count_documents({})}')
    except KeyboardInterrupt:
        print('\n用户中断')
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if crawler:
            crawler.close()
        print('完成!')
