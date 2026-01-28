"""
国家法律法规数据库API客户端
https://flk.npc.gov.cn/
"""

import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import aiohttp

from .base_api import BaseAPIClient

logger = logging.getLogger(__name__)


class NPCDatabaseAPI(BaseAPIClient):
    """国家法律法规数据库API客户端"""

    def __init__(self):
        super().__init__("https://flk.npc.gov.cn/api/", timeout=30)

    async def get_laws(self, page: int = 1, per_page: int = 20) -> List[Dict[str, Any]]:
        """获取法律列表"""
        try:
            await self.create_session()
            data = await self.get("", params={"page": page})
            
            laws = []
            if data.get('code') == 200:
                items = data.get('data', [])
                for item in items:
                    law = self.parse_law_item(item)
                    if law:
                        laws.append(lawaw)
                        
            logger.info(f"从NPC API获取 {len(laws)} 条法律")
            return laws
            
        except Exception as e:
            logger.error(f"获取法律列表失败: {e}")
            return []
        finally:
            await self.close_session()

    async def get_law_by_name(self, law_name: str) -> Optional[Dict[str, Any]]:
        """根据名称搜索法律"""
        try:
            await self.create_session()
            
            # 搜索前几页
            for page in range(1, 5):
                data = await self.get("", params={"page": page})
                
                if data.get('code') == 200:
                    items = data.get('data', [])
                    for item in items:
                        title = item.get('title', '')
                        if law_name in title:
                            law_code = item.get('code', '')
                            if law_code:
                                detail = await self.get_detail(law_code)
                                if detail:
                                    return self.parse_law_detail(detail)
            
            logger.warning(f"未找到法律: {law_name}")
            return None
            
        except Exception as e:
            logger.error(f"搜索法律失败 {law_name}: {e}")
            return None
        finally:
            await self.close_session()

    async def get_detail(self, law_code: str) -> Optional[Dict[str, Any]]:
        """获取法律详情"""
        try:
            data = await self.get(f"detail?code={law_code}")
            if data.get('code') == 200:
                return data.get('data')
            return None
        except Exception as e:
            logger.error(f"获取法律详情失败 {law_code}: {e}")
            return None

    def parse_law_item(self, item: Dict) -> Dict[str, Any]:
        """解析法律列表项"""
        return {
            'code': item.get('code', ''),
            'title': item.get('title', ''),
            'publish_date': item.get('publishDate', ''),
            'source': '全国人大',
            'url': f"https://flk.npc.gov.cn/detail.html?code={item.get('code', '')}",
            'api_source': 'npc_database'
        }

    def parse_law_detail(self, detail: Dict) -> Dict[str, Any]:
        """解析法律详情为标准格式"""
        content = detail.get('content', '')
        
        # 提取发文字号
        document_number = self._extract_document_number(content)
        
        # 提取发布日期
        publish_date = detail.get('publishDate', '')
        if not publish_date:
            publish_date = self._extract_publish_date(content)
        
        # 提取生效日期
        effective_date = self._extract_effective_date(content)
        
        # 确定层级和类型
        title = detail.get('title', '')
        document_level = self._determine_level(title)
        document_type = '法律'
        
        return {
            'policy_id': f"NPC_{document_level}_{detail.get('code', '')}",
            'title': title,
            'source': '全国人大',
            'url': f"https://flk.npc.gov.cn/detail.html?code={detail.get('code', '')}",
            'content': content,
            'document_level': document_level,
            'document_type': document_type,
            'document_number': document_number,
            'publish_date': publish_date,
            'effective_date': effective_date,
            'region': '全国',
            'api_source': 'npc_database',
            'crawled_at': datetime.now(),
            'quality_score': 5
        }

    def _extract_document_number(self, content: str) -> Optional[str]:
        """提取发文字号"""
        patterns = [
            r'主席令[第第]?(\d+)号',
            r'中华人民共和国主席令.*?第(\d+)号',
        ]
        for pattern in patterns:
            match = re.search(pattern, content[:200])
            if match:
                return match.group(0)
        return None

    def _extract_publish_date(self, content: str) -> Optional[str]:
        """提取发布日期"""
        patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, content[:500])
            if match:
                return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
        return None

    def _extract_effective_date(self, content: str) -> Optional[str]:
        """提取生效日期"""
        patterns = [
            r'自(\d{4})年(\d{1,2})月(\d{1,2})日起[施行行]',
            r'(\d{4})年(\d{1,2})月(\d{1,2})日起[施行行]',
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
        return None

    def _determine_level(self, title: str) -> str:
        """根据标题确定层级"""
        if '法' in title and '实施条例' not in title:
            return 'L1'
        elif '条例' in title or '实施细则' in title:
            return 'L2'
        else:
            return 'L1'

    async def close(self):
        """关闭客户端"""
        await self.close_session()
