"""
12366纳税服务平台爬虫 v2.0
爬取热点问答和办税指南
根据《共享CFO - 爬虫模块需求文档 v3.0》设计

合规性说明：
- 只爬取公开的政府政策信息
- 遵守robots.txt协议
- 限制访问频率，避免对服务器造成负担
"""

import re
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urljoin, urlencode
import logging

from bs4 import BeautifulSoup
from .base_v2 import BaseCrawler


logger = logging.getLogger("Crawler12366")


class Crawler12366(BaseCrawler):
    """
    12366纳税服务平台爬虫
    网址: https://12366.chinatax.gov.cn/

    主要栏目：
    - 热点问题
    - 办税指南
    - 政策问答
    """

    def __init__(self, db_connector=None):
        super().__init__(db_connector)
        self.base_url = "https://12366.chinatax.gov.cn"

        # 问答类型映射
        self.qa_type_mapping = {
            '增值税': '增值税',
            '企业所得税': '企业所得税',
            '个人所得税': '个人所得税',
            '房产税': '房产税',
            '印花税': '印花税',
            '征管': '征管程序',
        }

    def get_source_name(self) -> str:
        return "12366纳税服务平台"

    def get_base_url(self) -> str:
        return self.base_url

    def extract_content_from_page(self, soup: BeautifulSoup) -> Dict[str, str]:
        """从解析的页面中提取内容"""
        result = {'title': '', 'content': '', 'metadata': {}, 'qa_pairs': []}

        try:
            # 提取标题
            title_selectors = [
                'h1.title',
                'h1',
                '.qa-title',
                '.question-title',
            ]

            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    result['title'] = title_elem.get_text(strip=True)
                    break

            # 问答页特殊处理
            question_elem = soup.select_one('.question, .qa-question, .ask')
            answer_elem = soup.select_one('.answer, .qa-answer, .reply')

            if question_elem and answer_elem:
                question = question_elem.get_text(separator='\n', strip=True)
                answer = answer_elem.get_text(separator='\n', strip=True)

                result['qa_pairs'] = [{
                    'question': question,
                    'answer': answer,
                    'question_type': self._determine_question_type(question)
                }]

                # 使用问题作为标题
                if not result['title']:
                    result['title'] = question[:50] + ('...' if len(question) > 50 else '')

                # 使用答案作为内容
                result['content'] = answer

            else:
                # 常规内容提取
                content_selectors = [
                    'div.content',
                    'div[class*="content"]',
                    '.answer-content',
                ]

                for selector in content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        result['content'] = content_elem.get_text(separator='\n', strip=True)
                        break

            # 提取日期
            date_elem = soup.select_one('.date, .time, .publish-time, [class*="date"]')
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                result['metadata']['publish_date'] = self._parse_date(date_text)

            # 提取税种标签
            tags = soup.select('.tag, .label, [class*="tax"]')
            if tags:
                result['metadata']['tags'] = [tag.get_text(strip=True) for tag in tags]

        except Exception as e:
            self.logger.error(f"Error extracting content: {e}")

        return result

    def _determine_question_type(self, question: str) -> str:
        """判断问题类型"""
        if '增值税' in question:
            return '增值税'
        elif '企业所得税' in question or '企税' in question:
            return '企业所得税'
        elif '个人所得税' in question or '个税' in question:
            return '个人所得税'
        elif '申报' in question or '纳税' in question:
            return '征管程序'
        else:
            return '其他'

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """解析日期文本"""
        patterns = [
            r'(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    year, month, day = match.groups()[:3]
                    return datetime(int(year), int(month), int(day))
                except (ValueError, IndexError):
                    pass

        return None

    def crawl_list_page(self, url: str) -> List[str]:
        """爬取列表页"""
        detail_urls = []

        try:
            response = self._make_request(url)
            if not response:
                return detail_urls

            soup = self._parse_html(response.text)

            # 查找问题/文章链接
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text()

                # 检查是否为问答链接
                if any(kw in text for kw in ['问', '答', '热点', '指南']) and not href.startswith('javascript'):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in detail_urls:
                        detail_urls.append(full_url)

            self.logger.info(f"Found {len(detail_urls)} URLs from {url}")

        except Exception as e:
            self.logger.error(f"Error crawling list page {url}: {e}")

        return detail_urls

    def process_policy(self, url: str, html: str, extra_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """处理问答页面"""
        soup = self._parse_html(html)
        page_data = self.extract_content_from_page(soup)

        title = page_data.get('title', '')
        content = page_data.get('content', '')
        qa_pairs = page_data.get('qa_pairs', [])

        if not title or not content:
            return None

        # 问答类文档固定为L4层级
        source = self.get_source_name()
        policy_id = self._generate_policy_id(source, url)

        # 判断税种
        category, tax_types = self.extractor.determine_tax_category_and_type(title, content)

        policy_data = {
            'policy_id': policy_id,
            'title': title,
            'source': source,
            'url': url,
            'document_level': 'L4',
            'document_type': '热点问答',
            'tax_category': category,
            'tax_type': tax_types,
            'region': extra_data.get('region', '全国') if extra_data else '全国',
            'content': content,
            'qa_pairs': qa_pairs,
            'publish_date': page_data.get('metadata', {}).get('publish_date'),
            'crawled_at': datetime.now(),
            'extra': {
                'qa_type': self._determine_question_type(title),
                'tags': page_data.get('metadata', {}).get('tags', [])
            }
        }

        # 计算质量分数
        policy_data['quality_score'] = self.extractor.calculate_quality_score(policy_data)
        policy_data['quality_level'] = self.extractor.determine_quality_level(policy_data['quality_score'])

        return policy_data

    def crawl_hot_questions(self, keyword: str = '增值税', max_results: int = 50) -> Dict[str, int]:
        """
        爬取热点问题

        Args:
            keyword: 搜索关键词
            max_results: 最大结果数
        """
        self.logger.info(f"Crawling hot questions for: {keyword}")

        # 构建搜索URL
        search_url = f"{self.base_url}/portal/search/kwd?{urlencode({'kw': keyword})}"

        detail_urls = []
        for _ in range(5):  # 限制页数
            urls = self.crawl_list_page(search_url)
            if not urls:
                break
            detail_urls.extend(urls)
            if len(detail_urls) >= max_results:
                break

        detail_urls = detail_urls[:max_results]
        stats = {'total': len(detail_urls), 'success': 0, 'failed': 0, 'duplicate': 0}

        for url in detail_urls:
            try:
                policy_data = self.crawl_detail_page(url)
                if policy_data and self.save_policy(policy_data):
                    stats['success'] += 1
                elif policy_data:
                    stats['duplicate'] += 1
                else:
                    stats['failed'] += 1
            except Exception as e:
                self.logger.error(f"Failed to crawl {url}: {e}")
                stats['failed'] += 1

        self.logger.info(f"Hot questions for {keyword} completed: {stats}")
        return stats

    def crawl_all_tax_types(self, max_per_type: int = 30) -> Dict[str, Any]:
        """爬取所有主要税种的热点问题"""
        keywords = ['增值税', '企业所得税', '个人所得税', '印花税']

        total_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'duplicate': 0,
            'by_tax_type': {}
        }

        for keyword in keywords:
            stats = self.crawl_hot_questions(keyword, max_per_type)

            total_stats['total'] += stats['total']
            total_stats['success'] += stats['success']
            total_stats['failed'] += stats['failed']
            total_stats['duplicate'] += stats['duplicate']
            total_stats['by_tax_type'][keyword] = stats

        return total_stats


def crawl_12366(db_connector, keywords: List[str] = None, max_per_type: int = 30) -> Dict[str, Any]:
    """便捷函数：爬取12366平台"""
    crawler = Crawler12366(db_connector)

    try:
        if keywords is None:
            keywords = ['增值税', '企业所得税', '个人所得税']

        total_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'duplicate': 0,
            'by_tax_type': {}
        }

        for keyword in keywords:
            stats = crawler.crawl_hot_questions(keyword, max_per_type)
            total_stats['total'] += stats['total']
            total_stats['success'] += stats['success']
            total_stats['failed'] += stats['failed']
            total_stats['duplicate'] += stats['duplicate']
            total_stats['by_tax_type'][keyword] = stats

        return total_stats
    finally:
        crawler.close()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    from .database_v2 import MongoDBConnectorV2

    db = MongoDBConnectorV2()
    crawler = Crawler12366(db)

    try:
        # 测试爬取增值税热点问题
        stats = crawler.crawl_hot_questions('增值税', max_results=5)
        print(f"Crawl completed: {stats}")
    finally:
        crawler.close()
        db.close()
