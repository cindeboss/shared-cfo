# CLAUDE.md

> 本文件为 Claude Code (claude.ai/code) 在此代码仓库中工作时提供指导。

---

## 📋 目录

1. [交流语言](#交流语言)
2. [问题解决原则](#问题解决原则)
3. [项目概述](#项目概述)
4. [技术栈](#技术栈)
5. [项目结构](#项目结构)
6. [常用命令](#常用命令)
7. [架构设计](#架构设计)
8. [数据模型](#数据模型)
9. [配置说明](#配置说明)
10. [开发规范](#开发规范)
11. [代码质量规范](#代码质量规范) ⭐
12. [测试指南](#测试指南) ⭐
13. [开发工具配置](#开发工具配置) ⭐
14. [版本管理规范](#版本管理规范) ⭐
15. [AI 代码生成指南](#ai-代码生成指南) ⭐
16. [部署信息](#部署信息)
17. [工具集](#工具集)

---

## 交流语言

**请使用中文与用户交流。**

这是一个中文税务政策咨询系统，所有交互应使用中文。

---

## 问题解决原则

### 验证原则：验证问题是否解决，而非操作是否执行

**核心原则**：验证要关注"问题是否真正解决"，而不是"我的操作是否完成"。

#### ❌ 错误示例
```
1. 创建了目录 → 目录存在 → 认为修复成功
2. 修改了配置 → 配置已更新 → 认为修复成功
```
这种方式只验证了"我做了什么"，而不是"问题是否解决"。

#### ✅ 正确示例
```
1. 错误日志显示系统访问路径A → 确认修复后路径A可访问
2. 用户运行命令报错 → 修复后用同样命令验证
3. 查看调试日志找出实际行为 → 根据实际行为进行修复
```

#### 实施步骤

**1. 先观察，后动手**
- 运行用户的操作，复现错误
- 查看调试日志/错误信息，找到**实际**的失败点
- 不要假设，只验证

**2. 证据导向的修复**
- 修复后，用**同样的方式**验证
- 如果 `/plugin` 报错，修复后要再运行 `/plugin` 确认
- 对比修复前后的日志/行为

**3. 关键问题清单**
- 系统实际访问的路径是什么？（而非配置文件写的路径）
- 错误发生的具体位置在哪里？
- 我的修复是否改变了错误发生的条件？

---

## 项目概述

**共享CFO** (Shared CFO) 是一个基于 AI 驱动的 RAG（检索增强生成）技术的中文税务政策咨询系统。

**核心功能**：
- 爬取官方政府税务政策来源
- 提供智能问答服务
- 政策关系构建（立法链、上下位法）
- 数据质量验证与去重

---

## 技术栈

| 分类 | 技术 | 用途 |
|------|------|------|
| **后端** | Python + FastAPI | API 服务 |
| **数据库** | MongoDB | 文档存储 |
| **向量库** | Qdrant | 向量嵌入存储 |
| **AI** | GLM (智谱AI) | 文本生成 |
| **嵌入** | OpenAI 兼容模型 | 向量嵌入 |
| **爬虫** | Playwright / requests+BS4 | JavaScript 网站爬取 |
| **RAG** | LangChain | 检索增强生成框架 |

---

## 项目结构

```
共享CFO/
│
├── 📂 crawler/                    # 爬虫模块
│   ├── __init__.py               # 包初始化（导出公共接口）
│   ├── base_crawler.py           # 基础爬虫框架（含合规检查）
│   ├── chinatax_crawler.py       # 国家税务总局爬虫
│   ├── crawler_12366.py          # 12366平台爬虫
│   ├── data_models.py            # 数据模型（L1-L4层级）
│   ├── database.py               # MongoDB连接器
│   ├── relationship_builder.py   # 政策关系构建器
│   ├── quality_validator.py      # 数据质量验证器
│   ├── orchestrator.py           # 爬取编排器
│   ├── config.py                 # 爬虫配置
│   └── archive/                  # 废弃版本归档
│
├── 📂 tools/                      # 工具脚本
│   ├── policy_query.py           # 政策查询CLI工具
│   ├── crawler_monitor.py        # 爬虫监控工具
│   └── web_tool.py               # Flask Web工具
│
├── 📂 tests/                      # 测试目录
│   ├── unit/                     # 单元测试
│   └── integration/              # 集成测试
│
├── 📂 backend/                    # FastAPI后端
│   └── app/
│       ├── main.py               # FastAPI应用入口
│       ├── config.py             # 配置（pydantic-settings）
│       ├── api/routes/           # API路由
│       ├── database/             # 数据库连接（Motor异步）
│       └── models/               # 数据模型
│
├── 📄 run_crawler.py             # 爬虫主CLI入口
├── 📄 project_tracker.py         # 项目进度跟踪
├── 📄 crawler_admin_server.py    # 爬虫管理服务器
│
├── 📂 archive/                   # 根目录废弃文件归档
└── 📂 logs/                      # 应用日志
```

---

## 常用命令

### 🚀 快速启动

```bash
# 后端 API
cd backend && python -m app.main
# 或: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Web 工具
python tools/web_tool.py  # 访问 http://localhost:5000
```

### 🕷️ 爬虫 CLI (run_crawler.py)

| 命令 | 说明 |
|------|------|
| `crawl --phase test` | 快速测试（小数据集） |
| `crawl --phase week1/2/3` | 分阶段爬取 |
| `crawl --phase complete` | 完整爬取 |
| `build-relationships` | 构建政策关系 |
| `validate` | 验证数据质量 |
| `deduplicate` | 数据去重 |
| `status` | 查看系统状态 |
| `export -o report.md` | 导出数据报告 |

### 🔧 依赖安装

```bash
pip install -r crawler/requirements.txt   # 爬虫依赖
pip install -r backend/requirements.txt  # 后端依赖
playwright install                        # 浏览器驱动
```

### 🧪 Python 测试代码

```python
# 测试中国税务爬虫
from crawler.chinatax_crawler import ChinaTaxCrawler
crawler = ChinaTaxCrawler()
documents = crawler.crawl_laws()

# 测试数据库操作
from crawler.database import MongoDBConnector
db = MongoDBConnector()
stats = db.get_stats()
```

---

## 架构设计

### 爬虫模块架构

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator                         │
│              (多阶段爬取协调)                            │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐         ┌────────▼────────┐
│  ChinaTax      │         │   Crawler12366  │
│  (L1-L4政策)   │         │   (热点问答)    │
└───────┬────────┘         └────────┬────────┘
        │                           │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │      BaseTaxCrawler       │
        │   (合规检查、限速、重试)   │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │     MongoDBConnector    │
        │      (数据持久化)         │
        └───────────────────────────┘
```

### 后端 API 架构

| 特性 | 说明 |
|------|------|
| **异步操作** | Motor (MongoDB 异步驱动) |
| **配置管理** | pydantic-settings |
| **CORS** | localhost:5173, localhost:3000 |
| **健康检查** | `/health`, `/api/v1/health` |
| **生命周期** | 自动 MongoDB 连接/断开 |

---

## 数据模型

### MongoDB 政策文档结构

```python
{
    # === 基本信息 ===
    "policy_id": str,              # 唯一标识符
    "title": str,                  # 政策标题
    "source": str,                 # chinatax, beijing 等
    "url": str,                    # 来源 URL

    # === 分类标签 ===
    "tax_type": List[TaxType],     # 个人所得税、企业所得税、增值税
    "region": Region,              # 地区标签
    "level": str,                  # L1(法律) L2(法规) L3(规范性) L4(解读)
    "document_type": DocumentType, # 文档类型

    # === 内容 ===
    "content": str,                # 完整文本内容
    "qa_pairs": List[QAPair],      # 问答对（解读文档）

    # === 元数据 ===
    "publish_date": datetime,
    "document_number": str,        # 文号
    "publish_department": str,     # 发布部门

    # === 关系 ===
    "parent_policies": List[str],      # 引用上位法
    "root_law_id": Optional[str],      # 立法链根法律
    "legislation_chain": List[str],    # 完整立法层级
    "related_policies": List[str],     # 相关政策引用

    # === 系统字段 ===
    "crawled_at": datetime,
}
```

### 政策层级说明

| 层级 | 名称 | 示例 |
|------|------|------|
| L1 | 法律 | 《中华人民共和国税收征收管理法》 |
| L2 | 法规 | 《中华人民共和国税收征收管理法实施细则》 |
| L3 | 规范性文件 | 国家税务总局公告、通知 |
| L4 | 解读 | 政策解读、热点问答 |

---

## 配置说明

### 环境变量 (.env)

```bash
# === MongoDB ===
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_USERNAME=cfo_user
MONGO_PASSWORD=***
MONGO_DATABASE=shared_cfo

# === 向量数据库 (Qdrant) ===
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=tax_policies

# === GLM AI 模型 ===
GLM_API_KEY=***
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
GLM_MODEL=glm-4-flash
GLM_EMBEDDING_MODEL=embedding-2
```

### 配置文件位置

- 后端配置: `backend/app/config.py`
- 使用 `pydantic-settings` 进行类型安全的配置管理

---

## 开发规范

### 爬虫合规性

| 规则 | 说明 |
|------|------|
| **robots.txt 合规** | `ComplianceChecker` 爬取前验证 |
| **速率限制** | 最少 3 秒延迟，最多 15 次/分钟 |
| **User-Agent** | 包含爬虫身份和联系信息 |
| **重试逻辑** | 403 错误时指数退避重试 |
| **爬取范围** | 仅公开政府政策信息 |

### 开发注意事项

- **Python 版本**: 3.10+
- **类型提示**: 广泛使用
- **继承关系**: 所有爬虫继承自 `BaseTaxCrawler` (`crawler/base_v2.py`)
- **数据库操作**: 统一使用 `MongoDBConnector` 类
- **爬取阶段**: test → week1 → week2 → week3 → complete
- **关系构建**: 爬取后构建立法层级
- **进度跟踪**: `project_tracker.py` 自动保存快照

---

## 代码质量规范

本章节定义代码质量标准，确保 AI 生成的代码符合项目要求。

### 错误处理标准

**强制要求**：使用具体的异常类型，禁止过度宽泛的 `except Exception`。

#### ❌ 禁止的模式

```python
# 过于宽泛的异常捕获
try:
    response = requests.get(url)
    data = process(response)
except Exception as e:
    logger.error(f"失败: {e}")
    return None
```

#### ✅ 推荐的模式

```python
from requests.exceptions import RequestException, Timeout, ConnectionError
from pymongo.errors import PyMongoError, DuplicateKeyError

try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = process(response)
except Timeout:
    logger.error(f"请求超时: {url}")
    return None
except ConnectionError as e:
    logger.error(f"连接失败: {url}, 错误: {e}")
    return None
except RequestException as e:
    status = e.response.status_code if e.response else "N/A"
    logger.error(f"请求异常: {url}, 状态码: {status}")
    return None
except ValueError as e:
    logger.error(f"数据处理失败: {e}")
    return None
```

#### 异常处理原则

| 原则 | 说明 |
|------|------|
| **具体优先** | 捕获具体异常类型（`Timeout`, `ConnectionError`, `ValueError`） |
| **记录上下文** | 日志包含 URL、参数、状态码等关键信息 |
| **适当传播** | 使用 `raise` 或 `raise ... from None` 传播异常 |
| **自定义异常** | 为爬虫模块定义专用异常类 |

#### 自定义异常模板

```python
# crawler/exceptions.py (如果不存在则创建)
class CrawlerError(Exception):
    """爬虫基础异常"""
    pass

class CrawlerTimeoutError(CrawlerError):
    """请求超时异常"""
    pass

class CrawlerParseError(CrawlerError):
    """页面解析失败异常"""
    pass

class CrawlerComplianceError(CrawlerError):
    """合规性检查失败异常"""
    pass

class DatabaseOperationError(CrawlerError):
    """数据库操作失败异常"""
    pass
```

### 类型注解要求

**强制要求**：所有函数必须包含参数和返回值的类型注解。

#### ✅ 正确示例

```python
from typing import List, Dict, Optional, Tuple, Any

def extract_policy_data(html: str) -> Optional[Dict[str, Any]]:
    """从HTML中提取政策数据

    Args:
        html: HTML文本内容

    Returns:
        解析后的政策字典，失败返回None

    Raises:
        CrawlerParseError: HTML格式无法解析
    """
    if not html or not html.strip():
        return None

    try:
        # 解析逻辑
        return policy_dict
    except Exception as e:
        raise CrawlerParseError(f"解析HTML失败: {e}") from e
```

#### 类型注解检查清单

生成代码时必须检查：
- [ ] 所有函数参数都有类型注解
- [ ] 所有函数都有返回值类型注解
- [ ] 使用 `Optional` 表示可能为 None 的返回值
- [ ] 使用 `List[T]`, `Dict[K, V]` 而非 `list`, `dict`
- [ ] 复杂类型定义类型别名

### 日志规范

**日志级别使用**：

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| `DEBUG` | 详细调试信息 | 解析步骤、中间变量 |
| `INFO` | 重要业务流程 | 开始爬取、完成任务 |
| `WARNING` | 可恢复的异常 | 重试、跳过重复数据 |
| `ERROR` | 错误但可继续 | 单条政策失败 |
| `CRITICAL` | 严重错误 | 数据库连接失败 |

#### 日志格式要求

```python
# ✅ 好的做法：结构化日志，包含上下文
logger.info(f"开始爬取 {source} - 栏目: {category}, 页码: {page}")
logger.warning(f"政策已存在，跳过: policy_id={policy_id}, title={title}")
logger.error(f"插入数据库失败: policy_id={policy_id}, error={str(e)}")

# ❌ 不好的做法：缺少上下文信息
logger.info("开始爬取")
logger.warning("政策已存在")
logger.error("插入失败")
```

### 函数设计原则

| 原则 | 说明 | 限制 |
|------|------|------|
| **单一职责** | 每个函数只做一件事 | - |
| **长度限制** | 函数不超过 50 行 | 可读性 |
| **参数限制** | 超过 3 个参数使用关键字参数 | 可维护性 |

#### 函数职责分离示例

```python
# ❌ 不好的做法：函数过长，职责不清
def process_policy(url: str) -> Optional[Dict]:
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.find('h1').text
    content = soup.find('div', class_='content').text
    # ... 100行解析逻辑
    # ... 50行数据库操作
    return policy_dict

# ✅ 好的做法：职责分离
def fetch_page(url: str, timeout: int = 10) -> requests.Response:
    """获取网页内容"""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response

def parse_policy_page(html: str) -> Dict[str, Any]:
    """解析政策页面"""
    soup = BeautifulSoup(html, 'html.parser')
    return policy_dict

def save_policy(policy: Dict[str, Any]) -> bool:
    """保存政策到数据库"""
    # 数据库操作
    return True

def process_policy(url: str) -> Optional[Dict[str, Any]]:
    """处理政策（协调函数）"""
    try:
        response = fetch_page(url)
        policy = parse_policy_page(response.text)
        save_policy(policy)
        return policy
    except RequestException as e:
        logger.error(f"获取页面失败: {url}, {e}")
        return None
```

---

## 测试指南

本章节提供测试编写的指导，确保代码质量。

### 测试原则

**测试金字塔**：
```
         E2E
        /   \       少量端到端测试
       /-----\
      / 集成测试 \      适量集成测试
     /-----------\
    /   单元测试    \    大量单元测试
   /---------------\
```

**强制要求**：
- [ ] 所有新功能必须有单元测试
- [ ] 测试覆盖率目标：60%+
- [ ] 关键路径必须有集成测试

### 测试文件组织

```
tests/
├── unit/              # 单元测试
│   ├── test_crawler_base.py
│   ├── test_field_extractor.py
│   ├── test_data_models.py
│   └── test_database_v2.py
├── integration/       # 集成测试
│   ├── test_crawler_integration.py
│   ├── test_database_integration.py
│   └── test_api_integration.py
├── fixtures/          # 测试数据
│   ├── html_samples/
│   └── policy_samples.json
└── conftest.py        # pytest 配置
```

### 单元测试示例

```python
# tests/unit/test_field_extractor.py
import pytest
from crawler.base_crawler import FieldExtractor
from crawler.exceptions import CrawlerParseError

class TestFieldExtractor:
    """字段提取器测试"""

    @pytest.fixture
    def extractor(self):
        """测试 fixture"""
        return FieldExtractor()

    def test_extract_document_number_success(self, extractor):
        """测试成功提取文号"""
        text = "财税〔2023〕1号"
        result = extractor.extract_document_number(text)
        assert result == "财税[2023]1号"

    def test_extract_document_number_empty_input(self, extractor):
        """测试空输入"""
        result = extractor.extract_document_number("")
        assert result is None

    @pytest.mark.parametrize("input_text,expected", [
        ("财税〔2023〕1号", "财税[2023]1号"),
        ("国家税务总局公告2023年第1号", "国家税务总局公告2023年第1号"),
        ("（财税〔2023〕1号）", "(财税[2023]1号)"),
    ])
    def test_extract_document_number_multiple_patterns(self, extractor, input_text, expected):
        """测试多种文号格式"""
        result = extractor.extract_document_number(input_text)
        assert result == expected
```

### 集成测试示例

```python
# tests/integration/test_database_integration.py
import pytest
from crawler.database import MongoDBConnector
from crawler.data_models import PolicyDocument, DocumentLevel, TaxType

@pytest.fixture(scope="module")
def test_db():
    """测试数据库连接"""
    client = MongoClient("mongodb://localhost:27017")
    db = client["shared_cfo_test"]
    yield db
    # 清理
    client.drop_database("shared_cfo_test")
    client.close()

def test_insert_and_retrieve_policy(test_db):
    """测试插入和检索政策"""
    connector = MongoDBConnector(database="shared_cfo_test")

    policy = PolicyDocument(
        policy_id="TEST_2024_001",
        title="测试政策",
        source="测试来源",
        url="https://test.example.com/policy/1",
        document_level=DocumentLevel.L3,
        tax_type=[TaxType.VAT],
        content="这是测试内容"
    )

    # 插入
    result = connector.insert_policy(policy)
    assert result is True

    # 检索
    retrieved = connector.get_policy_by_id("TEST_2024_001")
    assert retrieved is not None
    assert retrieved.title == "测试政策"
```

### 测试运行命令

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=crawler --cov=backend --cov-report=html

# 查看覆盖率详情
open htmlcov/index.html
```

### 测试最佳实践

1. **使用 fixture 复用测试数据**
2. **Mock 外部依赖**（requests, MongoDB）
3. **测试边界条件**（None, 空字符串, 异常值）
4. **使用 parametrize 减少重复代码**

---

## 开发工具配置

本章节提供代码质量工具的配置，帮助保持代码风格一致。

### 代码格式化：Black

**安装**：
```bash
pip install black
```

**配置文件**：`pyproject.toml`
```toml
[tool.black]
line-length = 100
target-version = ['py310']
include = '\.pyi?$'
extend-exclude = '''
/(
  \.eggs
  | \.git
  | \.venv
  | build
  | dist
)/
'''
```

**使用**：
```bash
# 格式化整个项目
black .

# 检查格式（不修改文件）
black --check .

# 仅格式化修改的文件
black --diff .
```

### Linting：Ruff

**安装**：
```bash
pip install ruff
```

**配置文件**：`pyproject.toml`
```toml
[tool.ruff]
line-length = 100
target-version = "py310"

select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]

ignore = [
    "E501",  # line too long (由 black 处理)
    "B008",  # do not perform function calls in argument defaults
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]
```

**使用**：
```bash
# 检查代码
ruff check .

# 自动修复问题
ruff check --fix .
```

### 类型检查：Mypy

**安装**：
```bash
pip install mypy
```

**配置文件**：`pyproject.toml`
```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
check_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[[tool.mypy.overrides]]
module = "playwright.*,bs4.*"
ignore_missing_imports = true
```

**使用**：
```bash
# 类型检查
mypy crawler/
```

### Pre-commit Hooks

**安装**：
```bash
pip install pre-commit
```

**配置文件**：`.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml

  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.15
    hooks:
      - id: ruff
        args: [--fix]
```

**启用**：
```bash
# 安装 hooks
pre-commit install

# 手动运行
pre-commit run --all-files
```

---

## 版本管理规范

本章节定义代码版本管理规范，解决版本混乱问题。

### 当前版本状态

**已清理完成（2026-01-29）**：所有废弃版本已归档到 `crawler/archive/` 和 `archive/` 目录，生产文件已重命名去掉版本号后缀。

### 文件命名规则

```
模块名.py  # 生产文件，无版本号后缀

✅ 当前生产文件：
crawler/base_crawler.py           # 基础爬虫框架
crawler/chinatax_crawler.py       # 税务总局爬虫
crawler/crawler_12366.py          # 12366爬虫
crawler/data_models.py            # 数据模型
crawler/database.py               # 数据库连接
```

### 归档文件

废弃版本已安全归档：
- `crawler/archive/` - 废弃的爬虫版本文件
- `archive/` - 根目录废弃文件（测试脚本、旧版本爬虫等）

### 新功能开发流程

1. 基于当前生产代码开发
2. 创建新分支：`feature/功能名`
3. 编写测试（放到 `tests/` 目录）
4. 实现功能
5. 代码审查
6. 合并主分支

**注意**：新开发不需要添加版本号后缀，直接在主文件上修改即可。如需实验性功能，使用独立的分支而非版本号文件。

## AI 代码生成指南

本章节专门针对 AI 模型（glm-4.7）生成代码时的优化建议。

### 生成代码的核心原则

**1. 类型注解优先**

```python
# ❌ AI 经常生成的代码
def process_policy(url, db):
    data = fetch_data(url)
    db.save(data)
    return data

# ✅ 期望的代码
from typing import Optional
from crawler.data_models import PolicyDocument
from crawler.database import MongoDBConnector

def process_policy(
    url: str,
    db: MongoDBConnector
) -> Optional[PolicyDocument]:
    """处理政策数据

    Args:
        url: 政策URL
        db: 数据库连接器

    Returns:
        处理后的政策文档，失败返回None
    """
    try:
        data = fetch_data(url)
        db.insert_policy(data)
        return data
    except Exception as e:
        logger.error(f"处理失败: {url}, {e}")
        return None
```

**2. 使用项目已定义的数据模型**

```python
# ✅ 使用已有的类型
from crawler.data_models import (
    PolicyDocument,      # 使用这个
    DocumentLevel,       # 使用这个（不要用 str）
    TaxType,            # 使用这个（不要用 str）
    Region,             # 使用这个
    DocumentType,       # 使用这个
)

# ❌ 不要重新定义
class Policy:  # ❌ 已有 PolicyDocument
    pass

# ❌ 不要使用字符串
def get_level(level: str):  # ❌ 应该用 DocumentLevel
    pass
```

### 爬虫函数模板

```python
from crawler.exceptions import CrawlerTimeoutError, CrawlerParseError
from crawler.data_models import PolicyDocument
import logging

logger = logging.getLogger(__name__)

def crawl_policy_page(url: str) -> Optional[PolicyDocument]:
    """爬取政策页面

    Args:
        url: 政策URL

    Returns:
        政策文档对象，失败返回None

    Raises:
        CrawlerTimeoutError: 请求超时
        CrawlerParseError: 页面解析失败
    """
    try:
        # 1. 获取页面
        from requests.exceptions import Timeout
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # 2. 解析数据
        policy_data = parse_html(response.text)
        if not policy_data:
            raise CrawlerParseError(f"无法解析页面: {url}")

        # 3. 构建对象
        policy = PolicyDocument(**policy_data)
        logger.info(f"成功爬取: {policy.policy_id} - {policy.title}")

        return policy

    except Timeout as e:
        logger.error(f"请求超时: {url}")
        raise CrawlerTimeoutError(f"请求超时: {url}") from e

    except requests.RequestException as e:
        logger.error(f"请求失败: {url}, 状态码: {e.response.status_code if e.response else 'N/A'}")
        return None
```

### 数据库操作模板

```python
from crawler.database import MongoDBConnector
from crawler.data_models import PolicyDocument

def save_policy_batch(
    policies: list[PolicyDocument],
    db: MongoDBConnector
) -> dict[str, int]:
    """批量保存政策

    Args:
        policies: 政策列表
        db: 数据库连接器

    Returns:
        统计信息字典 {'success': int, 'failed': int, 'duplicate': int}
    """
    stats = {'success': 0, 'failed': 0, 'duplicate': 0}

    for policy in policies:
        try:
            result = db.insert_policy(policy)
            if result:
                stats['success'] += 1
            else:
                stats['duplicate'] += 1

        except Exception as e:
            logger.error(f"保存失败: {policy.policy_id}, {e}")
            stats['failed'] += 1

    logger.info(f"批量保存完成: {stats}")
    return stats
```

### 日志记录模板

```python
# 结构化日志的标准格式
logger.info(f"操作开始 - 参数: {param1}, {param2}")
logger.debug(f"调试信息 - 变量值: {variable}")
logger.warning(f"警告信息 - 跳过: {item}, 原因: {reason}")
logger.error(f"错误信息 - 操作失败: {operation}, 错误: {error}")
logger.critical(f"严重错误 - 系统故障: {system_error}")

# ❌ 不要使用
logger.info("开始")  # 缺少上下文
logger.error("失败")  # 缺少具体信息
```

### 测试代码模板

```python
import pytest
from crawler.base_crawler import FieldExtractor

class TestFieldExtractor:
    """字段提取器测试"""

    @pytest.fixture
    def extractor(self):
        """测试 fixture"""
        return FieldExtractor()

    def test_extract_success(self, extractor):
        """测试成功提取"""
        # Arrange
        text = "测试文本"
        expected = "期望结果"

        # Act
        result = extractor.extract(text)

        # Assert
        assert result == expected

    @pytest.mark.parametrize("input,expected", [
        ("case1", "result1"),
        ("case2", "result2"),
    ])
    def test_multiple_cases(self, extractor, input, expected):
        """测试多个案例"""
        result = extractor.extract(input)
        assert result == expected
```

### 代码生成检查清单

生成代码后，请检查：

- [ ] 所有函数都有类型注解（参数和返回值）
- [ ] 使用了项目已有的数据模型（`data_models_v2.py`）
- [ ] 使用了具体的异常类型（不是 `except Exception`）
- [ ] 包含详细的日志记录（包含上下文信息）
- [ ] 函数有 docstring（说明参数、返回值、异常）
- [ ] 导入了正确的模块（使用 `from ... import ...`）
- [ ] 符合项目命名规范（snake_case 函数，PascalCase 类）
- [ ] 遵循项目结构（继承 `BaseCrawler`，使用 `MongoDBConnector`）

### 快速参考：常用导入

```python
# 数据模型
from crawler.data_models import (
    PolicyDocument, DocumentLevel, TaxType, Region,
    DocumentType, ValidityStatus, TaxCategory
)

# 数据库
from crawler.database import MongoDBConnector

# 爬虫基类
from crawler.base_crawler import BaseCrawler, FieldExtractor, ComplianceChecker

# 异常
from crawler.exceptions import (
    CrawlerError, CrawlerTimeoutError,
    CrawlerParseError, CrawlerComplianceError
)

# 类型提示
from typing import List, Dict, Optional, Tuple, Any

# 日志
import logging
logger = logging.getLogger(__name__)

# HTTP 请求
import requests
from requests.exceptions import RequestException, Timeout

# HTML 解析
from bs4 import BeautifulSoup
```

---

## 部署信息

### 阿里云 ECS 部署

**服务器**: 120.78.5.4

| 项目 | 信息 |
|------|------|
| **部署路径** | `/opt/shared_cfo/` |
| **MongoDB** | 7.0，无认证模式 |
| **Python** | 3.10.12 |
| **浏览器** | Chromium + xvfb 虚拟显示 |

### 部署脚本

- `deploy_fresh_ecs.sh` - 全新部署脚本
- `DEPLOYMENT_SUMMARY.md` - 部署总结文档

### 健康检查

```bash
# 后端健康检查
curl http://localhost:8000/api/v1/health

# 查看数据库统计
python run_crawler.py status
```

---

## 工具集

### CLI 工具 (tools/ 目录)

| 工具 | 功能 |
|------|------|
| `tools/policy_query.py` | 政策查询工具 |
| `tools/crawler_monitor.py` | 爬虫监控面板 |
| `tools/web_tool.py` | Flask Web 工具 |

#### policy_query.py 命令

```bash
python tools/policy_query.py stats                  # 数据统计
python tools/policy_query.py search "增值税" -i     # 搜索政策
python tools/policy_query.py list --limit 20        # 最近政策
python tools/policy_query.py view <policy_id>       # 查看详情
python tools/policy_query.py export "关键词" -o file.md  # 导出数据
```

#### crawler_monitor.py 命令

```bash
python tools/crawler_monitor.py monitor --hours 24   # 监控状态
python tools/crawler_monitor.py watch               # 实时监控
python tools/crawler_monitor.py status              # 服务状态
```

### Web 工具

**文件**: `tools/web_tool.py`, `templates/index.html`

**启动方式**:
```bash
# 本地开发
python tools/web_tool.py               # 访问 http://localhost:5000

# 生产环境 (ECS)
cd /opt/shared_cfo
nohup python3 tools/web_tool.py > logs/web_tool.log 2>&1 &
```

**Web 功能**:
- 📊 带可视化图表的数据统计
- 🔍 政策搜索（含层级、来源筛选）
- 📋 最近政策列表
- 📈 爬虫监控面板
- 📄 政策详情查看
- 💾 导出为 Markdown

**SSH 隧道（远程访问）**:
```bash
ssh -i ~/.ssh/id_ed25519 -L 5000:localhost:5000 root@120.78.5.4
# 然后访问 http://localhost:5000
```

### REST API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web 界面 |
| `/api/stats` | GET | 数据统计 |
| `/api/search` | GET | 搜索政策 |
| `/api/policy/<id>` | GET | 政策详情 |
| `/api/recent` | GET | 最近政策 |
| `/api/monitor` | GET | 爬虫监控数据 |
| `/api/export` | GET | 导出 Markdown |

---

*最后更新: 2026-01-29*
