"""
政策关联关系构建器
自动建立政策之间的引用关系和立法链路
根据《共享CFO - 爬虫模块需求文档 v3.0》设计
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from .database import MongoDBConnector


logger = logging.getLogger("RelationshipBuilder")


class PolicyRelationshipBuilder:
    """
    政策关联关系构建器

    功能：
    1. 根据发文字号匹配上位法
    2. 从正文中提取引用的政策
    3. 构建完整的立法链路
    4. 建立相关政策关联（同一主题）
    """

    def __init__(self, db: MongoDBConnector):
        self.db = db
        self.logger = logging.getLogger("RelationshipBuilder")

        # 上位法映射表（人工配置，确保准确性）
        self.super_law_mapping = {
            # 增值税法规体系
            '增值税暂行条例': '中华人民共和国增值税暂行条例',  # 行政法规
            '中华人民共和国增值税暂行条例': '税收征收管理法',  # 上位法是征管法

            # 企业所得税法规体系
            '企业所得税法': '税收征收管理法',
            '企业所得税法实施条例': '企业所得税法',

            # 个人所得税法规体系
            '个人所得税法': '税收征收管理法',
            '个人所得税法实施条例': '个人所得税法',

            # 征管法体系
            '税收征收管理法实施细则': '税收征收管理法',
            '发票管理办法': '税收征收管理法',
        }

        # 税种到根本法律的映射
        self.tax_root_laws = {
            '增值税': '中华人民共和国增值税暂行条例',
            '企业所得税': '中华人民共和国企业所得税法',
            '个人所得税': '中华人民共和国个人所得税法',
            '征管程序': '中华人民共和国税收征收管理法',
            '房产税': '中华人民共和国房产税暂行条例',
            '契税': '中华人民共和国契税暂行条例',
            '印花税': '中华人民共和国印花税暂行条例',
        }

    def find_parent_policy(self, policy: Dict[str, Any]) -> Optional[str]:
        """
        查找政策的上位法

        策略：
        1. 检查预定义的上位法映射表
        2. 从正文中提取引用的政策
        3. 根据税种匹配根本法律
        """
        title = policy.get('title', '')
        content = policy.get('content', '')
        document_number = policy.get('document_number', '')

        # 策略1: 检查预定义映射
        for key, parent_title in self.super_law_mapping.items():
            if key in title:
                parent = self.db.collection.find_one({'title': {'$regex': parent_title}})
                if parent:
                    return parent['policy_id']

        # 策略2: 从正文中提取引用的政策
        cited_policies = self._extract_cited_policies(content)
        if cited_policies:
            # 找到被引用的政策中层级最高的作为上位法
            for cited_title in cited_policies:
                cited = self.db.collection.find_one({'title': {'$regex': cited_title}})
                if cited and cited.get('document_level') in ['L1', 'L2']:
                    return cited['policy_id']

        # 策略3: 根据税种匹配根本法律
        tax_types = policy.get('tax_type', [])
        for tax_type in tax_types:
            if tax_type in self.tax_root_laws:
                root_law_title = self.tax_root_laws[tax_type]
                root_law = self.db.collection.find_one({'title': {'$regex': root_law_title}})
                if root_law:
                    return root_law['policy_id']

        return None

    def _extract_cited_policies(self, content: str) -> List[str]:
        """从正文中提取被引用的政策标题"""
        cited = []

        # 匹配常见的引用模式
        patterns = [
            r'《([^》]{5,30}?法)》',
            r'《([^》]{5,40}?条例)》',
            r'《([^》]{5,40}?办法)》',
            r'《([^》]{5,40}?规定)》',
            r'《([^》]{5,40}?通知)》',
            r'《([^》]{5,40}?公告)》',
            r'根据([^，。]{5,40}?法)第',
            r'按照([^，。]{5,40}?条例)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            cited.extend(matches)

        # 去重
        return list(set(cited))

    def build_legislation_chain(self, policy_id: str) -> List[str]:
        """
        构建完整的立法链路
        从当前政策向上追溯到根本法律
        """
        chain = []
        current_id = policy_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            chain.append(current_id)

            policy = self.db.find_by_id(current_id)
            if not policy:
                break

            # 如果已有parent_policy_id，使用它
            parent_id = policy.get('parent_policy_id')
            if parent_id:
                current_id = parent_id
            else:
                # 否则尝试查找上位法
                parent_id = self.find_parent_policy(policy)
                if parent_id:
                    # 更新parent_policy_id
                    self.db.collection.update_one(
                        {'policy_id': current_id},
                        {'$set': {'parent_policy_id': parent_id}}
                    )
                    current_id = parent_id
                else:
                    break

        return chain

    def find_related_policies(self, policy: Dict[str, Any]) -> List[str]:
        """
        查找相关政策（同一主题）
        基于税种、关键词、政策类型等
        """
        related_ids = []

        title = policy.get('title', '')
        tax_types = policy.get('tax_type', [])
        document_level = policy.get('document_level')
        policy_id = policy.get('policy_id')

        # 同一税种的同层级政策
        if tax_types:
            related = self.db.collection.find({
                'policy_id': {'$ne': policy_id},
                'tax_type': {'$in': tax_types},
                'document_level': document_level
            }).limit(5)

            for r in related:
                related_ids.append(r['policy_id'])

        # 标题相似的政策
        keywords = self._extract_keywords(title)
        if keywords:
            for keyword in keywords:
                related = self.db.collection.find({
                    'policy_id': {'$ne': policy_id},
                    'title': {'$regex': keyword, '$options': 'i'}
                }).limit(3)

                for r in related:
                    if r['policy_id'] not in related_ids:
                        related_ids.append(r['policy_id'])

        return related_ids[:10]  # 限制数量

    def _extract_keywords(self, title: str) -> List[str]:
        """从标题中提取关键词"""
        keywords = []

        # 常见关键词
        common_keywords = [
            '增值税', '企业所得税', '个人所得税',
            '小规模纳税人', '一般纳税人',
            '研发费用', '专项附加扣除',
            '税收优惠', '减免税',
            '纳税申报', '发票管理',
        ]

        for kw in common_keywords:
            if kw in title:
                keywords.append(kw)

        return keywords

    def link_qa_to_policy(self, qa_policy: Dict[str, Any]) -> List[str]:
        """
        将问答关联到原文政策
        从问答内容中提取引用的政策
        """
        content = qa_policy.get('content', '')
        question = qa_policy.get('title', '')

        cited_policies = self._extract_cited_policies(content + ' ' + question)

        reference_ids = []
        for cited_title in cited_policies:
            policy = self.db.collection.find_one({'title': {'$regex': cited_title}})
            if policy:
                reference_ids.append(policy['policy_id'])

        return reference_ids

    def build_all_relationships(self, batch_size: int = 100) -> Dict[str, Any]:
        """
        构建所有政策的关联关系

        Args:
            batch_size: 每批处理的数量

        Returns:
            统计信息
        """
        self.logger.info("Starting to build policy relationships")

        stats = {
            'total': 0,
            'with_parent': 0,
            'with_chain': 0,
            'with_related': 0,
            'qa_linked': 0
        }

        # 获取所有需要处理的政策
        total = self.db.collection.count_documents({})
        self.logger.info(f"Total policies to process: {total}")

        skip = 0
        while skip < total:
            policies = list(self.db.collection.find().skip(skip).limit(batch_size))

            for policy in policies:
                policy_id = policy['policy_id']
                stats['total'] += 1

                # 1. 建立上位法关系
                if not policy.get('parent_policy_id'):
                    parent_id = self.find_parent_policy(policy)
                    if parent_id:
                        self.db.collection.update_one(
                            {'policy_id': policy_id},
                            {'$set': {'parent_policy_id': parent_id}}
                        )
                        stats['with_parent'] += 1

                # 2. 构建立法链路
                chain = self.build_legislation_chain(policy_id)
                if chain:
                    root_id = chain[-1] if chain else None
                    self.db.collection.update_one(
                        {'policy_id': policy_id},
                        {'$set': {
                            'legislation_chain': chain,
                            'root_law_id': root_id
                        }}
                    )
                    stats['with_chain'] += 1

                # 3. 建立相关政策的关联
                if policy.get('document_level') != 'L1':
                    related_ids = self.find_related_policies(policy)
                    if related_ids:
                        self.db.collection.update_one(
                            {'policy_id': policy_id},
                            {'$set': {'related_policy_ids': related_ids}}
                        )
                        stats['with_related'] += 1

                # 4. 对于L4问答，关联到原文
                if policy.get('document_level') == 'L4':
                    reference_ids = self.link_qa_to_policy(policy)
                    if reference_ids:
                        self.db.collection.update_one(
                            {'policy_id': policy_id},
                            {'$set': {'qa_reference_ids': reference_ids}}
                        )
                        stats['qa_linked'] += 1

                if stats['total'] % 100 == 0:
                    self.logger.info(f"Processed {stats['total']}/{total} policies")

            skip += batch_size

        self.logger.info(f"Relationship building completed: {stats}")
        return stats

    def get_legislation_tree(self, root_law_id: str) -> Dict[str, Any]:
        """
        获取完整的立法树
        返回从根本法律到所有下位政策的树形结构
        """
        root = self.db.find_by_id(root_law_id)
        if not root:
            return None

        def build_tree(policy_id: str, depth: int = 0) -> Dict[str, Any]:
            policy = self.db.find_by_id(policy_id)
            if not policy:
                return None

            node = {
                'policy_id': policy['policy_id'],
                'title': policy['title'],
                'document_level': policy['document_level'],
                'document_type': policy['document_type'],
                'depth': depth,
                'children': []
            }

            # 查找下位政策
            children = list(self.db.collection.find({'parent_policy_id': policy_id}))
            for child in children:
                child_node = build_tree(child['policy_id'], depth + 1)
                if child_node:
                    node['children'].append(child_node)

            return node

        return build_tree(root_law_id)

    def get_citation_graph(self, policy_id: str) -> Dict[str, Any]:
        """
        获取政策的引用关系图
        包括：引用的政策、被引用的政策
        """
        policy = self.db.find_by_id(policy_id)
        if not policy:
            return None

        # 引用的政策
        cited_ids = policy.get('cited_policy_ids', [])
        cited_policies = []
        for cid in cited_ids:
            p = self.db.find_by_id(cid)
            if p:
                cited_policies.append({
                    'policy_id': p['policy_id'],
                    'title': p['title'],
                    'document_level': p['document_level']
                })

        # 被引用的政策
        cited_by_ids = policy.get('cited_by_policy_ids', [])
        cited_by_policies = []
        for cbid in cited_by_ids:
            p = self.db.find_by_id(cbid)
            if p:
                cited_by_policies.append({
                    'policy_id': p['policy_id'],
                    'title': p['title'],
                    'document_level': p['document_level']
                })

        return {
            'policy_id': policy_id,
            'title': policy['title'],
            'cited_policies': cited_policies,
            'cited_by_policies': cited_by_policies
        }


# 便捷函数
def build_all_relationships(db: MongoDBConnector, batch_size: int = 100) -> Dict[str, Any]:
    """构建所有政策的关联关系"""
    builder = PolicyRelationshipBuilder(db)
    return builder.build_all_relationships(batch_size)
