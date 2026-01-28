"""
API客户端模块
用于接入各种官方数据源API
"""

from .base_api import BaseAPIClient
from .npc_database import NPCDatabaseAPI

__all__ = ['BaseAPIClient', 'NPCDatabaseAPI']
