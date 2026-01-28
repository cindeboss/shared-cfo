"""
国家税务总局政策法规库爬虫
"""

import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin

from .base import BaseCrawler
from .data_models import PolicyDocument, DocumentType, Region, TaxType


class ChinaTaxCrawler(BaseCrawler):
    """国家税务总局政策法规库爬虫"""

    def __init__(self):
        super().__init__(
            name="ChinaTax",
            base_url="https://fgk.chinatax.gov.cn"
        )

    def get_policy_list(self, channel: str = None, **kwargs) -> List[Dict[str, Any]]:
        """获取政策列表

        Args:
            channel: 栏目，如 'latest', 'law', 'interpretation' 等
            **kwargs: 额外参数
                - start_year: 起始年份（默认2022）
                - end_year: 结束年份（默认2025）
                - limit: 每次获取数量（默认20）
        """
        # 使用搜索API获取政策列表
        policies = []

        # 按年份分批获取
        start_year = kwargs.get('start_year', 2022)
        end_year = kwargs.get('end_year', 2025)
        limit = kwargs.get('limit', 20)

        for year in range(start_year, end_year + 1):
            self.logger.info(f"Fetching policies for year: {year}")

            # 分页获取
            start = 0
            while True:
                search_params = {
                    'start': start,
                    'limit': limit,
                    'publishDate': f'{year}-01-01',  # 搜索该年1月1日之后
                    'searchType': 1,  # 模糊搜索
                }

                # 构建搜索URL
                search_url = f"{self.base_url}/zcfgk/xsearch/list.do"

                response = self._request(search_url, method='POST', data=search_params)

                if not response:
                    break

                try:
                    data = response.json()
                    items = data.get('data', [])

                    if not items:
                        break

                    for item in items:
                        # 解析政策基本信息
                        title = item.get('title', '')
                        url = item.get('url', '')

                        if not title or not url:
                            continue

                        # 构建完整URL
                        if not url.startswith('http'):
                            url = urljoin(self.base_url, url)

                        publish_date = self._extract_date(item.get('publishDate', ''))

                        policies.append({
                            'title': title,
                            'url': url,
                            'publish_date': publish_date,
                            'document_type': self._infer_document_type(title),
                        })

                    # 检查是否还有更多数据
                    if len(items) < limit:
                        break

                    start += limit

                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse JSON response from {search_url}")
                    break

        return policies

    def parse_policy_detail(self, url: str, list_data: Dict[str, Any] = None) -> Optional[PolicyDocument]:
        """解析政策详情页"""
        response = self._request(url)
        if not response:
            return None

        soup = self._parse_html(response.text)

        # 提取标题
        title = list_data.get('title') if list_data else ''
        if not title:
            title_elem = soup.find('h1') or soup.find('h2') or soup.find('title')
            if title_elem:
                title = self._clean_text(title_elem.get_text())

        # 提取正文内容
        content_elem = (
            soup.find('div', class_='content') or
            soup.find('div', class_='article-content') or
            soup.find('div', id='content') or
            soup.find('div', class_='text')
        )

        if content_elem:
            content = self._clean_text(content_elem.get_text(separator='\n', strip=True))
        else:
            # 尝试获取整个body
            body = soup.find('body')
            content = self._clean_text(body.get_text(separator='\n', strip=True)) if body else ''

        # 提取元数据
        publish_date = list_data.get('publish_date') if list_data else None
        if not publish_date:
            # 尝试从页面中提取日期
            date_text = soup.find('span', class_='date') or soup.find('span', class_='publish-date')
            if date_text:
                publish_date = self._extract_date(date_text.get_text())

        # 提取文号
        document_number = None
        doc_num_pattern = r'([^、。\s]{1,10}〔\d{4}\]\d{1,10}号|[^、。\s]{1,10}\[\d{4}\]\d{1,10}号|[^、。\s]{1,10}发\d{4}\d{1,10}号)'
        match = re.search(doc_num_pattern, title)
        if match:
            document_number = match.group(1)

        # 提取发布单位
        publish_department = "国家税务总局"
        dept_elem = soup.find('span', class_='source') or soup.find('span', class_='department')
        if dept_elem:
            publish_department = self._clean_text(dept_elem.get_text())

        # 生成唯一ID
        policy_id = url.split('/')[-1].replace('.shtml', '') if url.endswith('.shtml') else url

        # 判断税种
        tax_types = self._classify_tax_type(title, content)

        # 构建文档对象
        doc = PolicyDocument(
            policy_id=policy_id,
            title=title,
            source="国家税务总局",
            url=url,
            tax_type=tax_types,
            region=Region.NATIONAL,
            document_type=list_data.get('document_type', DocumentType.OTHER) if list_data else DocumentType.OTHER,
            content=content,
            publish_date=publish_date,
            document_number=document_number,
            publish_department=publish_department,
        )

        return doc

    def _infer_document_type(self, title: str) -> DocumentType:
        """根据标题推断文档类型"""
        title_lower = title.lower()

        if '法律' in title or '法' in title:
            return DocumentType.LAW
        elif '条例' in title or '行政法规' in title:
            return DocumentType.REGULATION
        elif '规章' in title or '办法' in title:
            return DocumentType.RULE
        elif '公告' in title:
            return DocumentType.ANNOUNCEMENT
        elif '通知' in title:
            return DocumentType.NOTICE
        elif '解读' in title:
            return DocumentType.INTERPRETATION
        elif '财税' in title or '税' in title:
            return DocumentType.FISCAL_DOC
        else:
            return DocumentType.OTHER

    def _classify_tax_type(self, title: str, content: str) -> List[TaxType]:
        """分类税种"""
        text = f"{title} {content}".lower()
        tax_types = []

        if '增值税' in text or 'vat' in text or '进项' in text or '销项' in text:
            tax_types.append(TaxType.VAT)
        if any(kw in text for kw in ['企业所得税', '所得税', '企业所得税法', '汇算清缴']):
            tax_types.append(TaxType.CIT)
        if any(kw in text for kw in ['个人所得税', '工资薪金', '劳务报酬', '个税']):
            tax_types.append(TaxType.IIT)

        # 如果没有匹配到任何税种，默认为增值税
        if not tax_types:
            tax_types.append(TaxType.OTHER)

        return tax_types
