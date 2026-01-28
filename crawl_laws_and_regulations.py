#!/usr/bin/env python3
"""
共享CFO - 法律和行政法规爬虫
爬取实体法、程序法及相关行政法规
"""

import asyncio
import re
import os
from datetime import datetime
from pymongo import MongoClient
from playwright.async_api import async_playwright

# MongoDB配置
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB = 'shared_cfo'
MONGO_COLLECTION = 'policies'

# 目标法律和行政法规列表
TARGET_LAWS = {
    # === 实体法 ===
    '增值税法': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20241225165742856',
        'level': 'L1',
        'category': '实体税',
        'tax_type': ['增值税'],
        'expected_title': '中华人民共和国增值税法'
    },
    '个人所得税法': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20180831192857515',
        'level': 'L1',
        'category': '实体税',
        'tax_type': ['个人所得税'],
        'expected_title': '中华人民共和国个人所得税法'
    },
    '企业所得税法': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20070316173633701',
        'level': 'L1',
        'category': '实体税',
        'tax_type': ['企业所得税'],
        'expected_title': '中华人民共和国企业所得税法'
    },
    '税收征收管理法': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20150427142125701',
        'level': 'L1',
        'category': '程序税',
        'tax_type': ['税收征管'],
        'expected_title': '中华人民共和国税收征收管理法'
    },

    # === 行政法规（实施条例） ===
    '增值税法实施条例': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20171030182632700',
        'level': 'L2',
        'category': '实体税',
        'tax_type': ['增值税'],
        'expected_title': '中华人民共和国增值税暂行条例'
    },
    '个人所得税法实施条例': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20181220173530700',
        'level': 'L2',
        'category': '实体税',
        'tax_type': ['个人所得税'],
        'expected_title': '中华人民共和国个人所得税法实施条例'
    },
    '企业所得税法实施条例': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20071130152133700',
        'level': 'L2',
        'category': '实体税',
        'tax_type': ['企业所得税'],
        'expected_title': '中华人民共和国企业所得税法实施条例'
    },
    '税收征收管理法实施细则': {
        'url': 'https://fgk.chinatax.gov.cn/api/rest/v1/zcfgk/detail?code=20160210165243700',
        'level': 'L2',
        'category': '程序税',
        'tax_type': ['税收征管'],
        'expected_title': '中华人民共和国税收征收管理法实施细则'
    },
}

# 备用页面URL（如果API不可用）
FALLBACK_URLS = {
    '增值税法': 'https://www.npc.gov.cn/npc/c234/20241225a5a9a09.shtml',
    '个人所得税法': 'https://www.npc.gov.cn/npc/c234/20180831a48f9d9.shtml',
    '企业所得税法': 'https://www.npc.gov.cn/npc/c234/20070316a0e510e.shtml',
    '税收征收管理法': 'https://www.npc.gov.cn/npc/c234/20150427a4c7c2e.shtml',
}


class LawsCrawler:
    """法律和行政法规爬虫"""

    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB]
        self.collection = self.db[MONGO_COLLECTION]
        self.results = []

    def extract_fields(self, title, content, url):
        """提取政策字段"""
        # 提取发文字号
        document_number = None
        patterns = [
            r'主席令[第第](\d+)号',
            r'国务院令[第第](\d+)号',
            r'(财税|税总)[\u3000\s]{0,5}[〔\(]\d{4}[〕\)]\d{1,3}号',
            r'国家税务总局公告\d{4}年第\d+号',
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

    async def crawl_from_api(self, name, info, browser):
        """从API爬取"""
        try:
            page = await browser.new_page()
            await page.goto(info['url'], wait_until='networkidle', timeout=30000)

            # 等待内容加载
            await asyncio.sleep(2)

            content = await page.content()

            # 提取正文内容
            title = info['expected_title']

            # 尝试多种方式提取正文
            body_content = ''
            selectors = [
                '.content-body',
                '.article-content',
                '.detail-content',
                'body',
            ]

            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        body_content = await element.inner_text()
                        if len(body_content) > 500:
                            break
                except:
                    continue

            if not body_content or len(body_content) < 100:
                body_content = await page.inner_text('body')

            await page.close()

            if len(body_content) < 100:
                print(f"  ⚠️  {name}: 内容过短，跳过")
                return None

            # 提取字段
            fields = self.extract_fields(title, body_content, info['url'])

            # 生成policy_id
            policy_id = f"LAW_{info['level']}_{name}_{datetime.now().strftime('%Y%m%d')}"

            policy_data = {
                'policy_id': policy_id,
                'title': title,
                'source': '国家税务总局' if 'chinatax.gov.cn' in info['url'] else '全国人大',
                'url': info['url'],
                'content': body_content,
                'document_level': info['level'],
                'document_type': '法律' if info['level'] == 'L1' else '行政法规',
                'tax_category': info['category'],
                'tax_type': info['tax_type'],
                'region': '全国',
                'publish_date': fields['publish_date'],
                'document_number': fields['document_number'],
                'effective_date': fields['effective_date'],
                'crawled_at': datetime.now(),
                'quality_score': 5,  # 法律和行政法规质量最高
            }

            return policy_data

        except Exception as e:
            print(f"  ❌ API爬取失败 {name}: {e}")
            return None

    async def crawl_from_npc(self, name, url, info, browser):
        """从全国人大官网爬取"""
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)

            # 人大官网正文提取
            body_content = ''
            selectors = [
                '.zwx3-box',
                '.content',
                'article',
            ]

            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        body_content = await element.inner_text()
                        if len(body_content) > 500:
                            break
                except:
                    continue

            await page.close()

            if not body_content or len(body_content) < 100:
                return None

            title = info['expected_title']
            fields = self.extract_fields(title, body_content, url)
            policy_id = f"LAW_{info['level']}_{name}_{datetime.now().strftime('%Y%m%d')}"

            policy_data = {
                'policy_id': policy_id,
                'title': title,
                'source': '全国人大',
                'url': url,
                'content': body_content,
                'document_level': info['level'],
                'document_type': '法律',
                'tax_category': info['category'],
                'tax_type': info['tax_type'],
                'region': '全国',
                'publish_date': fields['publish_date'],
                'document_number': fields['document_number'],
                'effective_date': fields['effective_date'],
                'crawled_at': datetime.now(),
                'quality_score': 5,
            }

            return policy_data

        except Exception as e:
            print(f"  ❌ 人大官网爬取失败 {name}: {e}")
            return None

    async def crawl_all(self):
        """爬取所有目标法律"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            print("=" * 60)
            print("开始爬取法律和行政法规")
            print("=" * 60)

            for name, info in TARGET_LAWS.items():
                print(f"\n📋 正在爬取: {name}")

                # 首先尝试API
                policy = await self.crawl_from_api(name, info, browser)

                # 如果API失败，尝试人大官网
                if not policy and name in FALLBACK_URLS:
                    print(f"  🔄 尝试备用源: 全国人大官网")
                    policy = await self.crawl_from_npc(name, FALLBACK_URLS[name], info, browser)

                if policy:
                    # 检查是否已存在
                    existing = self.collection.find_one({'policy_id': policy['policy_id']})
                    if existing:
                        print(f"  ℹ️  已存在，更新数据")
                        self.collection.update_one(
                            {'policy_id': policy['policy_id']},
                            {'$set': policy}
                        )
                    else:
                        self.collection.insert_one(policy)
                        print(f"  ✅ 保存成功")

                    self.results.append({
                        'name': name,
                        'title': policy['title'],
                        'level': policy['document_level'],
                        'content_length': len(policy['content']),
                    })
                else:
                    print(f"  ⚠️  {name}: 爬取失败")

            await browser.close()

        print("\n" + "=" * 60)
        print("爬取完成!")
        print("=" * 60)

    def print_results(self):
        """打印结果统计"""
        print(f"\n📊 爬取结果:")
        print(f"成功: {len(self.results)} 条")

        for r in self.results:
            print(f"  • [{r['level']}] {r['name']}")
            print(f"    标题: {r['title'][:50]}...")
            print(f"    内容长度: {r['content_length']} 字符")


async def main():
    """主函数"""
    crawler = LawsCrawler()
    await crawler.crawl_all()
    crawler.print_results()


if __name__ == '__main__':
    asyncio.run(main())
