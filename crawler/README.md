# 税务政策爬虫

## 项目简介

税务政策爬虫用于爬取国家税务总局及各地方税务局的政策法规、解读和问答内容，为"共享CFO"产品提供数据基础。

## 功能特点

- 支持多数据源：国家税务总局、12366、北京、上海、广东等
- 智能去重：基于policy_id自动去重
- 数据验证：自动筛选目标税种和时间范围
- 可扩展：模块化设计，易于添加新数据源
- 云端部署：支持阿里云MongoDB存储

## 项目结构

```
crawler/
├── __init__.py           # 包初始化
├── config.py             # 配置文件
├── data_models.py        # 数据模型
├── base.py              # 基础爬虫类
├── chinatax_crawler.py  # 国家税务总局爬虫
├── local_tax_crawler.py # 地方税务局爬虫
├── database.py          # 数据库操作
├── run.py              # 主入口
├── requirements.txt     # 依赖包
└── README.md           # 说明文档
```

## 安装

### 1. 克隆项目

```bash
cd /path/to/Claude项目/共享CFO
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r crawler/requirements.txt
```

### 4. 配置环境变量

创建 `.env` 文件：

```bash
# MongoDB配置
MONGO_HOST=your-mongo-host
MONGO_PORT=27017
MONGO_USERNAME=your-username
MONGO_PASSWORD=your-password
MONGO_DATABASE=shared_cfo
MONGO_COLLECTION=policies

# Qdrant配置
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=tax_policies

# GLM配置
GLM_API_KEY=your-api-key
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
GLM_MODEL=glm-4-flash
```

## 使用方法

### 命令行运行

```bash
# 爬取国家税务总局政策
python -m crawler.run --source chinatax --start-year 2022 --end-year 2025

# 爬取北京税务局热点问答
python -m crawler.run --source beijing --channel hot_iit

# 爬取上海税务局所有栏目
python -m crawler.run --source shanghai --channel all

# 爬取所有数据源
python -m crawler.run --source all
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| --source | 数据源 (chinatax, beijing, shanghai, guangdong, all) | chinatax |
| --channel | 栏目名称 (all, interpretation, hot_qa, hot_iit, hot_cit) | all |
| --start-year | 起始年份 | 2022 |
| --end-year | 结束年份 | 2025 |
| --limit | 每次获取数量 | 20 |

### Python代码调用

```python
from crawler import ChinaTaxCrawler, MongoDBConnector

# 创建爬虫实例
crawler = ChinaTaxCrawler()

# 创建数据库连接
db = MongoDBConnector()

# 爬取数据
documents = crawler.crawl_channel('latest', start_year=2022, end_year=2025)

# 保存到数据库
stats = db.insert_policies(documents)
print(f"保存成功: {stats['success']}, 重复: {stats['duplicate']}")

# 查看统计
db_stats = db.get_stats()
print(f"数据库总数: {db_stats['total']}")
```

## 数据模型

### PolicyDocument（政策文档）

| 字段 | 类型 | 说明 |
|------|------|------|
| policy_id | str | 政策唯一ID |
| title | str | 政策标题 |
| source | str | 数据来源 |
| url | str | 原文链接 |
| tax_type | List[TaxType] | 税种标签 |
| region | Region | 地域标签 |
| document_type | DocumentType | 文档类型 |
| content | str | 正文内容 |
| qa_pairs | List[QAPair] | 问答对列表 |
| publish_date | datetime | 发布日期 |
| document_number | str | 发文字号 |
| publish_department | str | 发布单位 |
| crawled_at | datetime | 爬取时间 |

## 数据源说明

### 国家税务总局

- **网站**: https://fgk.chinatax.gov.cn/
- **栏目**: 最新文件、法律、行政法规、部门规章、财税文件、政策解读
- **数据量**: 约5000-8000条（近3年）

### 12366

- **网站**: https://12366.chinatax.gov.cn
- **栏目**: 热点问题、办税指南
- **数据量**: 约3000-5000条（近3年）

### 北京税务局

- **网站**: http://beijing.chinatax.gov.cn
- **栏目**: 政策解读、个人所得税热点、企业所得税热点
- **数据量**: 约1500条（近3年）

### 上海税务局

- **网站**: https://shanghai.chinatax.gov.cn
- **栏目**: 政策解读、热点问答
- **数据量**: 约1500条（近3年）

### 广东税务局

- **网站**: https://guangdong.chinatax.gov.cn
- **栏目**: 政策解读
- **数据量**: 约1200条（近3年）

## 云端部署

### 阿里云部署步骤

1. **购买阿里云ECS服务器**
   - 推荐配置：2核4G，按量付费
   - 操作系统：Ubuntu 22.04

2. **购买阿里云MongoDB**
   - 版本：4.4或以上
   - 规格：1核2G 100GB（入门版）

3. **配置安全组**
   - 开放SSH端口（22）
   - 开放应用端口（如8000）

4. **部署代码**
   ```bash
   # SSH连接服务器
   ssh root@your-server-ip

   # 安装Python
   apt update
   apt install python3 python3-pip python3-venv

   # 克隆代码
   cd /opt
   git clone your-repo-url

   # 创建虚拟环境
   python3 -m venv venv
   source venv/bin/activate

   # 安装依赖
   pip install -r crawler/requirements.txt

   # 配置环境变量
   vi .env

   # 运行爬虫
   python -m crawler.run --source chinatax
   ```

5. **设置定时任务**
   ```bash
   # 编辑crontab
   crontab -e

   # 每天凌晨2点运行
   0 2 * * * cd /opt/your-project && source venv/bin/activate && python -m crawler.run --source all >> logs/cron.log 2>&1
   ```

## 注意事项

### 反爬虫策略

- 每次请求间隔3-6秒（随机）
- 使用真实浏览器User-Agent
- 遇到403错误自动重试
- 不超过网站设定的频率限制

### 法律合规

- 仅用于学习和研究目的
- 遵守robots.txt协议
- 注明数据来源
- 不用于商业转售

### 数据质量

- 爬取后进行人工抽检
- 定期检查网站结构变化
- 及时更新解析规则

## 故障排查

### 常见问题

1. **403 Forbidden错误**
   - 原因：请求过于频繁
   - 解决：增加延迟时间

2. **数据解析失败**
   - 原因：网站结构变化
   - 解决：检查网站，更新解析规则

3. **MongoDB连接失败**
   - 原因：网络不通或配置错误
   - 解决：检查防火墙和连接配置

## 后续计划

- [ ] 添加更多地方税务局
- [ ] 实现增量更新
- [ ] 添加数据质量检查
- [ ] 实现向量化存储
- [ ] 添加监控和告警

## 联系方式

- 项目文档：`C:\Users\CINDEMAN\Claude项目\共享CFO\共享CFO产品战略.md`

## 许可证

MIT License
