"""
Scrapy 中间件
"""

import time
import logging
from datetime import datetime
from scrapy import signals
from scrapy.exceptions import NotConfigured
from scrapy.http import HtmlResponse
from twisted.internet.error import TimeoutError, ConnectionRefusedError, ConnectError

logger = logging.getLogger(__name__)


class ComplianceMiddleware:
    """
    合规性中间件
    确保爬虫行为符合政府网站要求
    """

    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.stats)

    def process_request(self, request, spider):
        """请求前处理"""
        # 添加时间戳，用于监控
        request.meta['start_time'] = time.time()

        # 记录请求统计
        self.stats.inc_value('compliance/total_requests')

        return None

    def process_response(self, request, response, spider):
        """响应后处理"""
        # 记录成功请求
        self.stats.inc_value('compliance/successful_requests')

        # 检查是否被限流
        if response.status == 429:
            self.stats.inc_value('compliance/rate_limited')
            logger.warning(f"Rate limited: {request.url}")

        # 检查是否被禁止
        if response.status == 403:
            self.stats.inc_value('compliance/forbidden')
            logger.warning(f"Access forbidden: {request.url}")

        return response

    def process_exception(self, request, exception, spider):
        """异常处理"""
        self.stats.inc_value('compliance/exceptions')

        if isinstance(exception, TimeoutError):
            self.stats.inc_value('compliance/timeout_errors')
            logger.error(f"Timeout: {request.url}")

        elif isinstance(exception, (ConnectionRefusedError, ConnectError)):
            self.stats.inc_value('compliance/connection_errors')
            logger.error(f"Connection error: {request.url}")

        return None


class RateLimitMiddleware:
    """
    速率限制中间件
    确保不超过政府网站的请求限制
    """

    def __init__(self, limit_per_minute=15):
        self.limit_per_minute = limit_per_minute
        self.request_times = []

    @classmethod
    def from_crawler(cls, crawler):
        limit = crawler.settings.getint('RATE_LIMIT_PER_MINUTE', 15)
        return cls(limit)

    def process_request(self, request, spider):
        """请求前检查速率限制"""
        now = time.time()

        # 清理60秒前的记录
        self.request_times = [t for t in self.request_times if now - t < 60]

        # 如果达到限制，等待
        if len(self.request_times) >= self.limit_per_minute:
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
                # 清理过期记录
                self.request_times = []

        # 记录本次请求
        self.request_times.append(now)

        return None


class ErrorHandlingMiddleware:
    """
    错误处理中间件
    优雅地处理各种错误情况
    """

    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.stats)

    def process_response(self, request, response, spider):
        """处理响应"""
        # 记录状态码
        self.stats.inc_value(f'http_status/{response.status}')

        # 处理空响应
        if not response.body:
            self.stats.inc_value('response/empty')
            logger.warning(f"Empty response: {request.url}")

        return response


class SpiderExtension:
    """
    Spider 扩展
    提供额外的功能
    """

    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        spider = cls(crawler.stats)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(spider.spider_idle, signal=signals.spider_idle)
        return spider

    def spider_opened(self, spider):
        """Spider 启动时"""
        logger.info(f"Spider opened: {spider.name}")
        self.stats.set_value('spider/start_time', datetime.now().isoformat())

    def spider_closed(self, spider, reason):
        """Spider 关闭时"""
        logger.info(f"Spider closed: {spider.name}, reason: {reason}")
        self.stats.set_value('spider/end_time', datetime.now().isoformat())
        self.stats.set_value('spider/close_reason', reason)

        # 打印统计信息
        logger.info(f"Total requests: {self.stats.get_value('downloader/request_count', 0)}")
        logger.info(f"Total responses: {self.stats.get_value('downloader/response_count', 0)}")
        logger.info(f"Total items: {self.stats.get_value('item_scraped_count', 0)}")

    def spider_idle(self, spider):
        """Spider 空闲时"""
        logger.info(f"Spider idle: {spider.name}")
