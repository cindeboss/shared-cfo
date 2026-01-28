"""
API客户端基类
提供通用的API请求功能
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)


class BaseAPIClient:
    """API客户端基类"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.session = None

    async def __aenter__(self):
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()

    async def create_session(self):
        """创建HTTP会话"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        self.session = aiohttp.ClientSession(headers=headers)
        logger.info(f"创建API会话: {self.base_url}")

    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            logger.info("关闭API会话")

    async def get(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """GET请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            async with self.session.get(url, params=params, timeout=self.timeout) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            logger.error(f"GET请求失败 {url}: {e}")
            raise

    async def post(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """POST请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            async with self.session.post(url, json=data, timeout=self.timeout) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            logger.error(f"POST请求失败 {url}: {e}")
            raise

    def parse_law_data(self, raw_data: Dict) -> Dict[str, Any]:
        """解析法律数据（子类重写）"""
        raise NotImplementedError

    def is_available(self) -> bool:
        """检查API是否可用（子类可重写）"""
        return True
