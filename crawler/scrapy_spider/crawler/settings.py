"""
Scrapy 爬虫配置
针对政府税务政策网站的优化配置
"""

import os
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Scrapy 项目设置
BOT_NAME = 'crawler.scrapy_spider'

SPIDER_MODULES = ['crawler.scrapy_spider.crawler.spiders']
NEWSPIDER_MODULE = 'crawler.scrapy_spider.crawler.spiders'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SharedCFO-Bot/1.0 (+https://sharedcfo.cn/bot)'

# 遵守 robots.txt 规则
ROBOTSTXT_OBEY = True

# 配置并发请求数 - 政府网站需要保守设置
CONCURRENT_REQUESTS = 5
CONCURRENT_REQUESTS_PER_DOMAIN = 3

# 下载延迟 - 重要：政府网站必须有足够延迟
DOWNLOAD_DELAY = 3
# 随机化延迟，避免检测
RANDOMIZE_DOWNLOAD_DELAY = True

# 禁用 cookies（大多数政府网站不需要）
COOKIES_ENABLED = False

# 禁用 Telnet Console
TELNETCONSOLE_ENABLED = False

# 覆盖默认的请求头
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

# 启用或禁用蜘蛛中间件
SPIDER_MIDDLEWARES = {
    'crawler.scrapy_spider.crawler.middlewares.ComplianceMiddleware': 543,
    'scrapy.spidermiddlewares.offsite.OffsiteMiddleware': None,
}

# 启用或禁用下载器中间件
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware': 100,
    'scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware': 300,
    'scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware': 350,
    'scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware': 400,
    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': 600,
    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': 700,
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 750,
    'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 800,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 900,
    'scrapy.downloadermiddlewares.stats.DownloaderStats': 850,
}

# 重试设置
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [403, 429, 500, 502, 503, 504]

# 超时设置
DOWNLOAD_TIMEOUT = 30

# 启用或禁用扩展
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
}

# 配置项目管道
ITEM_PIPELINES = {
    'crawler.scrapy_spider.crawler.policies.MongoDBPipeline': 300,
    'crawler.scrapy_spider.crawler.policies.DataValidationPipeline': 350,
    'crawler.scrapy_spider.crawler.policies.DeduplicationPipeline': 400,
}

# 启用和配置自动限制扩展
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# 启用和配置 HTTP 缓存
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400  # 24小时
HTTPCACHE_DIR = PROJECT_ROOT / '.scrapy_cache'
HTTPCACHE_IGNORE_HTTP_CODES = [403, 404, 500, 503]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# 日志设置
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'
LOG_FILE = str(PROJECT_ROOT.parent.parent / 'logs' / 'scrapy_crawler.log')

# Feed 导出设置
FEEDS = {
    'output/%(name)s_%(time)s.json': {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'fields': None,
        'indent': 2,
    },
}

# MongoDB 设置（从环境变量读取）
MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.getenv('MONGO_PORT', 27017))
MONGO_USERNAME = os.getenv('MONGO_USERNAME', '')
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', '')
MONGO_DATABASE = os.getenv('MONGO_DATABASE', 'shared_cfo')
MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'policies')

# 请求限流配置
CLOSESPIDER_TIMEOUT = 3600  # 1小时后自动关闭
CLOSESPIDER_PAGECOUNT = 1000  # 最多爬取1000页（测试阶段）
CLOSESPIDER_ERRORCOUNT = 50  # 50个错误后关闭

# User-Agent 池（可选，用于反爬）
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
]

# 确保输出目录存在
(Path(PROJECT_ROOT.parent.parent / 'logs')).mkdir(exist_ok=True)
(Path(PROJECT_ROOT / 'output')).mkdir(exist_ok=True)
