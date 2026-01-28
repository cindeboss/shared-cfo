"""
数据模型定义
定义MongoDB存储的数据结构
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TaxType(str, Enum):
    """税种枚举"""
    VAT = "增值税"  # 增值税
    CIT = "企业所得税"  # 企业所得税
    IIT = "个人所得税"  # 个人所得税
    CONSUMPTION = "消费税"
    STAMP = "印花税"
    OTHER = "其他"


class DocumentType(str, Enum):
    """文档类型枚举"""
    LAW = "法律"
    REGULATION = "行政法规"
    RULE = "部门规章"
    FISCAL_DOC = "财税文件"
    NORMATIVE_DOC = "规范性文件"
    ANNOUNCEMENT = "公告"
    NOTICE = "通知"
    INTERPRETATION = "解读"
    QA = "问答"
    OTHER = "其他"


class Region(str, Enum):
    """地区枚举"""
    NATIONAL = "全国"
    BEIJING = "北京"
    SHANGHAI = "上海"
    GUANGDONG = "广东"
    SHENZHEN = "深圳"
    JIANGSU = "江苏"
    ZHEJIANG = "浙江"
    OTHER = "其他"


class QAPair(BaseModel):
    """问答对"""
    question: str = Field(..., description="问题内容")
    answer: str = Field(..., description="答案内容")


class PolicyDocument(BaseModel):
    """政策文档数据模型"""
    # 基础信息
    policy_id: str = Field(..., description="政策唯一ID（URL中的文件ID或哈希值）")
    title: str = Field(..., description="政策标题")
    source: str = Field(..., description="数据来源（如：国家税务总局、北京税务局）")
    url: str = Field(..., description="原文链接")

    # 分类信息
    tax_type: List[TaxType] = Field(default_factory=list, description="税种标签")
    region: Region = Field(default=Region.NATIONAL, description="地域标签")
    document_type: DocumentType = Field(..., description="文档类型")

    # 内容信息
    content: str = Field(..., description="正文内容")
    qa_pairs: List[QAPair] = Field(default_factory=list, description="问答对列表（问答类文档）")

    # 元数据
    publish_date: Optional[datetime] = Field(None, description="发布日期")
    effective_date: Optional[datetime] = Field(None, description="生效日期")
    expiry_date: Optional[datetime] = Field(None, description="失效日期")
    document_number: Optional[str] = Field(None, description="发文字号")
    publish_department: Optional[str] = Field(None, description="发布单位")

    # 附件
    attachments: List[str] = Field(default_factory=list, description="附件链接列表")

    # 爬取信息
    crawled_at: datetime = Field(default_factory=datetime.now, description="爬取时间")
    is_valid: bool = Field(default=True, description="是否有效（未过期）")

    # 扩展字段（存储网站特定的额外信息）
    extra: Dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CrawlTask(BaseModel):
    """爬取任务"""
    task_id: str = Field(..., description="任务ID")
    source: str = Field(..., description="数据源")
    status: str = Field(default="pending", description="状态：pending/running/completed/failed")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    total_count: int = Field(default=0, description="应爬取总数")
    success_count: int = Field(default=0, description="成功数量")
    failed_count: int = Field(default=0, description="失败数量")
    error_message: Optional[str] = Field(None, description="错误信息")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
