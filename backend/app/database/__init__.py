"""
数据库模块初始化
"""
from .mongo import mongo, get_mongo
from .qdrant import qdrant, get_qdrant

__all__ = ["mongo", "get_mongo", "qdrant", "get_qdrant"]
