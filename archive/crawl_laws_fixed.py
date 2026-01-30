#!/usr/bin/env python3
"""
多源法律和行政法规爬虫 v2
使用Playwright + requests混合模式
"""

import asyncio
import re
import logging
import requests
from datetime import datetime
from pymongo import MongoClient
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# MongoDB配置
MONGO_URI = 'mongodb://localhost:27017/'
MONGO_DB = 'shared_cfo'
MONGO_COLLECTION = 'policies'

# 目标法律
TARGET_LAWS = {
    '增值税法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20241225a5a9a09.shtml',
        'fallback_url': 'https://www.npc.gov.cn/npc/c2/20241225a5a9a09.shtml',
        'level': 'L1',
        'type': '法律',
        'tax_type': ['增值税'],
        'expected_title': '中华人民共和国增值税法',
    },
    '个人所得税法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20180831a48f9d9.shtml',
        'level': 'L1',
        'type': '法律',
        'tax_type': ['个人所得税'],
        'expected_title': '中华人民共和国个人所得税法',
    },
    '企业所得税法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20070316a0e510e.shtml',
        'level': 'L1',
        'type': '法律',
        'tax_type': ['企业所得税'],
        'expected_title': '中华人民共和国企业所得税法',
    },
    '税收征收管理法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20150427a4c7c2e.shtml',
        'level': 'L1',
        'type': '法律',
        'tax_type': ['税收征管'],
        'expected_title': '中华人民共和国税收征收管理法',
    },
}

# 目标行政法规
TARGET_REGULATIONS = {
    '增值税暂行条例': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2017-12/29/content_5343642.htm',
        'level': 'L2',
        'type': '行政法规',
        'tax_type': ['增值税'],
        'expected_title': '中华人民共和国增值税暂行条例',
    },
    '个人所得税法实施条例': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2018-12/22/content_5350262.htm',
        'level': 'L2',
        'type': '行政法规',
        'tax_type': ['个人所得税'],
        'expected_title': '中华人民共和国个人所得税法实施条例',
    },
    '企业所得税法实施条例': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2007-12/11/content_5279817.htm',
        'level': 'L2',
        'type': '行政法规',
        'tax_type': ['企业所得税'],
        'expected_title': '中华人民共和国企业所得税法实施条例',
    },
    '税收征收管理法实施细则': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2016-02/06/content_5031145.htm',
        'level': 'L2',
        'type': '行政法规',
        'tax_type': ['税收征管'],
        'expected_title': '中华人民共和国税收征收管理法实施细则',
    },
}


class MultiSourceLawsCrawlerV2:
    """多源法律爬虫 V2"""

    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB]
        self.collection = self.db[MONGO_COLLECTION]
        self.results = []

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # requests session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })

    def fetch_with_requests(self, url):
        """使用requests获取页面"""
        try:
            resp = self.session.get(url, timeout=30, verify=False)  # 忽略SSL验证
            resp.encoding = resp.apparent_encoding
            return resp.text
        except Exception as e:
            self.logger.error(f"requests获取失败: {e}")
            return None

    def extract_npc_content(self, html, title):
        """提取人大官网正文"""
        soup = BeautifulSoup(html, 'html.parser')

        # 尝试多种选择器
        selectors = [
            ('div', {'class': 'zwx3-box'}),
            ('div', {'class': 'content'}),
            ('div', {'id': 'content'}),
            ('article', {}),
            ('div', {'class': 'text'}),
        ]

        for tag, attrs in selectors:
            elem = soup.find(tag, attrs)
            if elem:
                text = elem.get_text(separator='\n', strip=True)
                if len(text) > 500:
                    return text

        # 备用：获取整个body
        return soup.get_text(separator='\n', strip=True)

    def extract_gov_content(self, html, title):
        """提取国务院官网正文"""
        soup = BeautifulSoup(html, 'html.parser')

        # 尝试多种选择器
        selectors = [
            ('div', {'class': 'content-text'}),
            ('div', {'class': 'article-content'}),
            ('div', {'id': 'content'}),
            ('div', {'class': 'text'}),
            ('article', {}),
        ]

        for tag, attrs in selectors:
            elem = soup.find(tag, attrs)
            if elem:
                text = elem.get_text(separator='\n', strip=True)
                if len(text) > 500:
                    return text

        # 尝试找包含"第一条"的div
        for div in soup.find_all('div'):
            text = div.get_text(separator='\n', strip=True)
            if '第一条' in text and len(text) > 500:
                return text

        return soup.get_text(separator='\n', strip=True)

    def crawl_npc_law_requests(self, name, info):
        """使用requests从人大官网爬取法律"""
        try:
            url = info['npc_url']
            self.logger.info(f"[人大/requests] 爬取: {name}")

            html = self.fetch_with_requests(url)
            if not html:
                return None

            content = self.extract_npc_content(html, info['expected_title'])

            if len(content) < 200:
                self.logger.warning(f"[人大] {name}: 内容过短 ({len(content)} 字符)")
                return None

            policy_id = f"NPC_{info['level']}_{name}_{datetime.now().strftime('%Y%m%d')}"

            policy_data = {
                'policy_id': policy_id,
                'title': info['expected_title'],
                'source': '全国人大',
                'url': url,
                'content': content,
                'document_level': info['level'],
                'document_type': info['type'],
                'tax_type': info['tax_type'],
                'region': '全国',
                'crawled_at': datetime.now(),
                'quality_score': 5,
                'crawl_source': 'npc',
            }

            self.logger.info(f"[人大] {name}: 成功 ({len(content)} 字符)")
            return policy_data

        except Exception as e:
            self.logger.error(f"[人大] {name}: 失败 - {e}")
            return None

    async def crawl_gov_regulation_playwright(self, name, info, browser):
        """使用Playwright从国务院官网爬取行政法规"""
        try:
            url = info['gov_url']
            self.logger.info(f"[国务院] 爬取: {name}")

            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)

            # 获取HTML
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # 提取正文
            content = self.extract_gov_content(html, info['expected_title'])

            await page.close()

            if len(content) < 200:
                self.logger.warning(f"[国务院] {name}: 内容过短 ({len(content)} 字符)")
                return None

            policy_id = f"GOV_{info['level']}_{name}_{datetime.now().strftime('%Y%m%d')}"

            policy_data = {
                'policy_id': policy_id,
                'title': info['expected_title'],
                'source': '国务院',
                'url': url,
                'content': content,
                'document_level': info['level'],
                'document_type': info['type'],
                'tax_type': info['tax_type'],
                'region': '全国',
                'crawled_at': datetime.now(),
                'quality_score': 5,
                'crawl_source': 'gov',
            }

            self.logger.info(f"[国务院] {name}: 成功 ({len(content)} 字符)")
            return policy_data

        except Exception as e:
            self.logger.error(f"[国务院] {name}: 失败 - {e}")
            return None

    def save_policy(self, policy_data):
        """保存政策到数据库"""
        self.collection.delete_many({'title': policy_data['title']})
        self.collection.insert_one(policy_data)

    async def crawl_all(self):
        """爬取所有目标法律和行政法规"""
        self.logger.info("=" * 60)
        self.logger.info("开始爬取法律和行政法规 (V2)")
        self.logger.info("=" * 60)

        # 爬取法律（使用requests）
        self.logger.info("\n>>> 第一部分：爬取法律（人大官网 + requests）")
        for name, info in TARGET_LAWS.items():
            policy = self.crawl_npc_law_requests(name, info)
            if policy:
                self.save_policy(policy)
                self.results.append({
                    'name': name,
                    'title': policy['title'],
                    'source': '全国人大',
                    'level': policy['document_level'],
                    'content_length': len(policy['content']),
                })

        # 爬取行政法规（使用Playwright）
        self.logger.info("\n>>> 第二部分：爬取行政法规（国务院官网 + Playwright）")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            for name, info in TARGET_REGULATIONS.items():
                policy = await self.crawl_gov_regulation_playwright(name, info, browser)
                if policy:
                    self.save_policy(policy)
                    self.results.append({
                        'name': name,
                        'title': policy['title'],
                        'source': '国务院',
                        'level': policy['document_level'],
                        'content_length': len(policy['content']),
                    })
                await asyncio.sleep(1)
            await browser.close()

        self.logger.info("\n" + "=" * 60)
        self.logger.info("爬取完成!")
        self.logger.info("=" * 60)

    def print_results(self):
        """打印结果统计"""
        print(f"\n📊 爬取结果:")
        print(f"成功: {len(self.results)} 条\n")

        for r in self.results:
            print(f"  • [{r['level']}] {r['name']}")
            print(f"    来源: {r['source']}")
            print(f"    内容长度: {r['content_length']} 字符")


async def main():
    """主函数"""
    crawler = MultiSourceLawsCrawlerV2()
    await crawler.crawl_all()
    crawler.print_results()


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    asyncio.run(main())
