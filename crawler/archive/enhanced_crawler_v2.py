#!/usr/bin/env python3
"""
升级版Playwright税务政策爬虫
支持层级识别、字段提取、质量评分
"""
import asyncio
import logging
import random
import time
import re
from datetime import datetime
from urllib.parse import urljoin, quote_plus
from typing import List, Dict, Any, Optional, Tuple

from pymongo import MongoClient
from playwright.async_api import async_playwright, Browser, Page


# ==================== 字段提取模块 ====================

class PolicyLevel:
    """政策层级"""
    LAW = 1
    REGULATION = 2
    RULE = 3
    NORMATIVE = 4
    INTERPRETATION = 5
    GUIDANCE = 6

    @classmethod
    def get_name(cls, level):
        names = {
            1: "法律",
            2: "行政法规",
            3: "部门规章",
            4: "规范性文件",
            5: "官方解读",
            6: "执行口径"
        }
        return names.get(level, "未知")


class FieldExtractor:
    """字段提取器"""

    # 发文字号模式
    DOCUMENT_NUMBER_PATTERNS = [
        r'财[政关税]\s*〔\[]?\s*(\d{4})\s*\]?\s*号',
        r'税\s*总\s*发\s*〔\[]?\s*(\d{4})\s*\]?\s*号',
        r'国家税务总局公告\s*(\d{4})\s*年\s*第\s*(\d{1,3})\s*号',
        r'国务院令\s*第\s*([\d\u4e00\u4e8c\u4e09\u56db\u4e94\u4e03\u4ebf\u96f6]+)\s*号',
        r'公告\s*(\d{4})\s*年\s*第?\s*(\d{1,3})\s*号',
    ]

    # 日期模式
    DATE_PATTERNS = [
        r'成文日期\s*[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
        r'发布日期\s*[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
        r'(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日',
    ]

    # 税种模式
    TAX_TYPE_PATTERNS = {
        '增值税': r'增值税',
        '企业所得税': r'企业所得税',
        '个人所得税': r'个人所得税|个税',
    }

    def extract_document_number(self, text: str) -> Optional[str]:
        """提取发文字号"""
        if not text:
            return None

        for pattern in self.DOCUMENT_NUMBER_PATTERNS:
            match = re.search(pattern, text)
            if match:
                result = match.group(0)
                result = re.sub(r'\s+', '', result)
                result = result.replace('〔', '[').replace('〕', ']')
                return result.strip()
        return None

    def extract_dates(self, text: str) -> dict:
        """提取日期信息"""
        result = {
            'publish_date': None,
            'effective_date': None,
            'expiry_date': None,
            'validity_status': 'unknown',
        }

        if not text:
            return result

        # 提取日期
        for pattern in self.DATE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    year = int(re.search(r'(\d{4})', match[0]).group(1))
                    month = int(re.search(r'(\d{1,2})', match[1]).group(1))
                    day = int(re.search(r'(\d{1,2})', match[2] if len(match) > 2 else match[2]).group(1))

                    date_obj = datetime(year, month, day)

                    if not result['publish_date']:
                        result['publish_date'] = date_obj

                except (ValueError, AttributeError, IndexError):
                    continue

        # 提取有效期
        expiry_patterns = [
            r'执行期限\s*[：:]\s*(.*?)(?=。|；|\n|$)',
            r'自\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日.*?至\s*(\d{4})[年\-]?\s*(\d{1,2})?[月\-]?\s*(\d{1,2})?日?',
            r'(截止|有效期至)\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
        ]

        for pattern in expiry_patterns:
            match = re.search(pattern, text)
            if match:
                expiry_text = match.group(0)

                # 检查长期有效
                if re.search(r'(长期|无限期|永久)', expiry_text):
                    result['validity_status'] = 'valid'
                    result['expiry_date'] = None
                    break

                # 提取截止日期
                date_match = re.search(r'(\d{4})[年\-](\d{1,2})[月\-]?\s*(\d{1,2})?日?', expiry_text)
                if date_match:
                    try:
                        year = int(date_match.group(1))
                        month = int(date_match.group(2)) if date_match.group(2) else 12
                        day = int(date_match.group(3)) if date_match.group(3) else 31
                        result['expiry_date'] = datetime(year, month, day)

                        if result['expiry_date'] < datetime.now():
                            result['validity_status'] = 'expired'
                        else:
                            result['validity_status'] = 'valid'
                    except ValueError:
                        pass
                break

        # 如果有发布日期但无有效期，推断状态
        if result['publish_date'] and result['validity_status'] == 'unknown':
            if result['publish_date'].year < datetime.now().year - 5:
                result['validity_status'] = 'possibly_expired'
            else:
                result['validity_status'] = 'valid'

        return result

    def determine_tax_type(self, title: str, content: str) -> List[str]:
        """判断税种"""
        tax_types = []
        combined_text = f"{title} {content}"

        for tax_name, pattern in self.TAX_TYPE_PATTERNS.items():
            if re.search(pattern, combined_text):
                if tax_name not in tax_types:
                    tax_types.append(tax_name)

        return tax_types if tax_types else ['其他']

    def determine_authority(self, text: str, url: str = '') -> Tuple[str, str]:
        """判断制定机关"""
        authority = "国家税务总局"
        authority_type = "行政机关"

        if '人大' in text or '全国人民代表大会' in text:
            return "全国人民代表大会", "立法机关"

        return authority, authority_type

    def determine_level(self, title: str, content: str) -> int:
        """判断政策层级"""
        if '中华人民共和国.*?法' in title and '全国人民代表大会' in content:
            return PolicyLevel.LAW
        if '实施条例' in title and '国务院' in content:
            return PolicyLevel.REGULATION
        if '管理办法' in title or '实施细则' in title:
            return PolicyLevel.RULE
        if '解读' in title or '答记者问' in title:
            return PolicyLevel.INTERPRETATION
        if '12366' in title:
            return PolicyLevel.GUIDANCE
        return PolicyLevel.NORMATIVE

    def determine_document_type(self, title: str) -> str:
        """判断文档类型"""
        if '法' in title and '中华人民共和国' in title:
            return '法律'
        if '实施条例' in title:
            return '行政法规'
        if '办法' in title or '细则' in title or '规定' in title:
            return '部门规章'
        if '解读' in title:
            return '政策解读'
        if '公告' in title:
            return '公告'
        if '通知' in title:
            return '通知'
        return '规范性文件'

    def extract_key_points(self, content: str) -> List[str]:
        """提取关键要点"""
        key_points = []
        if not content:
            return key_points

        # 按段落分割
        paragraphs = re.split(r'[。\n]{2,}', content)
        for para in paragraphs:
            para = para.strip()
            if 50 < len(para) < 300:
                key_points.append(para)

        return key_points[:10]

    def calculate_quality_score(self, doc: dict) -> int:
        """计算质量分数"""
        score = 0

        # 必需字段 (30分)
        if doc.get('document_number'):
            score += 10
        if doc.get('publish_date'):
            score += 10
        if len(doc.get('title', '')) > 20:
            score += 10

        # 内容质量 (40分)
        content_len = len(doc.get('content', ''))
        if content_len > 200:
            score += 5
        if content_len > 500:
            score += 10
        if content_len > 1000:
            score += 10
        if content_len > 2000:
            score += 5

        if '解读' in doc.get('title', ''):
            score += 10

        # 时效性 (20分)
        if doc.get('effective_date'):
            score += 10
        if doc.get('expiry_date'):
            score += 10

        # 结构化 (10分)
        if doc.get('tax_type') and doc['tax_type'] != ['其他']:
            score += 5
        if doc.get('document_number'):
            score += 5

        return min(score, 100)

    def determine_quality_level(self, score: int) -> int:
        """确定质量等级"""
        if score >= 90:
            return 5
        elif score >= 75:
            return 4
        elif score >= 60:
            return 3
        elif score >= 40:
            return 2
        else:
            return 1

    def extract_all_fields(self, title: str, content: str, url: str, source: str) -> dict:
        """提取所有字段"""
        result = {
            'title': title,
            'content': content,
            'url': url,
            'source': source,
        }

        # 1. 提取发文字号
        result['document_number'] = self.extract_document_number(content)

        # 2. 提取日期
        dates = self.extract_dates(f"{title} {content}")
        result.update(dates)

        # 3. 判断税种
        result['tax_type'] = self.determine_tax_type(title, content)

        # 4. 判断制定机关
        authority, authority_type = self.determine_authority(content, url)
        result['issuing_authority'] = authority
        result['authority_type'] = authority_type

        # 5. 判断层级
        result['policy_level'] = self.determine_level(title, content)
        result['policy_level_name'] = PolicyLevel.get_name(result['policy_level'])

        # 6. 判断文档类型
        result['document_type'] = self.determine_document_type(title)

        # 7. 提取关键要点
        result['key_points'] = self.extract_key_points(content)

        # 8. 内容长度
        result['content_length'] = len(content)

        # 9. 质量分数
        result['quality_score'] = self.calculate_quality_score(result)

        # 10. 质量等级
        result['quality_level'] = self.determine_quality_level(result['quality_score'])

        return result


# ==================== 爬虫类 ====================

class EnhancedTaxCrawler:
    """增强版税务政策爬虫"""

    BASE_URL = "https://fgk.chinatax.gov.cn"

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
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = await context.new_page()

            stats = {
                'total': 0,
                'success': 0,
                'duplicate': 0,
                'error': 0,
                'by_level': {},
                'by_quality': {},
            }

            try:
                self.logger.info(f'访问: {self.BASE_URL}')
                await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=30000)
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

                            if 'chinatax.gov.cn' in full_url:
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
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await self.delay(1, 2)

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
                'policy_level_name': extracted.get('policy_level_name'),
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
            self.logger.info(f'✓ 保存成功 (层级:{extracted.get("policy_level_name")}, 质量:Lv{extracted.get("quality_level")}, 分数:{extracted.get("quality_score")})')
            return 'success'

        except Exception as e:
            error_str = str(e).lower()

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
            {'$group': {'quality_level': '$quality_level'}},
            {'$count': {'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]

        quality_counts = {}
        for doc in self.collection.aggregate(pipeline):
            level = doc.get('_id', 0)
            quality_counts[f"Level {level}"] = doc['count']

        self.logger.info('质量等级分布:')
        for level, count in sorted(quality_counts.items()):
            self.logger.info(f'  {level}: {count}条')

        # 层级分布
        pipeline2 = [
            {'$group': {'policy_level': '$policy_level'}},
            {'$count': {'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]

        level_counts = {}
        for doc in self.collection.aggregate(pipeline2):
            level = doc.get('_id', 0)
            level_counts[f"Level {level} ({PolicyLevel.get_name(level)})"] = doc['count']

        self.logger.info('层级分布:')
        for level, count in sorted(level_counts.items()):
            self.logger.info(f'  {level}: {count}条')

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


if __name__ == '__main__':
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
