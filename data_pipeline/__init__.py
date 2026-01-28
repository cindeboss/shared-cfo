"""
数据获取管道模块
整合API、爬虫、搜索等多种数据源
"""

from .pipeline import DataAcquisitionPipeline
from .validator import DataQualityValidator
from .search_fallback import SearchFallbackModule

__all__ = ['DataAcquisitionPipeline', 'DataQualityValidator', 'SearchFallbackModule']
