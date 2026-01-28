"""
搜索补充模块
当API不可用时，通过搜索引擎找到可靠的数据源
"""

import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SearchFallbackModule:
    """搜索补充模块"""

    def __init__(self):
        self.sources = [
            GovernmentWebsiteSource(),
            LegalDatabaseSource(),
        ]

    async def search_law(self, law_name: str) -> Optional[Dict[str, Any]]:
        """
        搜索法律
        
        Args:
            law_name: 法律名称
            
        Returns:
            法律数据
        """
        logger.info(f"开始搜索法律: {law_name}")
        
        for source in self.sources:
            try:
                result = await source.search_and_extract(law_name)
                if result and self._check_reliability(result):
                    logger.info(f"从 {source.__class__.__name__} 找到数据")
                    return result
            except Exception as e:
                logger.warning(f"{source.__class__.__name__} 搜索失败: {e}")
                continue
        
        logger.warning(f"所有搜索源均未找到: {law_name}")
        return None

    def _check_reliability(self, data: Dict[str, Any]) -> bool:
        """检查数据可靠性"""
        content = data.get('content', '')
        
        # 内容长度检查
        if len(content) < 500:
            return False
        
        # 来源权威性检查
        source = data.get('source', '')
        if any(auth in source for auth in ['全国人大', '国务院', '国家税务总局']):
            return True
        
        # URL权威性检查
        url = data.get('url', '')
        if any(domain in url for domain in ['npc.gov.cn', 'gov.cn', 'chinatax.gov.cn']):
            return True
        
        return False


class GovernmentWebsiteSource:
    """政府官网数据源"""

    async def search_and_extract(self, law_name: str) -> Optional[Dict[str, Any]]:
        """从政府官网搜索并提取"""
        # 直接尝试已知的政府官网URL
        urls = [
            ('全国人大', f'https://www.npc.gov.cn/npc/c234/{self._encode_law_name(law_name)}.shtml'),
            ('国务院', f'https://www.gov.cn/search?q={law_name}'),
        ]
        
        for source_name, url in urls:
            try:
                data = await self._fetch_and_extract(url, source_name, law_name)
                if data:
                    return data
            except Exception as e:
                logger.warning(f"{source_name} 提取失败: {e}")
                continue
        
        return None

    async def _fetch_and_extract(self, url: str, source_name: str, law_name: str) -> Optional[Dict[str, Any]]:
        """获取并提取网页内容"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                if resp.status != 200:
                    return None
                
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 提取正文
                content = self._extract_main_content(soup)
                
                if not content or len(content) < 200:
                    return None
                
                return {
                    'title': law_name,
                    'source': source_name,
                    'url': url,
                    'content': content,
                    'document_level': 'L1',
                    'document_type': '法律',
                    'region': '全国',
                    'api_source': 'search_fallback',
                    'crawled_at': __import__('datetime').datetime.now()
                }

    def _extract_main_content(self, soup) -> str:
        """提取主要内容"""
        # 尝试多种选择器
        selectors = [
            'article',
            '.content',
            '.main-content',
            '#content',
            '.text',
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator='\n', strip=True)
                if len(text) > 500:
                    return text
        
        return soup.get_text(separator='\n', strip=True)

    def _encode_law_name(self, law_name: str) -> str:
        """编码法律名称用于URL"""
        # 简单的日期编码
        if '增值税法' in law_name:
            return '20241225a5a9a09'  # 增值税法通过日期
        elif '个人所得税法' in law_name:
            return '20180831a48f9d9'
        elif '企业所得税法' in law_name:
            return '20070316a0e510e'
        elif '税收征收管理法' in law_name:
            return '20150427a4c7c2e'
        return ''

class LegalDatabaseSource:
    """法律数据库数据源"""
    
    async def search_and_extract(self, law_name: str) -> Optional[Dict[str, Any]]:
        # 这里可以扩展为接入其他法律数据库API
        return None
