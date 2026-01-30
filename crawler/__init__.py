"""
税务政策爬虫包
根据《共享CFO - 爬虫模块需求文档 v3.0》实现

主要模块：
- base_crawler: 基础爬虫框架（含合规检查）
- data_models: 数据模型（含层级和关联关系）
- database: 数据库连接器（含关系追踪）
- chinatax_crawler: 国家税务总局爬虫
- crawler_12366: 12366平台爬虫
- relationship_builder: 政策关联关系构建器
- quality_validator: 数据质量验证器
- orchestrator: 爬虫编排器
"""

# 核心模块
from .base_crawler import BaseCrawler, FieldExtractor, ComplianceChecker
from .data_models import (
    PolicyDocument, CrawlTask, DocumentLevel, TaxCategory, TaxType,
    DocumentType, Region, ValidityStatus, DataQualityReport
)
from .database import MongoDBConnector
from .chinatax_crawler import ChinaTaxCrawler
from .crawler_12366 import Crawler12366
from .relationship_builder import PolicyRelationshipBuilder
from .quality_validator import DataQualityValidator
from .orchestrator import CrawlerOrchestrator, run_crawl_phase, get_progress

# 向后兼容的别名
MongoDBConnector = MongoDBConnector  # 保持向后兼容

__all__ = [
    # 基础组件
    'BaseCrawler',
    'FieldExtractor',
    'ComplianceChecker',
    # 数据模型
    'PolicyDocument',
    'CrawlTask',
    'DocumentLevel',
    'TaxCategory',
    'TaxType',
    'DocumentType',
    'Region',
    'ValidityStatus',
    'DataQualityReport',
    # 数据库
    'MongoDBConnector',
    'MongoDBConnector',  # 向后兼容别名
    # 爬虫
    'ChinaTaxCrawler',
    'Crawler12366',
    # 工具
    'PolicyRelationshipBuilder',
    'DataQualityValidator',
    'CrawlerOrchestrator',
    'run_crawl_phase',
    'get_progress',
]

__version__ = '2.1.0'
