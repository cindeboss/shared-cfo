#!/usr/bin/env python3
"""
多源法律和行政法规爬虫
绕过WAF拦截，从多个权威源获取法律原文

数据源优先级：
1. 全国人大官网 (npc.gov.cn) - 法律
2. 国务院官网 (gov.cn) - 行政法规
3. 国家税务总局 - 备用
"""

import asyncio
import re
import logging
from datetime import datetime
from pymongo import MongoClient
from playwright.async_api import async_playwright

# MongoDB配置
MONGO_URI = 'mongodb://localhost:27017/'
MONGO_DB = 'shared_cfo'
MONGO_COLLECTION = 'policies'

# 目标法律列表（全国人大官网URL）
TARGET_LAWS = {
    '增值税法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20241225a5a9a09.shtml',
        'level': 'L1',
        'type': '法律',
        'category': '实体税',
        'tax_type': ['增值税'],
        'expected_title': '中华人民共和国增值税法',
    },
    '个人所得税法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20180831a48f9d9.shtml',
        'level': 'L1',
        'type': '法律',
        'category': '实体税',
        'tax_type': ['个人所得税'],
        'expected_title': '中华人民共和国个人所得税法',
    },
    '企业所得税法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20070316a0e510e.shtml',
        'level': 'L1',
        'type': '法律',
        'category': '实体税',
        'tax_type': ['企业所得税'],
        'expected_title': '中华人民共和国企业所得税法',
    },
    '税收征收管理法': {
        'npc_url': 'https://www.npc.gov.cn/npc/c234/20150427a4c7c2e.shtml',
        'level': 'L1',
        'type': '法律',
        'category': '程序税',
        'tax_type': ['税收征管'],
        'expected_title': '中华人民共和国税收征收管理法',
    },
}

# 目标行政法规（国务院官网URL）
TARGET_REGULATIONS = {
    '增值税暂行条例': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2017-12/29/content_5343642.htm',
        'level': 'L2',
        'type': '行政法规',
        'category': '实体税',
        'tax_type': ['增值税'],
        'expected_title': '中华人民共和国增值税暂行条例',
    },
    '个人所得税法实施条例': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2018-12/22/content_5350262.htm',
        'level': 'L2',
        'type': '行政法规',
        'category': '实体税',
        'tax_type': ['个人所得税'],
        'expected_title': '中华人民共和国个人所得税法实施条例',
    },
    '企业所得税法实施条例': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2007-12/11/content_5279817.htm',
        'level': 'L2',
        'type': '行政法规',
        'category': '实体税',
        'tax_type': ['企业所得税'],
        'expected_title': '中华人民共和国企业所得税法实施条例',
    },
    '税收征收管理法实施细则': {
        'gov_url': 'https://www.gov.cn/zhengce/content/2016-02/06/content_5031145.htm',
        'level': 'L2',
        'type': '行政法规',
        'category': '程序税',
        'tax_type': ['税收征管'],
        'expected_title': '中华人民共和国税收征收管理法实施细则',
    },
}


class MultiSourceLawsCrawler:
    """多源法律爬虫"""

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

    def extract_fields(self, title, content):
        """提取政策字段"""
        # 提取发文字号
        document_number = None
        patterns = [
            r'主席令[第第]?(\d+)号',
            r'国务院令[第第]?(\d+)号',
        ]
        for pattern in patterns:
            match = re.search(pattern, content[:500])
            if match:
                document_number = match.group(0)
                break

        # 提取发布日期
        publish_date = None
        date_patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, content[:1000])
            if match:
                publish_date = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                break

        # 提取生效日期
        effective_date = None
        eff_patterns = [
            r'自(\d{4})年(\d{1,2})月(\d{1,2})日起施行',
            r'自(\d{4})-(\d{1,2})-(\d{1,2})起施行',
            r'(\d{4})年(\d{1,2})月(\d{1,2})日起施行',
        ]
        for pattern in eff_patterns:
            match = re.search(pattern, content)
            if match:
                effective_date = f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                break

        return {
            'document_number': document_number,
            'publish_date': publish_date,
            'effective_date': effective_date,
        }

    async def crawl_npc_law(self, name, info, browser):
        """从全国人大官网爬取法律"""
        try:
            url = info['npc_url']
            self.logger.info(f"[人大] 爬取: {name} -> {url}")

            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)

            # 获取页面内容
            content = ''
            selectors = [
                '.zwx3-box',      # 人大官网正文
                '.content',
                '.article-content',
                'article',
            ]

            for selector in selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        content = await elem.inner_text()
                        if len(content) > 500:
                            break
                except:
                    continue

            if not content:
                content = await page.inner_text('body')

            await page.close()

            if len(content) < 200:
                self.logger.warning(f"[人大] {name}: 内容过短 ({len(content)} 字符)")
                return None

            title = info['expected_title']
            fields = self.extract_fields(title, content)
            policy_id = f"NPC_{info['level']}_{name}_{datetime.now().strftime('%Y%m%d')}"

            policy_data = {
                'policy_id': policy_id,
                'title': title,
                'source': '全国人大',
                'url': url,
                'content': content,
                'document_level': info['level'],
                'document_type': info['type'],
                'tax_category': info['category'],
                'tax_type': info['tax_type'],
                'region': '全国',
                'publish_date': fields['publish_date'],
                'document_number': fields['document_number'],
                'effective_date': fields['effective_date'],
                'crawled_at': datetime.now(),
                'quality_score': 5,
                'crawl_source': 'npc',
            }

            self.logger.info(f"[人大] {name}: 成功 ({len(content)} 字符)")
            return policy_data

        except Exception as e:
            self.logger.error(f"[人大] {name}: 失败 - {e}")
            return None

    async def crawl_gov_regulation(self, name, info, browser):
        """从国务院官网爬取行政法规"""
        try:
            url = info['gov_url']
            self.logger.info(f"[国务院] 爬取: {name} -> {url}")

            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)

            # 获取页面内容
            content = ''
            selectors = [
                '.content-text',       # 国务院官网正文
                '.article-content',
                '.content',
                '.texts',
                'article',
            ]

            for selector in selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        content = await elem.inner_text()
                        if len(content) > 500:
                            break
                except:
                    continue

            if not content:
                content = await page.inner_text('body')

            await page.close()

            if len(content) < 200:
                self.logger.warning(f"[国务院] {name}: 内容过短 ({len(content)} 字符)")
                return None

            title = info['expected_title']
            fields = self.extract_fields(title, content)
            policy_id = f"GOV_{info['level']}_{name}_{datetime.now().strftime('%Y%m%d')}"

            policy_data = {
                'policy_id': policy_id,
                'title': title,
                'source': '国务院',
                'url': url,
                'content': content,
                'document_level': info['level'],
                'document_type': info['type'],
                'tax_category': info['category'],
                'tax_type': info['tax_type'],
                'region': '全国',
                'publish_date': fields['publish_date'],
                'document_number': fields['document_number'],
                'effective_date': fields['effective_date'],
                'crawled_at': datetime.now(),
                'quality_score': 5,
                'crawl_source': 'gov',
            }

            self.logger.info(f"[国务院] {name}: 成功 ({len(content)} 字符)")
            return policy_data

        except Exception as e:
            self.logger.error(f"[国务院] {name}: 失败 - {e}")
            return None

    async def crawl_all(self):
        """爬取所有目标法律和行政法规"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            self.logger.info("=" * 60)
            self.logger.info("开始爬取法律和行政法规（多源）")
            self.logger.info("=" * 60)

            # 爬取法律（全国人大）
            self.logger.info("\n>>> 第一部分：爬取法律（全国人大官网）")
            for name, info in TARGET_LAWS.items():
                policy = await self.crawl_npc_law(name, info, browser)
                if policy:
                    self.save_policy(policy)
                    self.results.append({
                        'name': name,
                        'title': policy['title'],
                        'source': '全国人大',
                        'level': policy['document_level'],
                        'content_length': len(policy['content']),
                    })
                await asyncio.sleep(2)  # 延迟

            # 爬取行政法规（国务院）
            self.logger.info("\n>>> 第二部分：爬取行政法规（国务院官网）")
            for name, info in TARGET_REGULATIONS.items():
                policy = await self.crawl_gov_regulation(name, info, browser)
                if policy:
                    self.save_policy(policy)
                    self.results.append({
                        'name': name,
                        'title': policy['title'],
                        'source': '国务院',
                        'level': policy['document_level'],
                        'content_length': len(policy['content']),
                    })
                await asyncio.sleep(2)  # 延迟

            await browser.close()

        self.logger.info("\n" + "=" * 60)
        self.logger.info("爬取完成!")
        self.logger.info("=" * 60)

    def save_policy(self, policy_data):
        """保存政策到数据库"""
        # 先删除同名的旧数据（避免重复）
        self.collection.delete_many({'title': policy_data['title']})
        # 插入新数据
        self.collection.insert_one(policy_data)

    def print_results(self):
        """打印结果统计"""
        print(f"\n📊 爬取结果:")
        print(f"成功: {len(self.results)} 条")

        for r in self.results:
            print(f"  • [{r['level']}] {r['name']}")
            print(f"    来源: {r['source']}")
            print(f"    内容长度: {r['content_length']} 字符")


async def main():
    """主函数"""
    crawler = MultiSourceLawsCrawler()
    await crawler.crawl_all()
    crawler.print_results()


if __name__ == '__main__':
    asyncio.run(main())
