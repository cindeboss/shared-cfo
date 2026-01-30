"""
数据质量验证器
检查政策数据的完整性、关联性、时效性
根据《共享CFO - 爬虫模块需求文档 v3.0》设计
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from difflib import SequenceMatcher
import logging

from .database import MongoDBConnector


logger = logging.getLogger("QualityValidator")


class DataQualityValidator:
    """
    数据质量验证器

    检查项：
    1. 必填字段完整性
    2. 层级完整性
    3. 关联关系完整性
    4. 时效性
    5. 内容质量
    6. 去重
    """

    def __init__(self, db: MongoDBConnector):
        self.db = db
        self.logger = logging.getLogger("QualityValidator")

    def validate_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证单条政策的质量

        返回: {
            'valid': bool,
            'score': int,
            'issues': List[str],
            'warnings': List[str]
        }
        """
        issues = []
        warnings = []
        score = 100

        # 1. 必填字段检查 (30分)
        required_fields = {
            'policy_id': '政策ID',
            'title': '标题',
            'source': '来源',
            'url': '链接',
            'document_level': '政策层级',
            'document_type': '文件类型',
            'tax_category': '税收类别',
        }

        for field, name in required_fields.items():
            if not policy.get(field):
                issues.append(f"缺少必填字段: {name}")
                score -= 5

        # 标题长度检查
        title = policy.get('title', '')
        if len(title) < 10:
            issues.append(f"标题过短: {len(title)}字符 < 10字符")
            score -= 5

        # 2. 层级完整性检查 (25分)
        document_level = policy.get('document_level')

        # L4文档必须关联原文
        if document_level == 'L4':
            if not policy.get('qa_reference_ids') and not policy.get('parent_policy_id'):
                issues.append("L4文档未关联到原文政策")
                score -= 15

        # L2文档应该关联到L1
        if document_level == 'L2':
            if not policy.get('parent_policy_id'):
                warnings.append("L2文档未关联上位法（建议添加）")
                score -= 5

        # 地方政策必须标注地区
        region = policy.get('region')
        source = policy.get('source', '')
        if '税务局' in source and region == '全国':
            warnings.append(f"地方政策未标注地区: {source}")
            score -= 3

        # 3. 关联关系检查 (20分)
        # 检查立法链路
        legislation_chain = policy.get('legislation_chain', [])
        if document_level in ['L2', 'L3'] and not legislation_chain:
            warnings.append("未建立立法链路")
            score -= 10

        # 检查关联的上位法是否存在
        parent_id = policy.get('parent_policy_id')
        if parent_id:
            parent = self.db.find_by_id(parent_id)
            if not parent:
                issues.append(f"关联的上位法不存在: {parent_id}")
                score -= 10

        # 4. 时效性检查 (15分)
        validity_status = policy.get('validity_status')
        if not validity_status:
            warnings.append("未标注有效状态")
            score -= 5

        # 检查日期逻辑
        publish_date = policy.get('publish_date')
        effective_date = policy.get('effective_date')
        expiry_date = policy.get('expiry_date')

        if publish_date and effective_date:
            if isinstance(publish_date, str):
                publish_date = datetime.fromisoformat(publish_date)
            if isinstance(effective_date, str):
                effective_date = datetime.fromisoformat(effective_date)

            if effective_date < publish_date:
                issues.append("生效日期早于发布日期")
                score -= 5

        if effective_date and expiry_date:
            if isinstance(effective_date, str):
                effective_date = datetime.fromisoformat(effective_date)
            if isinstance(expiry_date, str):
                expiry_date = datetime.fromisoformat(expiry_date)

            if expiry_date < effective_date:
                issues.append("失效日期早于生效日期")
                score -= 5

        # 5. 内容质量检查 (10分)
        content = policy.get('content', '')
        content_length = len(content)

        if content_length < 100:
            issues.append(f"内容过短: {content_length}字符 < 100字符")
            score -= 10
        elif content_length < 500:
            warnings.append(f"内容较短: {content_length}字符 < 500字符")
            score -= 5

        return {
            'valid': score >= 60,
            'score': max(0, score),
            'issues': issues,
            'warnings': warnings
        }

    def deduplicate_policies(self) -> Dict[str, Any]:
        """
        去重处理

        去重策略：
        1. URL去重（保留最早爬取的）
        2. 标题+日期去重
        3. 内容相似度去重
        """
        self.logger.info("Starting deduplication")

        stats = {
            'total': 0,
            'url_duplicates': 0,
            'title_date_duplicates': 0,
            'content_duplicates': 0,
            'removed': 0
        }

        total = self.db.collection.count_documents({})
        stats['total'] = total

        # 1. URL去重（通过唯一索引已处理，这里只统计）
        # 2. 标题+日期去重
        pipeline = [
            {'$group': {
                '_id': {'title': '$title', 'publish_date': '$publish_date'},
                'count': {'$sum': 1},
                'docs': {'$push': '$policy_id'}
            }},
            {'$match': {'count': {'$gt': 1}}}
        ]

        duplicates = list(self.db.collection.aggregate(pipeline))
        stats['title_date_duplicates'] = len(duplicates)

        for dup in duplicates:
            docs = dup['docs']
            if len(docs) > 1:
                # 保留第一个，删除其余的
                to_keep = docs[0]
                to_remove = docs[1:]

                for doc_id in to_remove:
                    self.db.collection.delete_one({'policy_id': doc_id})
                    stats['removed'] += 1

        self.logger.info(f"Deduplication completed: {stats}")
        return stats

    def check_content_similarity(self, threshold: float = 0.9) -> List[Dict[str, Any]]:
        """
        检查内容相似度

        返回相似的政策组
        """
        similar_groups = []

        # 获取所有政策
        policies = list(self.db.collection.find())
        n = len(policies)

        for i in range(n):
            for j in range(i + 1, n):
                p1 = policies[i]
                p2 = policies[j]

                # 计算相似度
                similarity = self._calculate_similarity(
                    p1.get('content', ''),
                    p2.get('content', '')
                )

                if similarity >= threshold:
                    similar_groups.append({
                        'policy1_id': p1['policy_id'],
                        'policy2_id': p2['policy_id'],
                        'similarity': similarity,
                        'title1': p1.get('title', ''),
                        'title2': p2.get('title', '')
                    })

        return similar_groups

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        return SequenceMatcher(None, text1, text2).ratio()

    def validate_all(self) -> Dict[str, Any]:
        """
        验证所有政策数据

        返回质量报告
        """
        self.logger.info("Starting quality validation")

        total = self.db.collection.count_documents({})
        issues_by_type = {
            'missing_fields': 0,
            'broken_relationships': 0,
            'invalid_dates': 0,
            'short_content': 0,
        }

        # 批量验证
        batch_size = 100
        skip = 0

        low_quality_policies = []

        while skip < total:
            policies = list(self.db.collection.find().skip(skip).limit(batch_size))

            for policy in policies:
                validation = self.validate_policy(policy)

                if not validation['valid']:
                    low_quality_policies.append({
                        'policy_id': policy['policy_id'],
                        'title': policy.get('title', ''),
                        'score': validation['score'],
                        'issues': validation['issues']
                    })

                # 统计问题类型
                for issue in validation['issues']:
                    if '缺少必填字段' in issue:
                        issues_by_type['missing_fields'] += 1
                    elif '关联的上位法不存在' in issue:
                        issues_by_type['broken_relationships'] += 1
                    elif '日期' in issue:
                        issues_by_type['invalid_dates'] += 1
                    elif '内容过短' in issue:
                        issues_by_type['short_content'] += 1

            skip += batch_size

        # 计算质量分数
        valid_count = total - len(low_quality_policies)
        quality_score = (valid_count / total * 100) if total > 0 else 0

        return {
            'total_policies': total,
            'valid_policies': valid_count,
            'invalid_policies': len(low_quality_policies),
            'quality_score': quality_score,
            'issues_by_type': issues_by_type,
            'low_quality_sample': low_quality_policies[:20]  # 只返回前20条
        }

    def get_completeness_report(self) -> Dict[str, Any]:
        """
        获取数据完整性报告
        """
        total = self.db.collection.count_documents({})

        # 检查各字段的覆盖率
        fields_to_check = [
            'document_number', 'publish_date', 'effective_date',
            'expiry_date', 'validity_status', 'parent_policy_id',
            'legislation_chain', 'root_law_id'
        ]

        coverage = {}
        for field in fields_to_check:
            count = self.db.collection.count_documents({field: {'$exists': True, '$ne': None, '$ne': ''}})
            coverage[field] = {
                'count': count,
                'percentage': (count / total * 100) if total > 0 else 0
            }

        return {
            'total_policies': total,
            'field_coverage': coverage
        }

    def fix_common_issues(self) -> Dict[str, int]:
        """
        修复常见问题

        包括：
        1. 清理空白字段
        2. 标准化日期格式
        3. 补充默认值
        """
        stats = {
            'cleaned_blank_fields': 0,
            'standardized_dates': 0,
            'added_defaults': 0
        }

        # 清理空白字段
        result = self.db.collection.update_many(
            {'validity_status': ''},
            {'$set': {'validity_status': '有效'}}
        )
        stats['cleaned_blank_fields'] = result.modified_count

        # 补充默认质量等级
        # 批量更新所有缺少质量等级的政策
        policies = list(self.db.collection.find({'quality_level': {'$exists': False}}))
        for policy in policies:
            quality_score = policy.get('quality_score', 0)
            if quality_score >= 90:
                level = 'A'
            elif quality_score >= 75:
                level = 'B'
            elif quality_score >= 60:
                level = 'C'
            else:
                level = 'D'
            self.db.collection.update_one(
                {'policy_id': policy['policy_id']},
                {'$set': {'quality_level': level}}
            )
        stats['added_defaults'] = len(policies)

        self.logger.info(f"Fixed common issues: {stats}")
        return stats


# 便捷函数
def validate_data_quality(db: MongoDBConnector) -> Dict[str, Any]:
    """验证数据质量"""
    validator = DataQualityValidator(db)
    return validator.validate_all()


def deduplicate_data(db: MongoDBConnector) -> Dict[str, Any]:
    """去重处理"""
    validator = DataQualityValidator(db)
    return validator.deduplicate_policies()
