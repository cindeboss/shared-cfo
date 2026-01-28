"""
地方税务局爬虫（北京、上海、广东）
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin
import re

from .base import BaseCrawler
from .data_models import PolicyDocument, DocumentType, Region, TaxType, QAPair


class BeijingTaxCrawler(BaseCrawler):
    """北京税务局爬虫"""

    def __init__(self):
        super().__init__(
            name="BeijingTax",
            base_url="http://beijing.chinatax.gov.cn"
        )

    def get_policy_list(self, channel: str = None, **kwargs) -> List[Dict[str, Any]]:
        """获取政策列表"""
        policies = []

        # 北京税务网站的热点问答通常按月归档
        # URL格式: /bjswj/c105397/YYYYMM/hash.shtml

        start_year = kwargs.get('start_year', 2022)
        end_year = kwargs.get('end_year', 2025)

        # 个人所得税热点
        if channel in ['hot_iit', 'all']:
            base_path = "/bjswj/c105397"
            policies.extend(self._crawl_archive(base_path, start_year, end_year, TaxType.IIT))

        # 企业所得税热点
        if channel in ['hot_cit', 'all']:
            base_path = "/bjswj/c105425"
            policies.extend(self._crawl_archive(base_path, start_year, end_year, TaxType.CIT))

        return policies

    def _crawl_archive(self, base_path: str, start_year: int, end_year: int, tax_type: TaxType) -> List[Dict[str, Any]]:
        """爬取归档内容"""
        policies = []

        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                # 构建月度归档URL
                date_str = f"{year}{month:02d}"
                archive_url = f"{self.base_url}{base_path}/{date_str}/index.shtml"

                response = self._request(archive_url)
                if not response:
                    continue

                # 解析该月的问答列表
                soup = self._parse_html(response.text)
                links = soup.find_all('a', href=re.compile(rf'{date_str}/[a-f0-9]+\.shtml'))

                for link in links:
                    title = self._clean_text(link.get_text())
                    href = link.get('href', '')

                    if href and not href.startswith('http'):
                        href = urljoin(self.base_url, href)

                    policies.append({
                        'title': title,
                        'url': href,
                        'tax_type': tax_type,
                        'publish_date': self._extract_date(f"{year}-{month:02d}-01"),
                    })

        return policies

    def parse_policy_detail(self, url: str, list_data: Dict[str, Any] = None) -> Optional[PolicyDocument]:
        """解析政策详情页"""
        response = self._request(url)
        if not response:
            return None

        soup = self._parse_html(response.text)

        title = list_data.get('title') if list_data else ''
        if not title:
            title_elem = soup.find('h1') or soup.find('h2')
            if title_elem:
                title = self._clean_text(title_elem.get_text())

        # 提取问答内容
        qa_pairs = []
        content_div = soup.find('div', class_='content') or soup.find('div', class_='article-content')

        if content_div:
            # 北京税务的问答格式通常是：
            # 问：...
            # 答：...
            text = self._clean_text(content_div.get_text(separator='\n', strip=True))

            # 分割问答对
            qa_sections = re.split(r'问[：:]', text)

            for section in qa_sections[1:]:  # 跳过第一个空section
                if '答' in section or '回' in section:
                    parts = re.split(r'答[：:]', section, maxsplit=1)
                    if len(parts) == 2:
                        question = self._clean_text(parts[0])
                        answer = self._clean_text(parts[1])
                        if question and answer:
                            qa_pairs.append(QAPair(question=question, answer=answer))

        # 生成唯一ID
        policy_id = url.split('/')[-1].replace('.shtml', '') if url.endswith('.shtml') else url

        doc = PolicyDocument(
            policy_id=policy_id,
            title=title,
            source="北京税务局",
            url=url,
            tax_type=[list_data.get('tax_type', TaxType.OTHER)] if list_data else [TaxType.OTHER],
            region=Region.BEIJING,
            document_type=DocumentType.QA,
            content='\n'.join([f"问：{qa.question}\n答：{qa.answer}" for qa in qa_pairs]),
            qa_pairs=qa_pairs,
            publish_date=list_data.get('publish_date') if list_data else None,
            publish_department="北京市税务局",
        )

        return doc


class ShanghaiTaxCrawler(BaseCrawler):
    """上海税务局爬虫"""

    def __init__(self):
        super().__init__(
            name="ShanghaiTax",
            base_url="https://shanghai.chinatax.gov.cn"
        )

    def get_policy_list(self, channel: str = None, **kwargs) -> List[Dict[str, Any]]:
        """获取政策列表"""
        policies = []

        # 政策解读
        if channel in ['interpretation', 'all']:
            policies.extend(self._get_list_from_page(
                f"{self.base_url}/zcfw/zcjd/",
                DocumentType.INTERPRETATION
            ))

        # 热点问答
        if channel in ['hot_qa', 'all']:
            policies.extend(self._get_list_from_page(
                f"{self.base_url}/zcfw/rdwd/",
                DocumentType.QA
            ))

        return policies

    def _get_list_from_page(self, url: str, doc_type: DocumentType) -> List[Dict[str, Any]]:
        """从列表页获取政策列表"""
        policies = []

        response = self._request(url)
        if not response:
            return policies

        soup = self._parse_html(response.text)

        # 上海税务的列表格式：圆点列表
        list_items = soup.find_all('li')

        for item in list_items:
            link = item.find('a')
            if not link:
                continue

            title = self._clean_text(link.get_text())
            href = link.get('href', '')

            # 过滤非政策链接
            if not href or 'javascript' in href or 'htm' not in href:
                continue

            if not href.startswith('http'):
                href = urljoin(self.base_url, href)

            # 提取日期
            date_text = item.get_text()
            date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_text)
            publish_date = None
            if date_match:
                publish_date = self._extract_date(date_match.group(0))

            policies.append({
                'title': title,
                'url': href,
                'document_type': doc_type,
                'publish_date': publish_date,
            })

        return policies

    def parse_policy_detail(self, url: str, list_data: Dict[str, Any] = None) -> Optional[PolicyDocument]:
        """解析政策详情页"""
        response = self._request(url)
        if not response:
            return None

        soup = self._parse_html(response.text)

        # 提取标题（上海税务用双下划线包裹标题）
        title = list_data.get('title') if list_data else ''
        if not title:
            # 尝试从页面中提取
            title_elem = soup.find('h1') or soup.find('h2')
            if title_elem:
                title = self._clean_text(title_elem.get_text().replace('_', ''))

        # 提取问答内容
        qa_pairs = []
        content_div = soup.find('div', class_='content') or soup.find('div', class_='article-content')

        if content_div:
            text = self._clean_text(content_div.get_text(separator='\n', strip=True))

            # 上海税务的问答格式：__问题__ \n 答：...
            qa_sections = re.split(r'__[^_]+__', text)

            for section in qa_sections:
                if '答' in section or '回' in section:
                    parts = re.split(r'答[：:]', section, maxsplit=1)
                    if len(parts) == 2:
                        question = self._clean_text(parts[0])
                        answer = self._clean_text(parts[1])
                        if question and answer:
                            qa_pairs.append(QAPair(question=question, answer=answer))

        # 生成唯一ID
        policy_id = url.split('/')[-1].replace('.html', '') if url.endswith('.html') else url

        doc = PolicyDocument(
            policy_id=policy_id,
            title=title,
            source="上海税务局",
            url=url,
            tax_type=self._classify_tax_type(title),
            region=Region.SHANGHAI,
            document_type=list_data.get('document_type', DocumentType.OTHER) if list_data else DocumentType.OTHER,
            content='\n'.join([f"问：{qa.question}\n答：{qa.answer}" for qa in qa_pairs]),
            qa_pairs=qa_pairs,
            publish_date=list_data.get('publish_date') if list_data else None,
            publish_department="上海市税务局",
        )

        return doc

    def _classify_tax_type(self, title: str) -> List[TaxType]:
        """分类税种"""
        title_lower = title.lower()
        tax_types = []

        if '增值税' in title_lower or '个税' in title_lower:
            tax_types.append(TaxType.VAT)
        elif '个人所得税' in title_lower or '工资' in title_lower or '汇算' in title_lower:
            tax_types.append(TaxType.IIT)
        elif '企业' in title_lower:
            tax_types.append(TaxType.CIT)
        else:
            tax_types.append(TaxType.OTHER)

        return tax_types


class GuangdongTaxCrawler(BaseCrawler):
    """广东税务局爬虫"""

    def __init__(self):
        super().__init__(
            name="GuangdongTax",
            base_url="https://guangdong.chinatax.gov.cn"
        )

    def get_policy_list(self, channel: str = None, **kwargs) -> List[Dict[str, Any]]:
        """获取政策列表"""
        # 广东税务网站结构较为复杂，这里提供一个基础实现
        policies = []

        # 获取政策解读列表
        if channel in ['interpretation', 'all']:
            url = f"{self.base_url}/gdsw/gzsw_zcfg/"
            response = self._request(url)
            if response:
                soup = self._parse_html(response.text)
                links = soup.find_all('a', href=re.compile(r'shtml'))

                for link in links[:50]:  # 限制数量
                    title = self._clean_text(link.get_text())
                    href = link.get('href', '')

                    if href and not href.startswith('http'):
                        href = urljoin(self.base_url, href)

                    policies.append({
                        'title': title,
                        'url': href,
                        'document_type': DocumentType.INTERPRETATION,
                    })

        return policies

    def parse_policy_detail(self, url: str, list_data: Dict[str, Any] = None) -> Optional[PolicyDocument]:
        """解析政策详情页"""
        response = self._request(url)
        if not response:
            return None

        soup = self._parse_html(response.text)

        title = list_data.get('title') if list_data else ''
        if not title:
            title_elem = soup.find('h1') or soup.find('h2')
            if title_elem:
                title = self._clean_text(title_elem.get_text())

        # 提取正文
        content_div = soup.find('div', class_='content') or soup.find('div', class_='article-content')
        if content_div:
            content = self._clean_text(content_div.get_text(separator='\n', strip=True))
        else:
            content = ''

        policy_id = url.split('/')[-1].replace('.shtml', '') if url.endswith('.shtml') else url

        doc = PolicyDocument(
            policy_id=policy_id,
            title=title,
            source="广东税务局",
            url=url,
            tax_type=self._classify_tax_type(title, content),
            region=Region.GUANGDONG,
            document_type=list_data.get('document_type', DocumentType.OTHER) if list_data else DocumentType.OTHER,
            content=content,
            publish_department="广东省税务局",
        )

        return doc

    def _classify_tax_type(self, title: str, content: str) -> List[TaxType]:
        """分类税种"""
        text = f"{title} {content}".lower()
        tax_types = []

        if '增值税' in text:
            tax_types.append(TaxType.VAT)
        if '企业所得税' in text or '汇算清缴' in text:
            tax_types.append(TaxType.CIT)
        if '个人所得税' in text or '个税' in text:
            tax_types.append(TaxType.IIT)

        if not tax_types:
            tax_types.append(TaxType.OTHER)

        return tax_types
