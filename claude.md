# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication Language

**请使用中文与用户交流。** Please use Chinese when communicating with the user. This is a Chinese tax policy consultation system, and all interactions should be in Chinese.

## Problem-Solving Principles

### 验证原则：验证问题是否解决，而非操作是否执行

**核心原则**：验证要关注"问题是否真正解决"，而不是"我的操作是否完成"。

#### 错误示例 ❌
```
1. 创建了目录 → 目录存在 → 认为修复成功
2. 修改了配置 → 配置已更新 → 认为修复成功
```
这种方式只验证了"我做了什么"，而不是"问题是否解决"。

#### 正确示例 ✅
```
1. 错误日志显示系统访问路径A → 确认修复后路径A可访问
2. 用户运行命令报错 → 修复后用同样命令验证
3. 查看调试日志找出实际行为 → 根据实际行为进行修复
```

#### 实施步骤

1. **先观察，后动手**
   - 运行用户的操作，复现错误
   - 查看调试日志/错误信息，找到**实际**的失败点
   - 不要假设，只验证

2. **证据导向的修复**
   - 修复后，用**同样的方式**验证
   - 如果 `/plugin` 报错，修复后要再运行 `/plugin` 确认
   - 对比修复前后的日志/行为

3. **关键问题清单**
   - 系统实际访问的路径是什么？（而非配置文件写的路径）
   - 错误发生的具体位置在哪里？
   - 我的修复是否改变了错误发生的条件？

## Project Overview

**共享CFO** (Shared CFO) is a Chinese tax policy consultation system built with AI-powered RAG (Retrieval-Augmented Generation) capabilities. It crawls official government tax policy sources and provides intelligent Q&A services.

### Technology Stack

- **Backend**: Python with FastAPI
- **Database**: MongoDB for document storage, Qdrant for vector embeddings
- **AI**: GLM (zhipuai) for text generation, OpenAI-compatible embeddings
- **Crawler**: Playwright for JavaScript-heavy sites, requests/BeautifulSoup for basic crawling
- **RAG Framework**: LangChain

## Project Structure

```
共享CFO/
├── crawler/              # Crawler module
│   ├── base_v2.py       # Base crawler framework with compliance checking
│   ├── chinatax_crawler_v4.py  # National Tax Administration crawler
│   ├── crawler_12366_v2.py     # 12366 platform crawler
│   ├── data_models_v2.py       # Data models (PolicyDocument with L1-L4 hierarchy)
│   ├── database_v2.py          # MongoDB connector
│   ├── relationship_builder.py # Policy relationship builder
│   ├── quality_validator.py    # Data quality validator
│   └── orchestrator.py         # Crawl orchestrator
├── backend/              # FastAPI backend
│   └── app/
│       ├── main.py       # FastAPI application entry
│       ├── config.py     # Configuration (pydantic-settings)
│       ├── api/routes/   # API routes
│       ├── database/     # Database connections (Motor for async MongoDB)
│       └── models/       # Data models
├── run_crawler.py        # Main CLI entry point for crawler
├── project_tracker.py    # Project progress tracking
└── logs/                 # Application logs
```

## Common Commands

### Backend API

```bash
# Start the FastAPI backend
cd backend && python -m app.main

# Or using uvicorn directly
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health
```

### Crawler CLI

The crawler uses a CLI interface via `run_crawler.py`:

```bash
# Quick test crawl (small dataset)
python run_crawler.py crawl --phase test

# Full crawl phases
python run_crawler.py crawl --phase week1
python run_crawler.py crawl --phase week2
python run_crawler.py crawl --phase week3
python run_crawler.py crawl --phase complete

# Build policy relationships (parent-child, legislative chains)
python run_crawler.py build-relationships

# Validate data quality
python run_crawler.py validate

# Data deduplication
python run_crawler.py deduplicate

# View system status
python run_crawler.py status

# Export data report
python run_crawler.py export -o report.md
```

### Dependencies

```bash
# Install crawler dependencies
pip install -r crawler/requirements.txt

# Install backend dependencies
pip install -r backend/requirements.txt

# Install Playwright browsers (for JavaScript-heavy sites)
playwright install
```

### Testing Individual Crawler Modules

```python
# Test ChinaTax crawler
from crawler.chinatax_crawler_v4 import ChinaTaxCrawler
crawler = ChinaTaxCrawler()
documents = crawler.crawl_laws()

# Test database operations
from crawler.database_v2 import MongoDBConnectorV2
db = MongoDBConnectorV2()
stats = db.get_stats()
```

## Architecture

### Crawler Module

The crawler follows a modular architecture:

1. **Base Crawler** (`base_v2.py`): Abstract base class with:
   - `ComplianceChecker`: Validates robots.txt, enforces rate limiting (min 3s between requests)
   - Field extraction utilities (document numbers, dates, hierarchy detection)
   - Retry logic with backoff

2. **Source Crawlers**: Individual crawlers for different tax authorities:
   - `ChinaTaxCrawler`: National Tax Administration (L1-L4 policies)
   - `Crawler12366`: 12366 platform (hot Q&A)

3. **Orchestrator** (`orchestrator.py`): Coordinates multi-phase crawling:
   - `run_quick_test()`: Test with small dataset
   - `run_phase1_week1/2/3()`: Phase-based crawling
   - `run_phase1_complete()`: Full phase 1 execution

4. **Relationship Builder** (`relationship_builder.py`): Builds policy relationships:
   - Parent-child relationships (superior-subordinate laws)
   - Legislative chains (complete hierarchy from root to leaf)
   - Related policies and Q&A linking

5. **Quality Validator** (`quality_validator.py`): Validates and deduplicates data

### Backend API

FastAPI-based REST API with:
- **Async database operations** using Motor (MongoDB async driver)
- **Centralized configuration** via `config.py` using pydantic-settings
- **CORS middleware** for frontend integration (origins: localhost:5173, localhost:3000)
- **Health check endpoints**: `/health` and `/api/v1/health`
- **Lifespan management**: Automatic MongoDB connect/disconnect

### Data Model

Policies are stored with the following structure in MongoDB:

```python
{
    "policy_id": str,           # Unique identifier
    "title": str,               # Policy title
    "source": str,              # chinatax, beijing, etc.
    "url": str,                 # Source URL
    "tax_type": List[TaxType],  # IIT, CIT, VAT, etc.
    "region": Region,           # Regional tags
    "level": str,               # L1 (laws), L2 (regulations), L3 (normative), L4 (interpretations)
    "document_type": DocumentType,
    "content": str,             # Full text content
    "qa_pairs": List[QAPair],   # For interpretation documents
    "publish_date": datetime,
    "document_number": str,
    "publish_department": str,
    "parent_policies": List[str],     # References to superior laws
    "root_law_id": Optional[str],     # Root law in legislative chain
    "legislation_chain": List[str],   # Complete legislative hierarchy
    "related_policies": List[str],    # Related policy references
    "crawled_at": datetime,
}
```

## Configuration

Configuration is managed through environment variables in `.env`:

```bash
# MongoDB
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_USERNAME=cfo_user
MONGO_PASSWORD=***
MONGO_DATABASE=shared_cfo

# Vector Database (Qdrant)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=tax_policies

# GLM AI Model
GLM_API_KEY=***
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
GLM_MODEL=glm-4-flash
GLM_EMBEDDING_MODEL=embedding-2
```

The backend uses `pydantic-settings` for type-safe configuration (see `backend/app/config.py`).

## Crawler Compliance

The crawler implements ethical web scraping practices:
- **robots.txt compliance**: `ComplianceChecker` validates against robots.txt before crawling
- **Rate limiting**: Minimum 3-second delays between requests, max 15 requests/minute
- **User-Agent**: Includes crawler identity and contact information
- **Retry logic**: Automatic retry with exponential backoff on 403 errors
- **Scope**: Only crawls publicly available government policy information

## Development Notes

- **Python version**: 3.10+
- **Type hints**: Used extensively throughout the codebase
- **All crawlers inherit from `BaseTaxCrawler`** in `crawler/base_v2.py`
- **Database operations**: Use `MongoDBConnectorV2` class for consistency
- **Orchestrator phases**: The crawler operates in phases (test → week1 → week2 → week3 → complete)
- **Policy relationships**: Built after crawling to establish legislative hierarchy
- **Project tracking**: `project_tracker.py` automatically saves progress snapshots

## Deployment

The project is deployed on Alibaba Cloud ECS (120.78.5.4):
- **Location**: `/opt/shared_cfo/`
- **MongoDB**: Version 7.0 running without auth mode
- **Python**: 3.10.12
- **Playwright**: Chromium browser with xvfb for virtual display

For deployment scripts, see `deploy_fresh_ecs.sh` and `DEPLOYMENT_SUMMARY.md`.

## Running Tests

```bash
# Quick crawler test
python run_crawler.py crawl --phase test

# Backend health check
curl http://localhost:8000/api/v1/health

# View database stats
python run_crawler.py status
```

## Query & Monitoring Tools

### Local CLI Tools

Located in project root:

- **policy_query.py**: Command-line tool for querying crawled policies
- **crawler_monitor.py**: Monitoring dashboard for crawler status
- **启动工具.bat**: Windows launcher (interactive menu)

```bash
# View data statistics
python policy_query.py stats

# Search policies
python policy_query.py search "增值税" --interactive

# List recent policies
python policy_query.py list --limit 20

# View policy detail
python policy_query.py view <policy_id>

# Export data
python policy_query.py export "关键词" -o export.md

# Monitor crawler status
python crawler_monitor.py monitor --hours 24

# Real-time monitoring
python crawler_monitor.py watch

# Check crawler service
python crawler_monitor.py status
```

### Web Tool

A Flask-based web interface for querying and monitoring:

- **web_tool.py**: Flask web server
- **templates/index.html**: Web UI
- **启动Web工具.bat**: Windows launcher

**Start Web Tool:**
```bash
# Local development
python web_tool.py
# Access at http://localhost:5000

# On ECS server (production)
cd /opt/shared_cfo
nohup python3 web_tool.py > logs/web_tool.log 2>&1 &
```

**Web Features:**
- 📊 Data statistics with visual charts
- 🔍 Policy search with filters (level, source)
- 📋 Recent policies list
- 📈 Crawler monitoring dashboard
- 📄 Policy detail view
- 💾 Export to Markdown

**SSH Tunnel (for remote access):**
```bash
ssh -i ~/.ssh/id_ed25519 -L 5000:localhost:5000 root@120.78.5.4
# Then access at http://localhost:5000
```

### API Endpoints

The web tool exposes these REST APIs:

- `GET /` - Web interface
- `GET /api/stats` - Data statistics
- `GET /api/search?keyword=...&level=...&source=...` - Search policies
- `GET /api/policy/<policy_id>` - Policy detail
- `GET /api/recent?limit=...` - Recent policies
- `GET /api/monitor?hours=...` - Crawler monitoring data
- `GET /api/export` - Export data as Markdown
