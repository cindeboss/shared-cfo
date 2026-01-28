"""
Scrapy 数据处理管道
"""

import logging
import hashlib
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class MongoDBPipeline:
    """
    MongoDB 存储管道
    将爬取的数据保存到 MongoDB
    """

    def __init__(self, mongo_uri, mongo_db, mongo_collection):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection

    @classmethod
    def from_crawler(cls, crawler):
        """从 Scrapy settings 配置"""
        mongo_host = crawler.settings.get('MONGO_HOST', 'localhost')
        mongo_port = crawler.settings.get('MONGO_PORT', 27017)
        mongo_user = crawler.settings.get('MONGO_USERNAME', '')
        mongo_pass = crawler.settings.get('MONGO_PASSWORD', '')
        mongo_db = crawler.settings.get('MONGO_DATABASE', 'shared_cfo')
        mongo_collection = crawler.settings.get('MONGO_COLLECTION', 'policies')

        # 构建 MongoDB URI
        if mongo_user and mongo_pass:
            mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:{mongo_port}/{mongo_db}"
        else:
            mongo_uri = f"mongodb://{mongo_host}:{mongo_port}/{mongo_db}"

        return cls(mongo_uri, mongo_db, mongo_collection)

    def open_spider(self, spider):
        """Spider 启动时打开连接"""
        self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[self.mongo_db]
        self.collection = self.db[self.mongo_collection]

        # 创建索引
        self._create_indexes()

        logger.info(f"MongoDB 连接成功: {self.mongo_db}.{self.mongo_collection}")

    def _create_indexes(self):
        """创建必要的索引"""
        try:
            self.collection.create_index([('policy_id', 1)], unique=True)
            self.collection.create_index([('url', 1)])
            self.collection.create_index([('source', 1)])
            self.collection.create_index([('publish_date', -1)])
            self.collection.create_index([('level', 1)])
            logger.info("MongoDB 索引创建完成")
        except Exception as e:
            logger.warning(f"索引创建失败: {e}")

    def process_item(self, item, spider):
        """处理并保存 item"""
        try:
            # 生成 policy_id（如果没有）
            if not item.get('policy_id'):
                item['policy_id'] = self._generate_policy_id(item)

            # 添加爬取时间
            if not item.get('crawled_at'):
                item['crawled_at'] = datetime.now().isoformat()

            # 添加爬虫版本
            if not item.get('crawler_version'):
                item['crawler_version'] = 'scrapy-1.0'

            # 转换为字典
            document = dict(item)

            # 保存到 MongoDB
            try:
                self.collection.insert_one(document)
                logger.debug(f"保存成功: {item.get('title', 'N/A')}")
            except DuplicateKeyError:
                # 已存在，更新
                self.collection.update_one(
                    {'policy_id': item['policy_id']},
                    {'$set': document}
                )
                logger.debug(f"更新成功: {item.get('title', 'N/A')}")

        except Exception as e:
            logger.error(f"保存失败: {e}")
            raise DropItem(f"保存到 MongoDB 失败: {e}")

        return item

    def _generate_policy_id(self, item):
        """生成唯一的 policy_id"""
        # 使用 URL + 标题生成哈希
        source_str = f"{item.get('url', '')}{item.get('title', '')}{item.get('publish_date', '')}"
        return hashlib.md5(source_str.encode('utf-8')).hexdigest()[:16]

    def close_spider(self, spider):
        """Spider 关闭时关闭连接"""
        self.client.close()
        logger.info("MongoDB 连接已关闭")


class DataValidationPipeline:
    """
    数据验证管道
    验证数据的完整性和有效性
    """

    def __init__(self):
        self.required_fields = ['title', 'url', 'source']

    def process_item(self, item, spider):
        """验证 item"""
        # 检查必填字段
        missing_fields = [f for f in self.required_fields if not item.get(f)]
        if missing_fields:
            raise DropItem(f"缺少必填字段: {missing_fields}")

        # 验证 URL 格式
        if not item.get('url', '').startswith('http'):
            raise DropItem(f"无效的 URL: {item.get('url')}")

        # 验证标题长度
        title = item.get('title', '')
        if len(title) < 5:
            raise DropItem(f"标题过短: {title}")

        return item


class DeduplicationPipeline:
    """
    去重管道
    防止重复数据
    """

    def __init__(self):
        self.seen_urls = set()
        self.seen_titles = set()

    def process_item(self, item, spider):
        """检查是否重复"""
        url = item.get('url')
        title = item.get('title')

        # URL 去重
        if url in self.seen_urls:
            raise DropItem(f"重复的 URL: {url}")

        # 标题+日期 去重
        title_date = f"{title}_{item.get('publish_date', '')}"
        if title_date in self.seen_titles:
            raise DropItem(f"重复的标题+日期: {title}")

        self.seen_urls.add(url)
        self.seen_titles.add(title_date)

        return item

    def close_spider(self, spider):
        """打印统计信息"""
        logger.info(f"去重统计: URLs={len(self.seen_urls)}, 标题={len(self.seen_titles)}")


class LoggingPipeline:
    """
    日志记录管道
    记录爬取的统计信息
    """

    def __init__(self):
        self.items_count = 0
        self.dropped_count = 0

    def process_item(self, item, spider):
        """记录 item"""
        self.items_count += 1

        if self.items_count % 100 == 0:
            logger.info(f"已处理 {self.items_count} 条数据")

        return item

    def close_spider(self, spider):
        """打印统计"""
        logger.info(f"处理完成: 成功={self.items_count}, 丢弃={self.dropped_count}")
