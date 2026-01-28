"""
数据库连接和操作 v2.0 - 支持政策关联关系和质量追踪
根据《共享CFO - 爬虫模块需求文档 v3.0》设计
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pymongo import MongoClient, IndexModel, ASCENDING, TEXT, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError
from urllib.parse import quote_plus

from .config import mongo_config
from .data_models_v2 import (
    PolicyDocument, CrawlTask, PolicyRelationship,
    DataQualityReport, DocumentLevel, TaxCategory, ValidityStatus
)


class MongoDBConnectorV2:
    """
    MongoDB连接器 v2.0
    支持政策层级、关联关系、质量追踪
    """

    def __init__(self, host=None, port=None, username=None, password=None, database=None):
        self.logger = logging.getLogger("MongoDBV2")

        # 构建连接URI
        host = host or mongo_config.host
        port = port or mongo_config.port
        username = username or mongo_config.username
        password = password or mongo_config.password
        database = database or mongo_config.database

        if username and password:
            encoded_password = quote_plus(password)
            uri = f"mongodb://{username}:{encoded_password}@{host}:{port}/{database}?authSource=admin"
        else:
            uri = f"mongodb://{host}:{port}/{database}"

        self.client = MongoClient(uri)
        self.db = self.client[database]
        self.collection = self.db['policies']
        self.relationships_collection = self.db['policy_relationships']
        self.updates_collection = self.db['policy_updates']
        self.tasks_collection = self.db['crawl_tasks']

        # 初始化索引
        self._ensure_indexes()

    def _ensure_indexes(self):
        """创建必要的索引"""
        # 政策集合索引
        policy_indexes = [
            # 唯一索引
            IndexModel([("policy_id", ASCENDING)], unique=True),
            IndexModel([("url", ASCENDING)], unique=True),  # URL去重

            # 层级和分类索引（用于按层级检索）
            IndexModel([("document_level", ASCENDING)]),
            IndexModel([("document_type", ASCENDING)]),
            IndexModel([("tax_category", ASCENDING)]),
            IndexModel([("tax_type", ASCENDING)]),
            IndexModel([("region", ASCENDING)]),

            # 时效性索引
            IndexModel([("validity_status", ASCENDING)]),
            IndexModel([("publish_date", DESCENDING)]),
            IndexModel([("effective_date", ASCENDING)]),
            IndexModel([("expiry_date", ASCENDING)]),

            # 关联关系索引（用于查找上下级政策）
            IndexModel([("parent_policy_id", ASCENDING)]),
            IndexModel([("root_law_id", ASCENDING)]),
            IndexModel([("policy_group", ASCENDING)]),

            # 质量评分索引
            IndexModel([("quality_score", DESCENDING)]),
            IndexModel([("quality_level", ASCENDING)]),

            # 文本搜索索引
            IndexModel([("title", TEXT), ("content", TEXT), ("summary", TEXT)]),

            # 国际税收索引
            IndexModel([("counterpart_country", ASCENDING)]),
            IndexModel([("treaty_type", ASCENDING)]),
        ]

        # 关联关系集合索引
        relationship_indexes = [
            IndexModel([("child_id", ASCENDING), ("parent_id", ASCENDING)]),
            IndexModel([("parent_id", ASCENDING)]),
            IndexModel([("relationship_type", ASCENDING)]),
        ]

        try:
            self.collection.create_indexes(policy_indexes)
            self.relationships_collection.create_indexes(relationship_indexes)
            self.logger.info("Indexes created successfully")
        except PyMongoError as e:
            self.logger.error(f"Failed to create indexes: {e}")

    def insert_policy(self, policy: PolicyDocument) -> Tuple[bool, str]:
        """
        插入单条政策
        返回：(是否成功, 消息)
        """
        try:
            doc_dict = self._convert_policy_to_dict(policy)

            # 检查重复
            existing = self.collection.find_one({
                '$or': [
                    {'policy_id': policy.policy_id},
                    {'url': policy.url}
                ]
            })

            if existing:
                # 更新现有政策
                self.collection.update_one(
                    {'policy_id': policy.policy_id},
                    {'$set': {**doc_dict, 'updated_at': datetime.now()}}
                )
                self.logger.debug(f"Updated policy: {policy.title}")
                return True, "updated"
            else:
                # 插入新政策
                self.collection.insert_one(doc_dict)
                self.logger.debug(f"Inserted policy: {policy.title}")
                return True, "inserted"

        except DuplicateKeyError:
            return False, "duplicate"
        except PyMongoError as e:
            self.logger.error(f"Failed to insert policy: {e}")
            return False, str(e)

    def _convert_policy_to_dict(self, policy: PolicyDocument) -> Dict[str, Any]:
        """将PolicyDocument转换为字典"""
        doc_dict = policy.model_dump()

        # 处理日期类型
        date_fields = ['publish_date', 'effective_date', 'expiry_date',
                       'signed_date', 'crawled_at', 'updated_at']
        for field in date_fields:
            if doc_dict.get(field):
                doc_dict[field] = doc_dict[field].isoformat()

        # 处理枚举类型
        if doc_dict.get('document_level'):
            doc_dict['document_level'] = doc_dict['document_level'].value
        if doc_dict.get('document_type'):
            doc_dict['document_type'] = doc_dict['document_type'].value
        if doc_dict.get('tax_category'):
            doc_dict['tax_category'] = doc_dict['tax_category'].value
        if doc_dict.get('region'):
            doc_dict['region'] = doc_dict['region'].value
        if doc_dict.get('validity_status'):
            doc_dict['validity_status'] = doc_dict['validity_status'].value
        if doc_dict.get('tax_type'):
            doc_dict['tax_type'] = [t.value if hasattr(t, 'value') else t for t in doc_dict['tax_type']]

        # 处理KeyPoint对象
        if doc_dict.get('key_points'):
            doc_dict['key_points'] = [
                kp if isinstance(kp, dict) else {'point': kp.point, 'reference': kp.reference}
                for kp in doc_dict['key_points']
            ]

        # 处理QAPair对象
        if doc_dict.get('qa_pairs'):
            doc_dict['qa_pairs'] = [
                qa if isinstance(qa, dict) else {'question': qa.question, 'answer': qa.answer, 'question_type': qa.question_type}
                for qa in doc_dict['qa_pairs']
            ]

        return doc_dict

    def insert_policies(self, policies: List[PolicyDocument]) -> Dict[str, int]:
        """批量插入政策"""
        stats = {
            'success': 0,
            'updated': 0,
            'duplicate': 0,
            'failed': 0,
        }

        for policy in policies:
            success, msg = self.insert_policy(policy)
            if success:
                if msg == "inserted":
                    stats['success'] += 1
                else:
                    stats['updated'] += 1
            elif msg == "duplicate":
                stats['duplicate'] += 1
            else:
                stats['failed'] += 1

        self.logger.info(f"Batch insert completed: {stats}")
        return stats

    def find_by_id(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """根据ID查找政策"""
        return self.collection.find_one({'policy_id': policy_id})

    def find_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """根据URL查找政策"""
        return self.collection.find_one({'url': url})

    def find_by_document_number(self, document_number: str) -> Optional[Dict[str, Any]]:
        """根据发文字号查找政策"""
        return self.collection.find_one({'document_number': document_number})

    def find_by_level(self, level: DocumentLevel, limit: int = 100) -> List[Dict[str, Any]]:
        """根据层级查找政策"""
        return list(self.collection.find({'document_level': level.value}).limit(limit))

    def find_by_category(self, category: TaxCategory, limit: int = 100) -> List[Dict[str, Any]]:
        """根据税收类别查找政策"""
        return list(self.collection.find({'tax_category': category.value}).limit(limit))

    def find_children(self, parent_policy_id: str) -> List[Dict[str, Any]]:
        """查找下位政策"""
        return list(self.collection.find({'parent_policy_id': parent_policy_id}))

    def find_by_legislation_chain(self, root_law_id: str) -> List[Dict[str, Any]]:
        """根据根本法律查找整个立法链路"""
        return list(self.collection.find({'root_law_id': root_law_id}))

    def find_related_policies(self, policy_id: str) -> List[Dict[str, Any]]:
        """查找相关政策"""
        policy = self.find_by_id(policy_id)
        if not policy or not policy.get('related_policy_ids'):
            return []

        related_ids = policy['related_policy_ids']
        return list(self.collection.find({'policy_id': {'$in': related_ids}}))

    def search_policies(self, keyword: str, limit: int = 20,
                       filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        全文搜索政策，支持过滤

        filters: {
            'document_level': 'L1',
            'tax_category': '实体税',
            'tax_type': ['增值税', '企业所得税'],
            'region': '全国',
            'validity_status': '有效'
        }
        """
        query = {'$text': {'$search': keyword}}

        # 添加过滤条件
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    query[key] = {'$in': value}
                else:
                    query[key] = value

        results = self.collection.find(
            query,
            {'score': {'$meta': 'textScore'}}
        ).sort([('score', {'$meta': 'textScore'})]).limit(limit)

        return list(results)

    def get_legislation_chain(self, policy_id: str) -> List[Dict[str, Any]]:
        """
        获取完整的立法链路
        返回从根本法律到当前政策的完整路径
        """
        policy = self.find_by_id(policy_id)
        if not policy:
            return []

        chain_ids = policy.get('legislation_chain', [])
        if not chain_ids:
            return []

        # 按立法链路顺序查找
        chain = []
        for cid in chain_ids:
            p = self.find_by_id(cid)
            if p:
                chain.append(p)

        return chain

    def update_policy_relationships(self, child_id: str, parent_id: str,
                                   relationship_type: str = "legislation"):
        """更新政策关联关系"""
        try:
            # 更新子政策的parent_id
            self.collection.update_one(
                {'policy_id': child_id},
                {'$set': {'parent_policy_id': parent_id}}
            )

            # 更新父政策的cited_by
            self.collection.update_one(
                {'policy_id': parent_id},
                {'$addToSet': {'cited_by_policy_ids': child_id}}
            )

            # 记录到关联关系集合
            self.relationships_collection.update_one(
                {'child_id': child_id, 'parent_id': parent_id},
                {'$set': {
                    'relationship_type': relationship_type,
                    'updated_at': datetime.now()
                }},
                upsert=True
            )

            return True
        except PyMongoError as e:
            self.logger.error(f"Failed to update relationship: {e}")
            return False

    def build_legislation_chain(self, policy_id: str) -> bool:
        """
        构建完整的立法链路
        从当前政策向上追溯到根本法律
        """
        try:
            chain = []
            current_id = policy_id

            while current_id:
                policy = self.find_by_id(current_id)
                if not policy:
                    break

                chain.append(current_id)
                current_id = policy.get('parent_policy_id')

                # 防止循环引用
                if current_id in chain:
                    break

            # 更新所有链路上政策的立法链路字段
            root_id = chain[-1] if chain else None

            for cid in chain:
                self.collection.update_one(
                    {'policy_id': cid},
                    {'$set': {
                        'legislation_chain': chain,
                        'root_law_id': root_id
                    }}
                )

            return True
        except PyMongoError as e:
            self.logger.error(f"Failed to build legislation chain: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.collection.count_documents({})

        # 按层级统计
        level_stats = self.collection.aggregate([
            {'$group': {'_id': '$document_level', 'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ])

        # 按类别统计
        category_stats = self.collection.aggregate([
            {'$group': {'_id': '$tax_category', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ])

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

        # 按来源统计
        source_stats = self.collection.aggregate([
            {'$group': {'_id': '$source', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ])

        # 时效性统计
        validity_stats = self.collection.aggregate([
            {'$group': {'_id': '$validity_status', 'count': {'$sum': 1}}}
        ])

        return {
            'total': total,
            'by_level': {s['_id']: s['count'] for s in level_stats},
            'by_category': {s['_id']: s['count'] for s in category_stats},
            'by_tax_type': {s['_id']: s['count'] for s in tax_type_stats},
            'by_region': {s['_id']: s['count'] for s in region_stats},
            'by_source': {s['_id']: s['count'] for s in source_stats},
            'by_validity': {s['_id']: s['count'] for s in validity_stats},
        }

    def get_quality_report(self) -> DataQualityReport:
        """生成数据质量报告"""
        total = self.collection.count_documents({})

        # 按层级统计
        by_level = {}
        for level in ['L1', 'L2', 'L3', 'L4']:
            count = self.collection.count_documents({'document_level': level})
            by_level[level] = count

        # 按类别统计
        by_category = {}
        for cat in ['实体税', '程序税', '国际税收']:
            count = self.collection.count_documents({'tax_category': cat})
            by_category[cat] = count

        # 完整性分数：必填字段齐全度
        total_with_fields = self.collection.count_documents({
            'title': {'$exists': True, '$ne': ''},
            'source': {'$exists': True, '$ne': ''},
            'document_level': {'$exists': True},
            'document_type': {'$exists': True},
            'tax_category': {'$exists': True},
        })
        completeness_score = (total_with_fields / total * 100) if total > 0 else 0

        # 权威性分数：L1+L2层级政策占比
        l1_l2_count = by_level.get('L1', 0) + by_level.get('L2', 0)
        authority_score = (l1_l2_count / total * 100) if total > 0 else 0

        # 关联性分数：有parent_policy_id的政策占比
        with_parent = self.collection.count_documents({
            'parent_policy_id': {'$exists': True, '$ne': None, '$ne': ''}
        })
        relationship_score = (with_parent / total * 100) if total > 0 else 0

        # 时效性分数：有validity_status的政策占比
        with_validity = self.collection.count_documents({
            'validity_status': {'$exists': True}
        })
        timeliness_score = (with_validity / total * 100) if total > 0 else 0

        # 内容质量分数：内容长度>500的政策占比
        with_long_content = self.collection.count_documents({
            'content': {'$exists': True, '$regex': r'^.{500,}$', '$options': 'i'}
        })
        content_quality_score = (with_long_content / total * 100) if total > 0 else 0

        # 总体质量等级
        overall_score = (
            completeness_score * 0.25 +
            authority_score * 0.30 +
            relationship_score * 0.20 +
            timeliness_score * 0.15 +
            content_quality_score * 0.10
        )

        if overall_score >= 90:
            quality_level = 'A'
        elif overall_score >= 75:
            quality_level = 'B'
        elif overall_score >= 60:
            quality_level = 'C'
        else:
            quality_level = 'D'

        # 发现问题
        issues = []
        if completeness_score < 95:
            issues.append(f"完整性不足：{completeness_score:.1f}% < 95%")
        if relationship_score < 80:
            issues.append(f"关联关系缺失：{relationship_score:.1f}% < 80%")
        if l1_l2_count < 30:
            issues.append(f"L1+L2层级政策不足：{l1_l2_count}条 < 30条")

        return DataQualityReport(
            total_policies=total,
            by_level=by_level,
            by_category=by_category,
            completeness_score=completeness_score,
            authority_score=authority_score,
            relationship_score=relationship_score,
            timeliness_score=timeliness_score,
            content_quality_score=content_quality_score,
            overall_quality_level=quality_level,
            issues=issues
        )

    def save_crawl_task(self, task: CrawlTask) -> bool:
        """保存爬取任务"""
        try:
            doc_dict = task.model_dump()

            # 处理日期类型
            if doc_dict.get('start_time'):
                doc_dict['start_time'] = doc_dict['start_time'].isoformat()
            if doc_dict.get('end_time'):
                doc_dict['end_time'] = doc_dict['end_time'].isoformat()

            self.tasks_collection.update_one(
                {'task_id': task.task_id},
                {'$set': doc_dict},
                upsert=True
            )
            return True
        except PyMongoError as e:
            self.logger.error(f"Failed to save crawl task: {e}")
            return False

    def update_crawl_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        """更新爬取任务"""
        try:
            result = self.tasks_collection.update_one(
                {'task_id': task_id},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            self.logger.error(f"Failed to update crawl task {task_id}: {e}")
            return False

    def get_crawl_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取爬取任务"""
        return self.tasks_collection.find_one({'task_id': task_id})

    def get_all_crawl_tasks(self) -> List[Dict[str, Any]]:
        """获取所有爬取任务"""
        return list(self.tasks_collection.find().sort('start_time', DESCENDING))

    def close(self):
        """关闭连接"""
        self.client.close()
        self.logger.info("MongoDB connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
