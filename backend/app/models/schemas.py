"""
API数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==================== 请求模型 ====================

class ChatRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., description="用户问题", min_length=1)
    tax_type: Optional[str] = Field(None, description="税种筛选")
    region: Optional[str] = Field(None, description="地区筛选")
    top_k: int = Field(5, description="检索相关文档数量", ge=1, le=20)


class PolicySearchRequest(BaseModel):
    """政策搜索请求"""
    keyword: str = Field(..., description="搜索关键词")
    tax_type: Optional[str] = Field(None, description="税种筛选")
    region: Optional[str] = Field(None, description="地区筛选")
    start_date: Optional[str] = Field(None, description="起始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    page: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页数量", ge=1, le=100)


class PolicyDetailRequest(BaseModel):
    """政策详情请求"""
    policy_id: str = Field(..., description="政策ID")


# ==================== 响应模型 ====================

class PolicyReference(BaseModel):
    """政策引用"""
    policy_id: str
    title: str
    source: str
    url: str
    publish_date: Optional[datetime] = None
    document_number: Optional[str] = None
    relevance_score: float = 0.0


class ChatResponse(BaseModel):
    """问答响应"""
    # 结论
    conclusion: str

    # 政策依据
    policy_references: List[PolicyReference]

    # 分析过程
    analysis: str

    # 通俗解释
    explanation: str

    # 有效期
    validity_period: str

    # 风险提示
    risk_warning: Optional[str] = None

    # 元数据
    processing_time: float = 0.0
    model_used: str = "glm-4-flash"


class PolicyListItem(BaseModel):
    """政策列表项"""
    policy_id: str
    title: str
    source: str
    tax_type: List[str]
    region: str
    document_type: str
    publish_date: Optional[datetime]
    document_number: Optional[str]
    summary: Optional[str] = None


class PolicySearchResponse(BaseModel):
    """政策搜索响应"""
    total: int
    page: int
    page_size: int
    items: List[PolicyListItem]


class PolicyDetailResponse(BaseModel):
    """政策详情响应"""
    policy_id: str
    title: str
    source: str
    url: str
    tax_type: List[str]
    region: str
    document_type: str
    content: str
    publish_date: Optional[datetime]
    document_number: Optional[str]
    publish_department: Optional[str]
    valid_until: Optional[datetime]
    is_valid: bool
    qa_pairs: List[Dict[str, Any]] = []
    crawled_at: datetime


# ==================== 通用响应 ====================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    mongo_connected: bool
    qdrant_connected: bool
    glm_configured: bool


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None
