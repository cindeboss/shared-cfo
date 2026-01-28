"""
Scrapy Items 定义
与 data_models_v2.py 保持一致
"""

import scrapy
from scrapy.loader import ItemLoader
from itemloaders.processors import TakeFirst, MapCompose, Join


def strip_whitespace(value):
    """去除空白字符"""
    if isinstance(value, str):
        return value.strip()
    return value


class TaxPolicyItem(scrapy.Item):
    """税务政策 Item"""
    # 基础字段
    policy_id = scrapy.Field()  # 唯一标识
    title = scrapy.Field()  # 标题
    url = scrapy.Field()  # 原文链接
    source = scrapy.Field()  # 数据来源

    # 分类字段
    tax_type = scrapy.Field()  # 税种标签
    region = scrapy.Field()  # 地域标签
    level = scrapy.Field()  # 层级（L1-L4）
    category = scrapy.Field()  # 分类（法律、行政法规等）
    document_type = scrapy.Field()  # 文档类型

    # 内容字段
    content = scrapy.Field()  # 正文内容
    summary = scrapy.Field()  # 摘要

    # 元数据字段
    publish_date = scrapy.Field()  # 发布日期
    document_number = scrapy.Field()  # 发文字号
    publish_department = scrapy.Field()  # 发布单位
    effective_date = scrapy.Field()  # 生效日期
    expiry_date = scrapy.Field()  # 失效日期

    # 关联字段
    parent_policies = scrapy.Field()  # 上位法
    related_policies = scrapy.Field()  # 相关政策
    keywords = scrapy.Field()  # 关键词

    # 系统字段
    crawled_at = scrapy.Field()  # 爬取时间
    crawler_version = scrapy.Field()  # 爬虫版本


class TaxPolicyItemLoader(ItemLoader):
    """Item Loader，默认输出第一个值"""
    default_output_processor = TakeFirst()

    # 某些字段需要保留列表
    tax_type_out = MapCompose(strip_whitespace)
    parent_policies_out = MapCompose(strip_whitespace)
    related_policies_out = MapCompose(strip_whitespace)
    keywords_out = MapCompose(strip_whitespace)

    # 内容字段可以拼接
    content_out = Join('\n')
    summary_out = Join(' ')
