"""
共享CFO - 层级化数据模型
定义政策文档的完整数据结构，包含层级、效力、关联关系等
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import IntEnum


class PolicyLevel(IntEnum):
    """政策层级 - 6级体系"""
    LAW = 1           # 法律 - 全国人大
    REGULATION = 2     # 行政法规 - 国务院
    RULE = 3           # 部门规章 - 各部委
    NORMATIVE = 4      # 规范性文件 - 红头文件
    INTERPRETATION = 5 # 官方解读
    GUIDANCE = 6       # 执行口径/操作指引


class DocumentType(BaseModel):
    """文档类型"""
    primary: str = Field(..., description="主类型")
    sub: Optional[str] = Field(None, description="子类型")

    class Config:
        use_enum_values = True


class LegalInfo(BaseModel):
    """法律效力信息"""
    level: PolicyLevel = Field(..., description="政策层级")
    level_name: str = Field(..., description="层级名称")

    # 制定机关
    issuing_authority: str = Field(..., description="制定机关")
    authority_type: str = Field(..., description="机关类型: 全国人大/国务院/部委/地方")

    # 文号信息
    document_number: Optional[str] = Field(None, description="发文字号")
    document_number_alias: List[str] = Field(default_factory=list, description="文号别名")

    # 效力评分（1-10）
    legal_effect_score: int = Field(default=5, ge=1, le=10, description="法律效力评分")
    authority_score: int = Field(default=5, ge=1, le=10, description="权威性评分")
    binding_force_score: int = Field(default=5, ge=1, le=10, description="约束力评分")

    # 综合权重（用于答案排序）
    total_weight: float = Field(default=0.5, description="综合权重")

    # 时效信息
    publish_date: Optional[datetime] = Field(None, description="发布日期")
    effective_date: Optional[datetime] = Field(None, description="生效日期")
    expiry_date: Optional[datetime] = Field(None, description="失效日期")

    # 有效状态
    validity_status: str = Field(default="unknown", description="有效状态: valid/expired/partial/unknown")
    validity_description: str = Field(default="", description="有效性描述")

    # 执行范围
    execution_scope: str = Field(default="全国", description="执行范围")
    target_taxpayers: List[str] = Field(default_factory=list, description="适用纳税人类型")


class PolicyRelations(BaseModel):
    """政策关联关系"""
    # 上位法依据
    upper_level_laws: List[str] = Field(default_factory=list, description="上位法律")

    # 下位实施文件
    implementation_rules: List[str] = Field(default_factory=list, description="实施细则")

    # 配套解读
    interpretations: List[str] = Field(default_factory=list, description="官方解读")

    # 相关政策
    related_policies: List[str] = Field(default_factory=list, description="相关政策")

    # 被以下文件引用
    referenced_by: List[str] = Field(default_factory=list, description="引用本政策的文件")

    # 地方执行口径
    local_guidance: Dict[str, List[str]] = Field(default_factory=dict, description="地方执行口径")


class TaxTypeInfo(BaseModel):
    """税种信息"""
    primary: str = Field(..., description="主税种")
    sub_types: List[str] = Field(default_factory=list, description="子类型")

    # 增值税特殊
    vat_rate: Optional[float] = Field(None, description="增值税税率")
    vat_type: Optional[str] = Field(None, description="增值税类型: 一般纳税人/小规模")

    # 个人所得税特殊
    pit_category: Optional[str] = Field(None, description="个税类别")

    # 企业所得税特殊
    cit_type: Optional[str] = Field(None, description="企税类型")


class ContentInfo(BaseModel):
    """内容信息"""
    full_text: str = Field(..., description="完整正文内容")
    summary: Optional[str] = Field(None, description="内容摘要")
    key_points: List[str] = Field(default_factory=list, description="关键要点")

    # 内容质量评分
    content_length: int = Field(..., description="内容长度(字符数)")
    quality_level: int = Field(default=3, ge=1, le=5, description="质量等级 1-5")
    quality_score: int = Field(default=60, ge=0, le=100, description="质量分数")

    # 内容类型
    content_type: str = Field(default="text", description="内容类型: text/qa/guide")

    # 结构化内容
    articles: List[Dict[str, Any]] = Field(default_factory=list, description="条文结构")
    faqs: List[Dict[str, str]] = Field(default_factory=list, description="问答对")


class PolicyDocument(BaseModel):
    """完整的政策文档"""

    # ========== 基础标识 ==========
    policy_id: str = Field(..., description="唯一标识")
    title: str = Field(..., description="政策标题")

    # ========== 层级与效力 ==========
    legal_info: LegalInfo = Field(..., description="法律效力信息")

    # ========== 关联关系 ==========
    relations: PolicyRelations = Field(default_factory=PolicyRelations, description="政策关联关系")

    # ========== 税种信息 ==========
    tax_info: TaxTypeInfo = Field(..., description="税种信息")

    # ========== 内容信息 ==========
    content_info: ContentInfo = Field(..., description="内容信息")

    # ========== 元数据 ==========
    source: str = Field(..., description="数据来源")
    url: str = Field(..., description="原文链接")
    region: str = Field(default="全国", description="适用地区")

    # 文档分类
    document_type: DocumentType = Field(..., description="文档类型")
    tags: List[str] = Field(default_factory=list, description="标签")
    keywords: List[str] = Field(default_factory=list, description="关键词")

    # 爬取元数据
    crawled_at: datetime = Field(default_factory=datetime.now, description="爬取时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    crawl_source: str = Field(..., description="爬取来源网站")

    # 数据质量
    data_quality: Dict[str, Any] = Field(default_factory=dict, description="数据质量指标")


class PolicyDocumentSimple(BaseModel):
    """简化版政策文档 - 用于列表展示"""
    policy_id: str
    title: str
    level: int
    level_name: str
    legal_effect_score: int
    source: str
    url: str
    tax_primary: str
    publish_date: Optional[datetime]
    validity_status: str
    quality_score: int
    summary: Optional[str] = None


# ==================== 质量评分函数 ====================

def calculate_quality_score(doc: Dict[str, Any]) -> int:
    """计算数据质量分数 (0-100)"""
    score = 0

    # 1. 必需字段完整性 (30分)
    if doc.get('document_number'):
        score += 10
    if doc.get('publish_date'):
        score += 10
    if doc.get('title') and len(doc.get('title', '')) > 20:
        score += 10

    # 2. 内容质量 (40分)
    content = doc.get('content', '')
    content_len = len(content)

    if content_len > 200:
        score += 5
    if content_len > 500:
        score += 10
    if content_len > 1000:
        score += 10
    if content_len > 2000:
        score += 5

    # 有配套解读加分
    if '解读' in doc.get('title', ''):
        score += 10

    # 3. 时效性 (20分)
    if doc.get('effective_date'):
        score += 10
    if doc.get('expiry_date'):
        score += 10

    # 4. 结构化程度 (10分)
    tax_type = doc.get('tax_type', [])
    if tax_type and tax_type != ['其他']:
        score += 5
    if doc.get('document_number'):
        score += 5

    return min(score, 100)


def determine_quality_level(score: int) -> int:
    """根据分数确定质量等级 (1-5)"""
    if score >= 90:
        return 5  # Level 5: 优秀
    elif score >= 75:
        return 4  # Level 4: 良好
    elif score >= 60:
        return 3  # Level 3: 合格
    elif score >= 40:
        return 2  # Level 2: 基础
    else:
        return 1  # Level 1: 较差


def determine_policy_level(doc: Dict[str, Any]) -> PolicyLevel:
    """根据政策特征判断层级"""
    title = doc.get('title', '')
    source = doc.get('source', '')
    content = doc.get('content', '')

    # 第一层：法律
    if '中华人民共和国增值税法' in title or '中华人民共和国个人所得税法' in title or '中华人民共和国企业所得税法' in title:
        if '全国人民代表大会' in content or '全国人大' in content:
            return PolicyLevel.LAW

    # 第二层：行政法规
    if '实施条例' in title and '国务院' in content:
        return PolicyLevel.REGULATION

    # 第三层：部门规章
    if '管理办法' in title or '实施细则' in title:
        if '部令' in content or '国家税务总局令' in content:
            return PolicyLevel.RULE

    # 第五层：官方解读
    if '解读' in title or '答记者问' in title:
        return PolicyLevel.INTERPRETATION

    # 第六层：执行口径
    if '12366' in source or '热点问题' in title:
        return PolicyLevel.GUIDANCE

    # 第四层：规范性文件（默认）
    return PolicyLevel.NORMATIVE


def calculate_total_weight(legal_info: LegalInfo) -> float:
    """计算综合权重"""
    # 基础权重（按层级）
    base_weights = {
        PolicyLevel.LAW: 1.0,
        PolicyLevel.REGULATION: 0.9,
        PolicyLevel.RULE: 0.8,
        PolicyLevel.NORMATIVE: 0.7,
        PolicyLevel.INTERPRETATION: 0.6,
        PolicyLevel.GUIDANCE: 0.5,
    }

    base_weight = base_weights.get(legal_info.level, 0.5)

    # 调整系数
   时效性调整 = 1.0
    if legal_info.validity_status == 'valid':
        时效性调整 = 1.0
    elif legal_info.validity_status == 'expired':
        时效性调整 = 0.3
    elif legal_info.validity_status == 'partial':
        时效性调整 = 0.6

    综合权重 = base_weight * 时效性调整
    return round(综合权重, 2)
