"""
基础爬虫类
提供所有爬虫的通用功能
"""

import time
import random
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from .config import crawler_config
from .data_models import PolicyDocument, CrawlTask


class BaseCrawler(ABC):
    """爬虫基类"""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.session = requests.Session()

        # 配置请求头
        self.session.headers.update({
            'User-Agent': crawler_config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

        # 配置日志
        self.logger = logging.getLogger(f"Crawler.{name}")
        self.logger.setLevel(getattr(logging, crawler_config.log_level))

        # 统计信息
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }

    def _delay(self):
        """随机延迟，避免请求过快"""
        delay = random.uniform(crawler_config.delay_min, crawler_config.delay_max)
        self.logger.debug(f"Delay {delay:.2f}s before next request")
        time.sleep(delay)

    def _request(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """发送HTTP请求，带重试机制"""
        for attempt in range(crawler_config.retry_times):
            try:
                self._delay()
                response = self.session.request(
                    method,
                    url,
                    timeout=crawler_config.timeout,
                    **kwargs
                )
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    self.logger.warning(f"Access forbidden (403): {url}")
                elif e.response.status_code == 404:
                    self.logger.warning(f"Not found (404): {url}")
                    return None
                else:
                    self.logger.error(f"HTTP error {e.response.status_code}: {url}")
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error: {e}, URL: {url}")

            if attempt < crawler_config.retry_times - 1:
                retry_delay = crawler_config.retry_delay * (2 ** attempt)
                self.logger.info(f"Retry in {retry_delay}s...")
                time.sleep(retry_delay)

        self.logger.error(f"Failed after {crawler_config.retry_times} attempts: {url}")
        return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        """解析HTML"""
        return BeautifulSoup(html, 'html.parser')

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        # 去除多余空白
        text = ' '.join(text.split())
        # 去除特殊字符
        text = text.replace('\u3000', ' ')  # 全角空格
        text = text.replace('\xa0', ' ')     # 不间断空格
        return text.strip()

    def _extract_date(self, date_str: str) -> Optional[datetime]:
        """提取日期"""
        if not date_str:
            return None

        # 常见日期格式
        date_formats = [
            '%Y-%m-%d',
            '%Y年%m月%d日',
            '%Y/%m/%d',
            '%Y.%m.%d',
            '%Y-%m-%d %H:%M:%S',
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        self.logger.warning(f"Failed to parse date: {date_str}")
        return None

    def _is_within_date_range(self, date: Optional[datetime]) -> bool:
        """检查日期是否在指定范围内"""
        if not date:
            return True

        start = datetime(crawler_config.start_year, 1, 1)
        end = datetime(crawler_config.end_year + 1, 1, 1)

        return start <= date < end

    def _is_target_tax_type(self, text: str) -> bool:
        """检查是否为目标税种"""
        if not crawler_config.target_tax_types:
            return True

        text_lower = text.lower()
        for tax_type in crawler_config.target_tax_types:
            if tax_type in text:
                return True

        return False

    @abstractmethod
    def get_policy_list(self, channel: str = None, **kwargs) -> List[Dict[str, Any]]:
        """获取政策列表

        Args:
            channel: 栏目名称
            **kwargs: 其他参数

        Returns:
            政策列表，每个元素包含 {title, url, publish_date, ...}
        """
        pass

    @abstractmethod
    def parse_policy_detail(self, url: str, list_data: Dict[str, Any] = None) -> Optional[PolicyDocument]:
        """解析政策详情页

        Args:
            url: 详情页URL
            list_data: 列表页提取的数据

        Returns:
            PolicyDocument对象或None
        """
        pass

    def crawl_channel(self, channel: str = None, **kwargs) -> List[PolicyDocument]:
        """爬取指定栏目

        Args:
            channel: 栏目名称
            **kwargs: 其他参数

        Returns:
            爬取的政策文档列表
        """
        self.logger.info(f"Starting to crawl channel: {channel}")

        # 获取政策列表
        policy_list = self.get_policy_list(channel, **kwargs)
        self.logger.info(f"Found {len(policy_list)} policies in channel: {channel}")

        documents = []

        # 爬取每个政策详情
        for idx, item in enumerate(policy_list, 1):
            self.logger.info(f"[{idx}/{len(policy_list)}] Processing: {item.get('title', 'Unknown')}")

            self.stats['total'] += 1

            try:
                doc = self.parse_policy_detail(item['url'], item)
                if doc:
                    # 数据验证
                    if self._validate_document(doc):
                        documents.append(doc)
                        self.stats['success'] += 1
                    else:
                        self.stats['skipped'] += 1
                        self.logger.info(f"Document skipped (not in target range): {doc.title}")
                else:
                    self.stats['failed'] += 1
            except Exception as e:
                self.stats['failed'] += 1
                self.logger.error(f"Error parsing policy: {e}", exc_info=True)

        self.logger.info(
            f"Channel {channel} completed. "
            f"Total: {self.stats['total']}, "
            f"Success: {self.stats['success']}, "
            f"Failed: {self.stats['failed']}, "
            f"Skipped: {self.stats['skipped']}"
        )

        return documents

    def _validate_document(self, doc: PolicyDocument) -> bool:
        """验证文档是否符合目标条件

        Args:
            doc: 政策文档

        Returns:
            是否符合
        """
        # 检查日期范围
        if doc.publish_date and not self._is_within_date_range(doc.publish_date):
            return False

        # 检查税种
        if doc.tax_type:
            content = f"{doc.title} {doc.content}".lower()
            if not any(t.lower() in content for t in crawler_config.target_tax_types):
                return False

        return True

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self.stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }
