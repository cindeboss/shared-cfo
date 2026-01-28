"""
数据模型定义 v2.0 - 支持政策层级体系和关联关系
根据《共享CFO - 爬虫模块需求文档 v3.0》设计
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class DocumentLevel(str, Enum):
    """政策层级枚举 - 严格按照法律效力划分"""
    L1 = "L1"  # 法律/行政法规/双边协定 (最高效力)
    L2 = "L2"  # 部门规章/财税文件/总局令 (核心依据)
    L3 = "L3"  # 规范性文件/执行口径 (执行指导)
    L4 = "L4"  # 解读/问答 (辅助理解)


class TaxCategory(str, Enum):
    """税收类别 - 按法律性质分类"""
    ENTITY = "实体税"  # 规定"交什么税"的法律
    PROCEDURAL = "程序税"  # 规定"怎么交税"的法律
    INTERNATIONAL = "国际税收"  # 双边协定、国际税收


class TaxType(str, Enum):
    """税种枚举"""
    # 流转税
    VAT = "增值税"
    CONSUMPTION = "消费税"
    CUSTOMS = "关税"
    VEHICLE_PURCHASE = "车辆购置税"

    # 所得税
    CIT = "企业所得税"
    IIT = "个人所得税"

    # 财产税
    PROPERTY = "房产税"
    DEED = "契税"
    LAND_APPRECIATION = "土地增值税"
    STAMP = "印花税"

    # 行为税
    CITY_MAINTENANCE = "城市维护建设税"

    # 资源环境税
    RESOURCE = "资源税"
    ENVIRONMENT = "环境保护税"
    FARMLAND_OCCUPATION = "耕地占用税"
    VESSEL = "车船税"
    TOBACCO = "烟叶税"
    TONNAGE = "船舶吨税"

    # 程序法
    PROCEDURE = "征管程序"

    # 国际税收
    TREATY = "国际税收协定"
    NON_RESIDENT = "非居民企业"
    ANTI_AVOIDANCE = "反避税"

    OTHER = "其他"


class DocumentType(str, Enum):
    """文档类型枚举"""
    # L1 类型
    LAW = "法律"
    ADMIN_REGULATION = "行政法规"
    TREATY = "双边协定"

    # L2 类型
    FISCAL_DOC = "财税文件"  # 财税〔2023〕1号
    ANNOUNCEMENT = "总局公告"
    DIRECTOR_ORDER = "总局令"
    MOF_DOC = "财政部文件"

    # L3 类型
    NORMATIVE_DOC = "规范性文件"
    IMPLEMENTATION_RULE = "执行口径"

    # L4 类型
    INTERPRETATION = "官方解读"
    QA = "热点问答"
    GUIDE = "办税指南"

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
    TIANJIN = "天津"
    CHONGQING = "重庆"
    SICHUAN = "四川"
    OTHER = "其他"


class ValidityStatus(str, Enum):
    """有效状态"""
    VALID = "有效"
    INVALID = "失效"
    PARTIALLY_INVALID = "部分失效"
    SUPERSEDED = "被新政策替代"


class QAPair(BaseModel):
    """问答对"""
    question: str = Field(..., description="问题内容")
    answer: str = Field(..., description="答案内容")
    question_type: Optional[str] = Field(None, description="问题类型")


class KeyPoint(BaseModel):
    """关键要点"""
    point: str = Field(..., description="要点内容")
    reference: Optional[str] = Field(None, description="参考条款")


class PolicyDocument(BaseModel):
    """
    政策文档数据模型 v2.0
    符合《共享CFO - 爬虫模块需求文档 v3.0》的数据库设计需求
    """

    # ========== 6.1.1 基础信息（必填） ==========
    policy_id: str = Field(..., description="政策唯一ID（格式：来源_年_序号，如 CHINATAX_2023_001）")
    title: str = Field(..., description="政策标题")
    source: str = Field(..., description="发布机关（如：国家税务总局、财政部）")
    url: str = Field(..., description="原文链接")
    publish_date: Optional[datetime] = Field(None, description="发布日期")
    document_number: Optional[str] = Field(None, description="发文字号（如：财税〔2023〕1号）")

    # ========== 6.1.2 层级分类（核心） ==========
    document_level: DocumentLevel = Field(..., description="政策层级：L1/L2/L3/L4")
    document_type: DocumentType = Field(..., description="文件类型：法律/行政法规/部门规章/公告/通知/解读/问答")
    tax_category: TaxCategory = Field(..., description="税收类别：实体税/程序税/国际税收")
    tax_type: List[TaxType] = Field(default_factory=list, description="税种标签")
    region: Region = Field(default=Region.NATIONAL, description="地域标签")

    # ========== 6.1.3 时效信息（重要） ==========
    effective_date: Optional[datetime] = Field(None, description="生效日期")
    expiry_date: Optional[datetime] = Field(None, description="失效日期")
    validity_status: ValidityStatus = Field(default=ValidityStatus.VALID, description="有效状态")
    validity_reason: Optional[str] = Field(None, description="失效原因")

    # ========== 6.1.4 关联关系（核心需求） ==========
    parent_policy_id: Optional[str] = Field(None, description="直接上位法ID")
    root_law_id: Optional[str] = Field(None, description="根本法律ID（最终溯源的法律，如征管法）")
    legislation_chain: List[str] = Field(default_factory=list, description="立法链路（从根本法律到当前政策的ID数组）")
    related_policy_ids: List[str] = Field(default_factory=list, description="相关政策ID列表（同一主题）")
    cited_policy_ids: List[str] = Field(default_factory=list, description="本政策引用的其他政策ID")
    cited_by_policy_ids: List[str] = Field(default_factory=list, description="引用本政策的其他政策ID")
    qa_reference_ids: List[str] = Field(default_factory=list, description="问答关联的原文政策ID")
    policy_group: Optional[str] = Field(None, description="政策组标识（同一主题的政策群）")

    # ========== 6.1.5 内容信息 ==========
    content: str = Field(..., description="正文内容")
    summary: Optional[str] = Field(None, description="摘要（100-200字）")
    key_points: List[KeyPoint] = Field(default_factory=list, description="关键要点（3-5个）")
    qa_pairs: List[QAPair] = Field(default_factory=list, description="问答对列表（问答类文档专用）")

    # ========== 6.1.6 国际税收专用字段 ==========
    counterpart_country: Optional[str] = Field(None, description="协定对方国家（如：新加坡、美国）")
    treaty_type: Optional[str] = Field(None, description="协定类型（如：避免双重征税协定）")
    signed_date: Optional[datetime] = Field(None, description="签署日期")

    # ========== 其他元数据 ==========
    publish_department: Optional[str] = Field(None, description="发布单位")
    attachments: List[str] = Field(default_factory=list, description="附件链接列表")
    crawled_at: datetime = Field(default_factory=datetime.now, description="爬取时间")
    updated_at: Optional[datetime] = Field(None, description="最后更新时间")

    # 质量评分（6.3 数据质量评分）
    quality_score: Optional[int] = Field(None, description="质量分数（0-100）")
    quality_level: Optional[str] = Field(None, description="质量等级（A/B/C/D）")

    # 扩展字段
    extra: Dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PolicyRelationship(BaseModel):
    """政策关联关系"""
    child_id: str = Field(..., description="下位政策ID")
    parent_id: str = Field(..., description="上位政策ID")
    relationship_type: str = Field(..., description="关系类型：legislation(立法)、citation(引用)、reference(参考)")
    created_at: datetime = Field(default_factory=datetime.now)


class PolicyUpdate(BaseModel):
    """政策更新记录"""
    policy_id: str = Field(..., description="政策ID")
    update_type: str = Field(..., description="更新类型：new/updated/expired")
    update_date: datetime = Field(default_factory=datetime.now)
    description: Optional[str] = Field(None, description="更新描述")


class CrawlTask(BaseModel):
    """爬取任务"""
    task_id: str = Field(..., description="任务ID")
    source: str = Field(..., description="数据源")
    source_type: str = Field(..., description="数据源类型：chinatax/mof/12366/international/provincial")
    status: str = Field(default="pending", description="状态：pending/running/completed/failed")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    total_count: int = Field(default=0, description="应爬取总数")
    success_count: int = Field(default=0, description="成功数量")
    failed_count: int = Field(default=0, description="失败数量")
    error_message: Optional[str] = Field(None, description="错误信息")
    progress: float = Field(default=0.0, description="进度（0-1）")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DataQualityReport(BaseModel):
    """数据质量报告"""
    report_date: datetime = Field(default_factory=datetime.now)
    total_policies: int = Field(..., description="总政策数")
    by_level: Dict[str, int] = Field(default_factory=dict, description="按层级统计")
    by_category: Dict[str, int] = Field(default_factory=dict, description="按类别统计")
    completeness_score: float = Field(..., description="完整性分数（0-100）")
    authority_score: float = Field(..., description="权威性分数（0-100）")
    relationship_score: float = Field(..., description="关联性分数（0-100）")
    timeliness_score: float = Field(..., description="时效性分数（0-100）")
    content_quality_score: float = Field(..., description="内容质量分数（0-100）")
    overall_quality_level: str = Field(..., description="总体质量等级")
    issues: List[str] = Field(default_factory=list, description="发现的问题")
