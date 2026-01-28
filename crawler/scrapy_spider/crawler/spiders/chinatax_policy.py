"""
国家税务总局政策法规库爬虫
使用 Scrapy 框架
"""

import scrapy
from datetime import datetime
from crawler.items import TaxPolicyItem, TaxPolicyItemLoader


class ChinaTaxPolicySpider(scrapy.Spider):
    """
    国家税务总局政策法规库爬虫

    目标网站: https://fgk.chinatax.gov.cn/

    支持爬取:
    - 法律 (L1)
    - 行政法规 (L1)
    - 税务部门规章 (L2)
    - 财税文件 (L2)
    - 税务规范性文件 (L3)
    - 政策解读 (L4)
    """

    name = 'chinatax_policy'
    allowed_domains = ['fgk.chinatax.gov.cn', 'chinatax.gov.cn']

    # 自定义设置
    custom_settings = {
        'DOWNLOAD_DELAY': 3,  # 3秒延迟（政府网站要求）
        'CONCURRENT_REQUESTS': 3,  # 限制并发
        'CLOSESPIDER_PAGECOUNT': 500,  # 测试阶段限制500页
        'LOG_LEVEL': 'INFO',
    }

    def __init__(self, category='all', start_year=2022, end_year=2026, *args, **kwargs):
        """
        初始化爬虫

        Args:
            category: 分类 (all, 法律, 行政法规, 部门规章, 财税文件, 规范性文件, 解读)
            start_year: 起始年份
            end_year: 结束年份
        """
        super(ChinaTaxPolicySpider, self).__init__(*args, **kwargs)

        self.category = category
        self.start_year = int(start_year)
        self.end_year = int(end_year)

        # 基础 URL
        self.base_url = 'https://fgk.chinatax.gov.cn'

        # 分类映射
        self.category_map = {
            '法律': {'level': 'L1', 'code': 'fl'},
            '行政法规': {'level': 'L1', 'code': 'xzfg'},
            '税务部门规章': {'level': 'L2', 'code': 'swbzgz'},
            '财税文件': {'level': 'L2', 'code': 'ccwj'},
            '税务规范性文件': {'level': 'L3', 'code': 'swgfwj'},
            '政策解读': {'level': 'L4', 'code': 'zcjd'},
        }

        self.logger.info(f"爬虫初始化: category={category}, years={start_year}-{end_year}")

    def start_requests(self):
        """生成起始请求"""
        # 从首页开始
        yield scrapy.Request(
            url=self.base_url + '/zcfgk/index.html',
            callback=self.parse_home,
            meta={'category': '首页'}
        )

    def parse_home(self, response):
        """解析首页，提取分类链接"""
        self.logger.info(f"解析首页: {response.url}")

        # 提取政策导航中的分类
        nav_links = response.css('.policy-nav a::attr(href)').getall()
        nav_titles = response.css('.policy-nav a::text').getall()

        for title, link in zip(nav_titles, nav_links):
            # 根据设置过滤分类
            if self.category != 'all' and self.category not in title:
                continue

            if title in self.category_map:
                full_url = response.urljoin(link)
                self.logger.info(f"发现分类: {title} -> {full_url}")

                yield response.follow(
                    full_url,
                    callback=self.parse_category,
                    meta={
                        'category': title,
                        'level': self.category_map[title]['level']
                    }
                )

    def parse_category(self, response):
        """
        解析分类页面

        这个方法需要根据实际的网站结构来实现
        """
        category = response.meta['category']
        level = response.meta['level']

        self.logger.info(f"解析分类页面: {category} ({level})")

        # 提取政策列表
        # 注意：这里的 CSS 选择器需要根据实际网站结构调整

        # 示例：提取政策列表项
        policy_items = response.css('.policy-item, .law-item, .file-item')

        for item in policy_items:
            loader = TaxPolicyItemLoader(item=TaxPolicyItem(), response=response)

            # 提取标题和链接
            title = item.css('.title a::text, a::text').get()
            url = item.css('.title a::attr(href), a::attr(href)').get()

            if not title or not url:
                continue

            loader.add_value('title', title)
            loader.add_value('url', response.urljoin(url))
            loader.add_value('source', 'chinatax')
            loader.add_value('level', level)
            loader.add_value('category', category)

            # 提取发布日期
            date_str = item.css('.date::text, .publish-date::text, time::text').get()
            if date_str:
                loader.add_value('publish_date', date_str.strip())

            # 提取文号
            doc_number = item.css('.doc-number::text, .wh::text').get()
            if doc_number:
                loader.add_value('document_number', doc_number.strip())

            # 提取发布单位
            dept = item.css('.dept::text, .publish-dept::text').get()
            if dept:
                loader.add_value('publish_department', dept.strip())

            # 生成 policy_id
            loader.add_value('policy_id', self._generate_policy_id(
                response.urljoin(url), title
            ))

            # 添加到待爬取队列
            detail_url = response.urljoin(url)
            yield response.follow(
                detail_url,
                callback=self.parse_detail,
                meta={'item': loader.load_item()}
            )

        # 处理分页
        next_page = response.css('.next-page a::attr(href), .page-next::attr(href)').get()
        if next_page:
            self.logger.info(f"发现下一页: {next_page}")
            yield response.follow(
                next_page,
                callback=self.parse_category,
                meta=response.meta
            )

    def parse_detail(self, response):
        """解析详情页面"""
        item = response.meta['item']

        self.logger.info(f"解析详情: {item.get('title', 'N/A')}")

        # 提取正文内容
        content_selectors = [
            '.content', '.article-content', '.detail-content',
            '.policy-content', '.main-content', '#content'
        ]

        content = ''
        for selector in content_selectors:
            content = response.css(f'{selector} ::text').getall()
            if content:
                content = ''.join(content).strip()
                break

        if content:
            item['content'] = content

        # 提取摘要（如果有）
        summary = response.css('.summary::text, .abstract::text').get()
        if summary:
            item['summary'] = summary.strip()

        # 提取关键词
        keywords = response.css('.keywords a::text, .tags a::text').getall()
        if keywords:
            item['keywords'] = [k.strip() for k in keywords if k.strip()]

        # 提取生效日期和失效日期
        effective_date = response.css('.effective-date::text, .sxrq::text').get()
        if effective_date:
            item['effective_date'] = effective_date.strip()

        expiry_date = response.css('.expiry-date::text, .sxrq::text').get()
        if expiry_date:
            item['expiry_date'] = expiry_date.strip()

        # 如果是解读类文件，提取问答对
        if item.get('level') == 'L4' or '解读' in item.get('category', ''):
            qa_pairs = self._extract_qa_pairs(response)
            if qa_pairs:
                item['qa_pairs'] = qa_pairs

        # 添加爬取时间
        item['crawled_at'] = datetime.now().isoformat()

        yield item

    def _extract_qa_pairs(self, response):
        """提取问答对（用于政策解读）"""
        qa_pairs = []

        # 查找问答元素
        qa_items = response.css('.qa-item, .question-answer, .faq-item')

        for qa in qa_items:
            question = qa.css('.question::text, .q::text').get()
            answer = qa.css('.answer::text, .a::text').get()

            if question and answer:
                qa_pairs.append({
                    'question': question.strip(),
                    'answer': answer.strip()
                })

        return qa_pairs

    def _generate_policy_id(self, url, title):
        """生成 policy_id"""
        import hashlib
        source_str = f"{url}{title}{datetime.now().date()}"
        return hashlib.md5(source_str.encode('utf-8')).hexdigest()[:16]
