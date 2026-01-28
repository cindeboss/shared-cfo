"""
国家税务总局政策法规库爬虫 v4.0
支持完整的政策层级体系和关联关系
根据《共享CFO - 爬虫模块需求文档 v3.0》设计

合规性说明：
- 只爬取公开的政府政策信息
- 遵守robots.txt协议
- 限制访问频率，避免对服务器造成负担
- 添加明确的User-Agent标识
"""

import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urljoin, urlparse
import logging

from bs4 import BeautifulSoup
from .base_v2 import BaseCrawler


logger = logging.getLogger("ChinaTaxCrawler")


class ChinaTaxCrawler(BaseCrawler):
    """
    国家税务总局政策法规库爬虫
    网址: https://fgk.chinatax.gov.cn/

    栏目结构：
    - c100001: 法律 (L1)
    - c100002: 行政法规 (L1)
    - c100003: 部门规章 (L2)
    - c100004: 财税文件 (L2)
    - c100005: 规范性文件 (L3)
    - c100015: 政策解读 (L4)
    """

    def __init__(self, db_connector=None):
        super().__init__(db_connector)
        self.base_url = "https://fgk.chinatax.gov.cn"

        # 栏目映射到层级和类型
        self.category_config = {
            'c100001': {'level': 'L1', 'type': '法律', 'tax_category': '实体税'},
            'c100002': {'level': 'L1', 'type': '行政法规', 'tax_category': '实体税'},
            'c100003': {'level': 'L2', 'type': '部门规章', 'tax_category': '实体税'},
            'c100004': {'level': 'L2', 'type': '财税文件', 'tax_category': '实体税'},
            'c100005': {'level': 'L3', 'type': '规范性文件', 'tax_category': '实体税'},
            'c100015': {'level': 'L4', 'type': '官方解读', 'tax_category': '实体税'},
        }

    def get_source_name(self) -> str:
        return "国家税务总局"

    def get_base_url(self) -> str:
        return self.base_url

    def get_category_list_url(self, category_id: str, page: int = 1) -> str:
        """获取栏目列表页URL"""
        # 法规库的列表页URL格式
        return f"{self.base_url}/zcfgk/{category_id}/listflfg.html"

    def get_detail_url(self, doc_id: str) -> str:
        """获取详情页URL"""
        return f"{self.base_url}/zcfgk/detail.html?id={doc_id}"

    def crawl_list_page(self, url: str, max_pages: int = 10) -> List[str]:
        """
        爬取列表页，返回详情页URL列表
        """
        detail_urls = []

        try:
            # 爬取多页
            for page in range(1, max_pages + 1):
                list_url = url.replace('listflfg.html', f'listflfg_{page}.html') if page > 1 else url

                response = self._make_request(list_url)
                if not response:
                    break

                soup = self._parse_html(response.text)

                # 查找政策链接
                # 法规库通常使用 <a> 标签，href 可能是 detail.html?id=xxx
                for link in soup.find_all('a', href=True):
                    href = link['href']

                    # 检查是否为详情页链接
                    if 'detail.html' in href or 'detail?' in href:
                        full_url = urljoin(self.base_url, href)

                        # 提取文档ID
                        doc_id = self._extract_doc_id(href)
                        if doc_id:
                            detail_url = self.get_detail_url(doc_id)
                            if detail_url not in detail_urls:
                                detail_urls.append(detail_url)

                self.logger.info(f"Found {len(detail_urls)} URLs from page {page}")

                # 检查是否有下一页
                next_page = soup.find('a', text=re.compile(r'下一页|下页'))
                if not next_page:
                    break

        except Exception as e:
            self.logger.error(f"Error crawling list page {url}: {e}")

        return detail_urls

    def _extract_doc_id(self, href: str) -> Optional[str]:
        """从链接中提取文档ID"""
        # 匹配 detail.html?id=xxx 或 detail?id=xxx
        match = re.search(r'id=([a-zA-Z0-9_-]+)', href)
        if match:
            return match.group(1)

        # 匹配路径中的ID，如 /zcfgk/2023/12345.html
        match = re.search(r'/(\d{6,})\.html', href)
        if match:
            return match.group(1)

        return None

    def extract_content_from_page(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        从解析的页面中提取内容
        返回: {title, content, metadata}
        """
        result = {'title': '', 'content': '', 'metadata': {}}

        try:
            # 提取标题 - 通常在 <h1> 或特定的标题容器中
            title_selectors = [
                'h1.title',
                'h1',
                '.title',
                '#title',
                'div[class*="title"] h1',
            ]

            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    result['title'] = title_elem.get_text(strip=True)
                    break

            # 提取发文字号
            doc_number = self._extract_document_number_from_soup(soup)
            if doc_number:
                result['metadata']['document_number'] = doc_number

            # 提取发布日期
            publish_date = self._extract_publish_date_from_soup(soup)
            if publish_date:
                result['metadata']['publish_date'] = publish_date

            # 提取正文内容
            content_selectors = [
                'div.content',
                'div[class*="content"]',
                'div[id*="content"]',
                'article',
                '.detail-content',
                '#content',
            ]

            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 清理内容
                    text = content_elem.get_text(separator='\n', strip=True)
                    result['content'] = text
                    break

            # 如果没找到内容，尝试提取整个body
            if not result['content']:
                body = soup.find('body')
                if body:
                    # 移除script和style标签
                    for script in body(['script', 'style', 'nav', 'header', 'footer']):
                        script.decompose()
                    result['content'] = body.get_text(separator='\n', strip=True)

        except Exception as e:
            self.logger.error(f"Error extracting content: {e}")

        return result

    def _extract_document_number_from_soup(self, soup: BeautifulSoup) -> Optional[str]:
        """从页面中提取发文字号"""
        # 查找包含发文字号的元素
        patterns = [
            r'财[政关税]\s*〔\[\(]\s*\d{4}\s*[\]\)\〕]\s*号',
            r'税\s*总\s*发\s*〔\[\(]\s*\d{4}\s*[\]\)\〕]\s*号',
            r'国家税务总局公告\s*\d{4}\s*年\s*第\s*\d+\s*号',
        ]

        # 在整个页面中搜索
        page_text = soup.get_text()

        for pattern in patterns:
            match = re.search(pattern, page_text)
            if match:
                return match.group(0)

        return None

    def _extract_publish_date_from_soup(self, soup: BeautifulSoup) -> Optional[datetime]:
        """从页面中提取发布日期"""
        # 查找日期元素
        date_patterns = [
            r'成文日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})',
            r'发布日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})',
            r'(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})',
        ]

        page_text = soup.get_text()

        for pattern in date_patterns:
            match = re.search(pattern, page_text)
            if match:
                try:
                    year, month, day = match.groups()[:3]
                    return datetime(int(year), int(month), int(day))
                except (ValueError, IndexError):
                    pass

        return None

    def crawl_category(self, category_id: str, max_pages: int = 5) -> Dict[str, int]:
        """
        爬取指定栏目
        """
        self.logger.info(f"Crawling category: {category_id}")

        list_url = self.get_category_list_url(category_id)
        detail_urls = self.crawl_list_page(list_url, max_pages)

        stats = {'total': len(detail_urls), 'success': 0, 'failed': 0, 'duplicate': 0}

        # 获取栏目配置
        config = self.category_config.get(category_id, {})

        for url in detail_urls:
            try:
                policy_data = self.crawl_detail_page(url)
                if policy_data:
                    # 应用栏目配置
                    if config.get('level'):
                        policy_data['document_level'] = config['level']
                    if config.get('type'):
                        policy_data['document_type'] = config['type']
                    if config.get('tax_category'):
                        policy_data['tax_category'] = config['tax_category']

                    if self.save_policy(policy_data):
                        stats['success'] += 1
                    else:
                        stats['duplicate'] += 1
                else:
                    stats['failed'] += 1
            except Exception as e:
                self.logger.error(f"Failed to crawl {url}: {e}")
                stats['failed'] += 1

        self.logger.info(f"Category {category_id} completed: {stats}")
        return stats

    def crawl_all(self, categories: List[str] = None, max_pages_per_category: int = 3) -> Dict[str, Any]:
        """
        爬取所有指定栏目
        """
        if categories is None:
            categories = ['c100001', 'c100002', 'c100003', 'c100004', 'c100005']

        total_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'duplicate': 0,
            'by_category': {}
        }

        for category_id in categories:
            category_name = self.category_config.get(category_id, {}).get('type', category_id)
            self.logger.info(f"Starting category: {category_name} ({category_id})")

            stats = self.crawl_category(category_id, max_pages_per_category)

            total_stats['total'] += stats['total']
            total_stats['success'] += stats['success']
            total_stats['failed'] += stats['failed']
            total_stats['duplicate'] += stats['duplicate']
            total_stats['by_category'][category_name] = stats

        self.logger.info(f"All categories completed: {total_stats}")
        return total_stats

    def crawl_laws(self, max_pages: int = 1) -> Dict[str, int]:
        """爬取法律（L1）"""
        return self.crawl_category('c100001', max_pages)

    def crawl_regulations(self, max_pages: int = 2) -> Dict[str, int]:
        """爬取行政法规（L1）"""
        return self.crawl_category('c100002', max_pages)

    def crawl_rules(self, max_pages: int = 5) -> Dict[str, int]:
        """爬取部门规章（L2）"""
        return self.crawl_category('c100003', max_pages)

    def crawl_fiscal_docs(self, max_pages: int = 10) -> Dict[str, int]:
        """爬取财税文件（L2）"""
        return self.crawl_category('c100004', max_pages)

    def crawl_normative_docs(self, max_pages: int = 5) -> Dict[str, int]:
        """爬取规范性文件（L3）"""
        return self.crawl_category('c100005', max_pages)

    def crawl_interpretations(self, max_pages: int = 5) -> Dict[str, int]:
        """爬取政策解读（L4）"""
        return self.crawl_category('c100015', max_pages)


# 便捷函数
def crawl_chinatax(db_connector, categories: List[str] = None, max_pages: int = 3) -> Dict[str, Any]:
    """
    便捷函数：爬取国家税务总局政策法规库
    """
    crawler = ChinaTaxCrawler(db_connector)

    try:
        if categories is None:
            # 默认爬取主要栏目
            categories = ['c100001', 'c100002', 'c100003', 'c100004']

        return crawler.crawl_all(categories, max_pages)
    finally:
        crawler.close()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    from .database_v2 import MongoDBConnectorV2

    db = MongoDBConnectorV2()
    crawler = ChinaTaxCrawler(db)

    try:
        # 测试爬取法律（只爬1页）
        stats = crawler.crawl_laws(max_pages=1)
        print(f"Crawl completed: {stats}")
    finally:
        crawler.close()
        db.close()
