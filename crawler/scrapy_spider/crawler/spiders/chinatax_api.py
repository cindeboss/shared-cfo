"""
国家税务总局政策法规库爬虫 - API版本
使用 Scrapy + API 调用
"""

import scrapy
import json
import hashlib
from datetime import datetime


class ChinaTaxAPISpider(scrapy.Spider):
    """
    国家税务总局政策法规库爬虫 (API版本)

    使用 API 端点获取数据，无需解析 HTML
    API: https://www.chinatax.gov.cn/getFileListByCodeId
    """

    name = 'chinatax_api'
    allowed_domains = ['chinatax.gov.cn', 'fgk.chinatax.gov.cn']

    # 自定义设置
    custom_settings = {
        'DOWNLOAD_DELAY': 2,  # API调用延迟
        'CONCURRENT_REQUESTS': 3,
        'LOG_LEVEL': 'INFO',
    }

    # API 配置
    API_URL = 'https://www.chinatax.gov.cn/getFileListByCodeId'

    # 分类对应的 codeId 和 channelId
    # 这些值来自网站页面的 JavaScript 变量
    CATEGORY_MAP = {
        '法律': {'codeId': 'c100006', 'channelId': '29a88b67e4b149cfa9fac7919dfb08a5', 'level': 'L1'},
        '行政法规': {'codeId': 'c100007', 'channelId': '', 'level': 'L1'},
        '税务部门规章': {'codeId': 'c100009', 'channelId': '', 'level': 'L2'},
        '财税文件': {'codeId': 'c100010', 'channelId': '', 'level': 'L2'},
        '税务规范性文件': {'codeId': 'c100012', 'channelId': '', 'level': 'L3'},
        '政策解读': {'codeId': 'c100015', 'channelId': '', 'level': 'L4'},
    }

    def __init__(self, category='法律', max_pages=10, *args, **kwargs):
        super(ChinaTaxAPISpider, self).__init__(*args, **kwargs)
        self.category = category
        self.max_pages = int(max_pages)
        self.stats = {'total': 0, 'success': 0, 'error': 0, 'items': 0}

    def start_requests(self):
        """生成 API 请求"""
        config = self.CATEGORY_MAP.get(self.category, self.CATEGORY_MAP['法律'])

        for page in range(1, self.max_pages + 1):
            body = f'codeId={config["codeId"]}&channelId={config["channelId"]}&page={page}&size=20'
            yield scrapy.Request(
                url=self.API_URL,
                method='POST',
                callback=self.parse_api_response,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://fgk.chinatax.gov.cn/',
                    'Origin': 'https://fgk.chinatax.gov.cn',
                },
                body=body,
                meta={'category': self.category, 'level': config['level'], 'page': page},
                dont_filter=True,
            )

    def parse_api_response(self, response):
        """解析 API 响应

        API 响应结构:
        {
            "code": 200,
            "results": {
                "data": {
                    "page": 1,
                    "rows": 20,
                    "total": 4934,
                    "results": [...]
                }
            }
        }
        """
        category = response.meta['category']
        level = response.meta['level']
        page = response.meta['page']

        try:
            self.stats['total'] += 1
            data = json.loads(response.text)

            # 检查响应码
            if data.get('code') != 200:
                self.logger.warning(f"第 {page} 页 ({category}): API 返回码 {data.get('code')}")
                return

            # 正确的嵌套路径: results.data.results
            results_container = data.get('results', {})
            results_data = results_container.get('data', {})
            results_list = results_data.get('results', [])
            total = results_data.get('total', 0)

            if not results_list:
                self.logger.warning(f"第 {page} 页 ({category}): 无数据")
                return

            self.logger.info(f"第 {page} 页 ({category}): {len(results_list)} 条记录，总计 {total} 条")
            self.stats['success'] += 1

            for item_data in results_list:
                yield from self.parse_policy_item(item_data, category, level)

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析错误 (第 {page} 页): {e}")
            self.stats['error'] += 1
        except Exception as e:
            self.logger.error(f"处理错误 (第 {page} 页): {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.stats['error'] += 1

    def parse_policy_item(self, item_data, category, level):
        """解析单条政策记录"""
        try:
            # 提取标题
            title = item_data.get('titleHtml', '') or ''
            if not title:
                title = item_data.get('subTitleHtml', '') or ''

            url = item_data.get('url', '')
            publish_time = item_data.get('publishedTimeStr', '')

            if not title or not url:
                return

            # 生成 policy_id
            policy_id = hashlib.md5(f"{url}{title}".encode('utf-8')).hexdigest()[:16]

            # 提取发文字号
            document_number = ''
            meta_list = item_data.get('domainMetaList', [])
            for meta_item in meta_list:
                result_list = meta_item.get('resultList', [])
                for res in result_list:
                    name = res.get('name', '')
                    value = res.get('value', '')
                    if '字号' in name or '文号' in name or '编号' in name:
                        if value and len(value) > 0:
                            document_number = value
                            break
                if document_number:
                    break

            self.stats['items'] += 1

            # 返回数据项
            yield {
                'policy_id': policy_id,
                'title': title.strip(),
                'url': url,
                'source': 'chinatax',
                'level': level,
                'category': category,
                'document_number': document_number,
                'publish_date': publish_time.split(' ')[0] if publish_time else '',
                'crawled_at': datetime.now().isoformat(),
                'crawler_version': 'scrapy-api-1.0',
            }

            # 可选：爬取详情页获取更多内容
            # if url and url.startswith('http'):
            #     yield response.follow(url, callback=self.parse_detail, meta={'policy_id': policy_id})

        except Exception as e:
            self.logger.error(f"解析政策项错误: {e}")

    def parse_detail(self, response):
        """解析详情页（可选）"""
        policy_id = response.meta.get('policy_id')

        # 提取正文内容
        content_selectors = [
            '.content', '.article-content', '.detail-content',
            '.policy-content', '.main-content', '#content',
            '.text', 'article', '.detail'
        ]

        content = ''
        for selector in content_selectors:
            texts = response.css(f'{selector} ::text').getall()
            if texts:
                content = ''.join(texts).strip()
                if len(content) > 100:  # 确保有实际内容
                    break

        if content:
            yield {
                'policy_id': policy_id,
                'content': content,
            }

    def closed(self, reason):
        """爬虫关闭时打印统计"""
        self.logger.info("=" * 50)
        self.logger.info("爬虫统计:")
        self.logger.info(f"  总请求数: {self.stats['total']}")
        self.logger.info(f"  成功: {self.stats['success']}")
        self.logger.info(f"  错误: {self.stats['error']}")
        self.logger.info(f"  提取项目: {self.stats['items']}")
        self.logger.info(f"  关闭原因: {reason}")
        self.logger.info("=" * 50)
