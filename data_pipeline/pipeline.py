"""
数据获取管道
整合API、搜索补充、校验等多种数据获取方式
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pymongo import MongoClient

# 导入模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.npc_database import NPCDatabaseAPI
from .validator import DataQualityValidator
from .search_fallback import SearchFallbackModule

logger = logging.getLogger(__name__)


class DataAcquisitionPipeline:
    """数据获取管道"""

    def __init__(self, mongo_uri: str = 'mongodb://localhost:27017/'):
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client['shared_cfo']
        self.collection = self.db['policies']
        
        self.npc_api = NPCDatabaseAPI()
        self.search_fallback = SearchFallbackModule()
        self.validator = DataQualityValidator()
        
        self.stats = {
            'api_success': 0,
            'search_success': 0,
            'total': 0
        }

    async def fetch_law(self, law_name: str, use_search_fallback: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取法律数据
        
        优先级: API -> 搜索补充 -> None
        
        Args:
            law_name: 法律名称
            use_search_fallback: 是否使用搜索补充
            
        Returns:
            法律数据
        """
        self.stats['total'] += 1
        logger.info(f"开始获取法律: {law_name}")
        
        # 优先级1: API获取
        data = await self._fetch_from_api(law_name)
        if data:
            self.stats['api_success'] += 1
            return data
        
        # 优先级2: 搜索补充
        if use_search_fallback:
            data = await self._fetch_from_search(law_name)
            if data:
                self.stats['search_success'] += 1
                return data
        
        logger.warning(f"无法获取法律: {law_name}")
        return None

    async def _fetch_from_api(self, law_name: str) -> Optional[Dict[str, Any]]:
        """从API获取"""
        try:
            data = await self.npc_api.get_law_by_name(law_name)
            if data:
                # 验证数据质量
                if self.validator.validate(data):
                    # 保存到数据库
                    self._save_to_db(data)
                    logger.info(f"API获取成功: {law_name}")
                    return data
                else:
                    logger.warning(f"API数据质量不合格: {law_name}")
        except Exception as e:
            logger.error(f"API获取失败 {law_name}: {e}")
        return None

    async def _fetch_from_search(self, law_name: str) -> Optional[Dict[str, Any]]:
        """从搜索补充获取"""
        try:
            data = await self.search_fallback.search_law(law_name)
            if data:
                # 验证数据质量
                if self.validator.validate(data):
                    # 保存到数据库
                    self._save_to_db(data)
                    logger.info(f"搜索获取成功: {law_name}")
                    return data
        except Exception as e:
            logger.error(f"搜索获取失败 {law_name}: {e}")
        return None

    def _save_to_db(self, data: Dict[str, Any]):
        """保存到数据库"""
        # 检查是否已存在
        existing = self.collection.find_one({'policy_id': data['policy_id']})
        
        if existing:
            # 更新现有记录
            self.collection.update_one(
                {'policy_id': data['policy_id']},
                {'$set': data}
            )
            logger.info(f"更新数据: {data['title']}")
        else:
            # 插入新记录
            self.collection.insert_one(data)
            logger.info(f"新数据: {data['title']}")

    async def fetch_multiple_laws(self, law_names: List[str]) -> Dict[str, int]:
        """
        批量获取法律
        
        Args:
            law_names: 法律名称列表
            
        Returns:
            统计信息
        """
        results = {
            'success': 0,
            'failed': 0,
            'total': len(law_names)
        }
        
        for law_name in law_names:
            data = await self.fetch_law(law_name)
            if data:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        logger.info(f"批量获取完成: {results}")
        return results

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self.stats

    def close(self):
        """关闭连接"""
        if self.mongo_client:
            self.mongo_client.close()


# 便捷函数
async def fetch_law_with_pipeline(law_name: str, mongo_uri: str = 'mongodb://localhost:27017/') -> Optional[Dict[str, Any]]:
    """
    便捷函数：使用管道获取法律
    
    Args:
        law_name: 法律名称
        mongo_uri: MongoDB连接URI
        
    Returns:
        法律数据
    """
    pipeline = DataAcquisitionPipeline(mongo_uri)
    try:
        return await pipeline.fetch_law(law_name)
    finally:
        pipeline.close()
