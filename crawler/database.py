"""
数据库连接和操作
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo import MongoClient, IndexModel, ASCENDING, TEXT
from pymongo.errors import DuplicateKeyError, PyMongoError

from .config import mongo_config
from .data_models import PolicyDocument, CrawlTask


class MongoDBConnector:
    """MongoDB连接器"""

    def __init__(self):
        self.logger = logging.getLogger("MongoDB")

        # 构建连接URI
        if mongo_config.username and mongo_config.password:
            uri = f"mongodb://{mongo_config.username}:{mongo_config.password}@{mongo_config.host}:{mongo_config.port}/{mongo_config.database}"
        else:
            uri = f"mongodb://{mongo_config.host}:{mongo_config.port}/{mongo_config.database}"

        self.client = MongoClient(uri)
        self.db = self.client[mongo_config.database]
        self.collection = self.db[mongo_config.collection]

        # 初始化索引
        self._ensure_indexes()

    def _ensure_indexes(self):
        """创建必要的索引"""
        indexes = [
            # 唯一索引：policy_id
            IndexModel([("policy_id", ASCENDING)], unique=True),
            # 文本索引：用于全文搜索
            IndexModel([("title", TEXT), ("content", TEXT)]),
            # 单字段索引
            IndexModel([("source", ASCENDING)]),
            IndexModel([("publish_date", ASCENDING)]),
            IndexModel([("tax_type", ASCENDING)]),
            IndexModel([("region", ASCENDING)]),
            IndexModel([("crawled_at", ASCENDING)]),
        ]

        try:
            self.collection.create_indexes(indexes)
            self.logger.info("Indexes created successfully")
        except PyMongoError as e:
            self.logger.error(f"Failed to create indexes: {e}")

    def insert_policy(self, policy: PolicyDocument) -> bool:
        """插入单条政策"""
        try:
            doc_dict = policy.model_dump()

            # 处理日期类型
            if doc_dict.get('publish_date'):
                doc_dict['publish_date'] = doc_dict['publish_date'].isoformat()
            if doc_dict.get('effective_date'):
                doc_dict['effective_date'] = doc_dict['effective_date'].isoformat()
            if doc_dict.get('expiry_date'):
                doc_dict['expiry_date'] = doc_dict['expiry_date'].isoformat()
            if doc_dict.get('crawled_at'):
                doc_dict['crawled_at'] = doc_dict['crawled_at'].isoformat()

            # 处理枚举类型
            if doc_dict.get('document_type'):
                doc_dict['document_type'] = doc_dict['document_type'].value
            if doc_dict.get('region'):
                doc_dict['region'] = doc_dict['region'].value
            if doc_dict.get('tax_type'):
                doc_dict['tax_type'] = [t.value for t in doc_dict['tax_type']]

            self.collection.insert_one(doc_dict)
            self.logger.debug(f"Inserted policy: {policy.title}")
            return True
        except DuplicateKeyError:
            self.logger.debug(f"Policy already exists: {policy.policy_id}")
            return False
        except PyMongoError as e:
            self.logger.error(f"Failed to insert policy: {e}")
            return False

    def insert_policies(self, policies: List[PolicyDocument]) -> Dict[str, int]:
        """批量插入政策"""
        stats = {
            'success': 0,
            'duplicate': 0,
            'failed': 0,
        }

        for policy in policies:
            if self.insert_policy(policy):
                stats['success'] += 1
            elif self.collection.find_one({'policy_id': policy.policy_id}):
                stats['duplicate'] += 1
            else:
                stats['failed'] += 1

        self.logger.info(f"Batch insert completed: {stats}")
        return stats

    def update_policy(self, policy_id: str, update_data: Dict[str, Any]) -> bool:
        """更新政策"""
        try:
            result = self.collection.update_one(
                {'policy_id': policy_id},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            self.logger.error(f"Failed to update policy {policy_id}: {e}")
            return False

    def find_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """根据ID查找政策"""
        return self.collection.find_one({'policy_id': policy_id})

    def find_policies(
        self,
        query: Dict[str, Any] = None,
        limit: int = 100,
        skip: int = 0,
        sort: List[tuple] = None
    ) -> List[Dict[str, Any]]:
        """查找政策"""
        cursor = self.collection.find(query or {}).skip(skip).limit(limit)

        if sort:
            cursor = cursor.sort(sort)

        return list(cursor)

    def search_policies(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """全文搜索政策"""
        results = self.collection.find(
            {'$text': {'$search': keyword}},
            {'score': {'$meta': 'textScore'}}
        ).sort([('score', {'$meta': 'textScore'})]).limit(limit)

        return list(results)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pipeline = [
            {
                '$group': {
                    '_id': '$source',
                    'count': {'$sum': 1}
                }
            },
            {
                '$sort': {'count': -1}
            }
        ]

        stats_by_source = list(self.collection.aggregate(pipeline))

        total = self.collection.count_documents({})

        # 按税种统计
        tax_type_stats = self.collection.aggregate([
            {'$unwind': '$tax_type'},
            {'$group': {'_id': '$tax_type', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ])

        # 按地区统计
        region_stats = self.collection.aggregate([
            {'$group': {'_id': '$region', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ])

        return {
            'total': total,
            'by_source': stats_by_source,
            'by_tax_type': list(tax_type_stats),
            'by_region': list(region_stats),
        }

    def get_crawl_tasks(self) -> List[Dict[str, Any]]:
        """获取所有爬取任务"""
        tasks = self.db['crawl_tasks'].find()
        return list(tasks)

    def save_crawl_task(self, task: CrawlTask) -> bool:
        """保存爬取任务"""
        try:
            doc_dict = task.model_dump()

            # 处理日期类型
            if doc_dict.get('start_time'):
                doc_dict['start_time'] = doc_dict['start_time'].isoformat()
            if doc_dict.get('end_time'):
                doc_dict['end_time'] = doc_dict['end_time'].isoformat()

            self.db['crawl_tasks'].insert_one(doc_dict)
            return True
        except PyMongoError as e:
            self.logger.error(f"Failed to save crawl task: {e}")
            return False

    def update_crawl_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        """更新爬取任务"""
        try:
            result = self.db['crawl_tasks'].update_one(
                {'task_id': task_id},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            self.logger.error(f"Failed to update crawl task {task_id}: {e}")
            return False

    def close(self):
        """关闭连接"""
        self.client.close()
        self.logger.info("MongoDB connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class QdrantConnector:
    """Qdrant向量数据库连接器"""

    def __init__(self):
        self.logger = logging.getLogger("Qdrant")
        # TODO: 实现Qdrant连接
        # from qdrant_client import QdrantClient
        # self.client = QdrantClient(
        #     host=qdrant_config.host,
        #     port=qdrant_config.port
        # )
        # self.collection_name = qdrant_config.collection_name

    def insert_policy(self, policy: PolicyDocument, vector: List[float]):
        """插入向量化的政策"""
        # TODO: 实现向量插入
        pass

    def search_similar(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        # TODO: 实现向量搜索
        return []

    def close(self):
        """关闭连接"""
        pass
