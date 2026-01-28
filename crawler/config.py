"""
配置文件
包含所有爬虫相关的配置参数
"""

import os
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class MongoConfig:
    """MongoDB配置"""
    host: str = "localhost"
    port: int = 27017
    username: str = ""
    password: str = ""
    database: str = "shared_cfo"
    collection: str = "policies"

    # 阿里云MongoDB配置模板
    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("MONGO_HOST", "localhost"),
            port=int(os.getenv("MONGO_PORT", "27017")),
            username=os.getenv("MONGO_USERNAME", ""),
            password=os.getenv("MONGO_PASSWORD", ""),
            database=os.getenv("MONGO_DATABASE", "shared_cfo"),
            collection=os.getenv("MONGO_COLLECTION", "policies")
        )


@dataclass
class QdrantConfig:
    """Qdrant向量数据库配置"""
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "tax_policies"
    vector_size: int = 1536  # OpenAI embedding size, 可根据实际embedding模型调整

    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            collection_name=os.getenv("QDRANT_COLLECTION", "tax_policies"),
            vector_size=int(os.getenv("QDRANT_VECTOR_SIZE", "1536"))
        )


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    # 请求配置
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    timeout: int = 30
    retry_times: int = 3
    retry_delay: int = 2

    # 请求延迟配置（秒）
    delay_min: float = 3.0
    delay_max: float = 6.0

    # 并发配置
    max_concurrent: int = 3

    # 数据范围配置
    start_year: int = 2022  # 爬取起始年份
    end_year: int = 2025    # 爬取结束年份（当前年份）

    # 税种筛选
    target_tax_types: List[str] = field(default_factory=lambda: ["增值税", "企业所得税", "个人所得税"])

    # 日志配置
    log_level: str = "INFO"
    log_file: str = "crawler.log"


@dataclass
class SourceConfig:
    """数据源配置"""
    name: str
    base_url: str
    enabled: bool = True
    priority: int = 1

    # 具体的栏目配置
    channels: Dict[str, str] = field(default_factory=dict)


# 预定义的数据源配置
SOURCES: Dict[str, SourceConfig] = {
    "chinatax": SourceConfig(
        name="国家税务总局",
        base_url="https://fgk.chinatax.gov.cn",
        channels={
            "latest": "/zcfgk/c100006/listflfg.html",
            "law": "/zcfgk/c100001/",
            "regulation": "/zcfgk/c100002/",
            "rule": "/zcfgk/c100003/",
            "fiscal_doc": "/zcfgk/c100004/",
            "interpretation": "/zcfgk/c100015/list_zcjd.html",
        }
    ),
    "12366": SourceConfig(
        name="12366纳税服务平台",
        base_url="https://12366.chinatax.gov.cn",
        channels={
            "hot_questions": "/portal/search/kwd",
        }
    ),
    "beijing": SourceConfig(
        name="北京税务局",
        base_url="http://beijing.chinatax.gov.cn",
        channels={
            "interpretation": "/bjswj/sszc/zcjd/",
            "hot_iit": "/bjswj/c105397/",  # 个人所得税热点
            "hot_cit": "/bjswj/c105425/",  # 企业所得税热点
        }
    ),
    "shanghai": SourceConfig(
        name="上海税务局",
        base_url="https://shanghai.chinatax.gov.cn",
        channels={
            "interpretation": "/zcfw/zcjd/",
            "hot_qa": "/zcfw/rdwd/",
        }
    ),
    "guangdong": SourceConfig(
        name="广东税务局",
        base_url="https://guangdong.chinatax.gov.cn",
        channels={
            "interpretation": "/gdsw/gzsw_zcfg/",
        }
    ),
}


@dataclass
class GLMConfig:
    """智谱GLM配置"""
    api_key: str = ""
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    model: str = "glm-4-flash"  # 使用flash模型，性价比高
    embedding_model: str = "embedding-2"
    max_tokens: int = 2000
    temperature: float = 0.3

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("GLM_API_KEY", ""),
            base_url=os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
            model=os.getenv("GLM_MODEL", "glm-4-flash"),
            embedding_model=os.getenv("GLM_EMBEDDING_MODEL", "embedding-2"),
        )


# 全局配置实例
mongo_config = MongoConfig.from_env()
qdrant_config = QdrantConfig.from_env()
crawler_config = CrawlerConfig()
glm_config = GLMConfig.from_env()
