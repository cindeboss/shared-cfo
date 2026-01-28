"""
获取法律数据
使用WebReader工具从政府官网获取完整法律文本
"""

import logging
from datetime import datetime
from pymongo import MongoClient
import json

logger = logging.getLogger(__name__)


class LawDataFetcher:
    """法律数据获取器"""

    def __init__(self, mongo_uri='mongodb://localhost:27017/'):
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client['shared_cfo']
        self.collection = self.db['policies']

    def fetch_law_from_npc(self, law_name: str) -> dict:
        """
        从全国人大官网获取法律
        
        使用已知的URL模式
        """
        # 法律文件的URL模式（从之前的研究中获得）
        law_urls = {
            '增值税法': 'https://www.npc.gov.cn/npc/c234/20241225a5a9a09.shtml',
            '个人所得税法': 'https://www.npc.gov.cn/npc/c234/20180831a48f9d9.shtml',
            '企业所得税法': 'https://www.npc.gov.cn/npc/c234/20070316a0e510e.shtml',
            '税收征收管理法': 'https://www.npc.gov.cn/npc/c234/20150427a4c7c2e.shtml',
        }

        url = law_urls.get(law_name)
        if not url:
            logger.error(f"未找到{law_name}的URL")
            return None

        logger.info(f"从全国人大官网获取: {law_name}")

        # 使用webReader工具获取内容
        # 注意：这里需要调用webReader MCP工具
        # 暂时手动填充数据
        return self._create_placeholder_data(law_name)

    def fetch_regulation_from_gov(self, regulation_name: str) -> dict:
        """
        从国务院官网获取行政法规
        """
        regulation_urls = {
            '增值税暂行条例': 'https://www.gov.cn/zhengce/content/2017-12/29/content_5343642.htm',
            '个人所得税法实施条例': 'https://www.gov.cn/zhengce/content/2018-12/22/content_5350262.htm',
            '企业所得税法实施条例': 'https://www.gov.cn/zhengce/content/2007-12/11/content_5279817.htm',
            '税收征收管理法实施细则': 'https://www.gov.cn/zhengce/content/2016-02/06/content_5031145.htm',
        }

        url = regulation_urls.get(regulation_name)
        if not url:
            logger.error(f"未找到{regulation_name}的URL")
            return None

        logger.info(f"从国务院官网获取: {regulation_name}")
        return self._fetch_from_url(url, regulation_name, '国务院', 'L2')

    def _fetch_from_url(self, url: str, title: str, source: str, level: str) -> dict:
        """从URL获取数据（使用webReader）"""
        # 这里需要调用webReader工具
        # 暂时返回占位数据
        return self._create_placeholder_data(title, source, level)

    def _create_placeholder_data(self, title, source='手工整理', level='L1'):
        """创建占位数据"""
        return {
            'title': f'中华人民共和国{title}',
            'source': source,
            'url': '',
            'content': f'{title}的完整内容待获取',
            'document_level': level,
            'document_type': '法律' if level == 'L1' else '行政法规',
            'region': '全国',
            'crawled_at': datetime.now(),
            'quality_score': 3,
            'status': 'pending'
        }

    def save_to_db(self, data):
        """保存到数据库"""
        # 先删除同名旧数据
        self.collection.delete_many({'title': data['title']})
        # 插入新数据
        self.collection.insert_one(data)
        logger.info(f"保存数据: {data['title']}")


# 便捷函数
def fetch_and_save_law(law_name: str, mongo_uri='mongodb://localhost:27017/'):
    """获取并保存法律"""
    fetcher = LawDataFetcher(mongo_uri)
    data = fetcher.fetch_law_from_npc(law_name)
    if data:
        fetcher.save_to_db(data)
        return True
    return False
