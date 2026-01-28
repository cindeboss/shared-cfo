"""
税务政策爬虫包 v2.0
根据《共享CFO - 爬虫模块需求文档 v3.0》实现

主要模块：
- base_v2: 基础爬虫框架（含合规检查）
- data_models_v2: 数据模型（含层级和关联关系）
- database_v2: 数据库连接器（含关系追踪）
- chinatax_crawler_v4: 国家税务总局爬虫
- crawler_12366_v2: 12366平台爬虫
- relationship_builder: 政策关联关系构建器
- quality_validator: 数据质量验证器
- orchestrator: 爬虫编排器
"""

# 新版本（v2.0）模块
from .base_v2 import BaseCrawler, FieldExtractor, ComplianceChecker
from .data_models_v2 import (
    PolicyDocument, CrawlTask, DocumentLevel, TaxCategory, TaxType,
    DocumentType, Region, ValidityStatus, DataQualityReport
)
from .database_v2 import MongoDBConnectorV2
from .chinatax_crawler_v4 import ChinaTaxCrawler
from .crawler_12366_v2 import Crawler12366
from .relationship_builder import PolicyRelationshipBuilder
from .quality_validator import DataQualityValidator
from .orchestrator import CrawlerOrchestrator, run_crawl_phase, get_progress

# 旧版本模块（向后兼容）
try:
    from .base import BaseCrawler as BaseCrawlerV1
    from .chinatax_crawler import ChinaTaxCrawler as ChinaTaxCrawlerV1
    from .database import MongoDBConnector, QdrantConnector
    from .data_models import PolicyDocument as PolicyDocumentV1
except ImportError:
    pass

__all__ = [
    # v2.0 模块
    'BaseCrawler',
    'FieldExtractor',
    'ComplianceChecker',
    'PolicyDocument',
    'CrawlTask',
    'DocumentLevel',
    'TaxCategory',
    'TaxType',
    'DocumentType',
    'Region',
    'ValidityStatus',
    'DataQualityReport',
    'MongoDBConnectorV2',
    'ChinaTaxCrawler',
    'Crawler12366',
    'PolicyRelationshipBuilder',
    'DataQualityValidator',
    'CrawlerOrchestrator',
    'run_crawl_phase',
    'get_progress',
]

__version__ = '2.0.0'
