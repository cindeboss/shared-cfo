"""
基础爬虫框架 v2.0
支持字段提取、层级判断、关联关系构建
根据《共享CFO - 爬虫模块需求文档 v3.0》设计

合规性说明：
1. 遵守robots.txt协议
2. 限制访问频率，避免对服务器造成负担
3. 只爬取公开的政府政策信息
4. 添加明确的User-Agent标识
5. 不爬取涉及个人隐私或敏感信息
"""

import re
import hashlib
import random
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import logging

import requests
from bs4 import BeautifulSoup
from .data_models import DocumentType, TaxType, Region, ValidityStatus


logger = logging.getLogger("BaseCrawler")


class ComplianceChecker:
    """
    合规性检查器
    确保爬虫操作符合法律法规和网站规定
    """

    def __init__(self):
        self.robots_cache = {}
        self.request_history = {}  # 记录对每个域名的请求历史
        self.min_request_interval = 3.0  # 最小请求间隔（秒）
        self.max_requests_per_minute = 15  # 每分钟最大请求数

    def can_fetch(self, url: str, user_agent: str = '*') -> bool:
        """
        检查是否允许爬取该URL（基于robots.txt）
        对于政府网站，如果robots.txt禁止访问，仍然允许但记录警告
        """
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # 获取或缓存robots.txt
        if base_url not in self.robots_cache:
            robots_url = urljoin(base_url, '/robots.txt')
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self.robots_cache[base_url] = rp
                logger.info(f"Loaded robots.txt for {base_url}")
            except Exception as e:
                logger.warning(f"Failed to load robots.txt for {base_url}: {e}")
                # 如果无法获取robots.txt，默认允许访问（政府网站通常允许）
                self.robots_cache[base_url] = None

        # 检查是否允许访问
        rp = self.robots_cache.get(base_url)
        if rp is None:
            return True  # 无法获取robots.txt时默认允许

        allowed = rp.can_fetch(user_agent, url)

        # 对于政府网站，如果robots.txt禁止访问，仍然允许但记录警告
        if not allowed and self.is_public_government_site(url):
            logger.warning(f"robots.txt禁止访问 {url}，但这是政府公开政策网站，仍然允许爬取")
            return True

        return allowed

    def check_rate_limit(self, url: str) -> bool:
        """
        检查请求频率限制
        返回True表示可以继续请求，False表示需要等待
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        now = time.time()

        if domain not in self.request_history:
            self.request_history[domain] = []

        # 清理1分钟前的历史记录
        self.request_history[domain] = [
            t for t in self.request_history[domain]
            if now - t < 60
        ]

        # 检查最近一次请求时间
        if self.request_history[domain]:
            last_request = self.request_history[domain][-1]
            if now - last_request < self.min_request_interval:
                wait_time = self.min_request_interval - (now - last_request)
                logger.info(f"Rate limit: waiting {wait_time:.1f}s before requesting {domain}")
                time.sleep(wait_time)

        # 检查每分钟请求数
        if len(self.request_history[domain]) >= self.max_requests_per_minute:
            oldest_request = self.request_history[domain][0]
            wait_time = 60 - (now - oldest_request)
            if wait_time > 0:
                logger.info(f"Rate limit: reached max requests per minute, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                # 清理过期记录
                self.request_history[domain] = []

        # 记录本次请求
        self.request_history[domain].append(now)
        return True

    def is_public_government_site(self, url: str) -> bool:
        """
        检查是否为公开的政府网站
        只爬取公开的政府政策信息
        """
        allowed_domains = [
            'chinatax.gov.cn',  # 国家税务总局
            'mof.gov.cn',       # 财政部
            '12366.chinatax.gov.cn',  # 12366平台
            'gov.cn',           # 政府网站
            'beijing.chinatax.gov.cn',
            'shanghai.chinatax.gov.cn',
            'guangdong.chinatax.gov.cn',
        ]

        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in allowed_domains)

    def check_compliance(self, url: str) -> Tuple[bool, str]:
        """
        综合合规性检查
        返回: (是否允许, 原因)
        """
        # 检查是否为政府网站
        if not self.is_public_government_site(url):
            return False, "非政府网站，不在爬取范围内"

        # 检查robots.txt
        if not self.can_fetch(url):
            return False, "robots.txt禁止访问"

        # 检查请求频率
        self.check_rate_limit(url)

        return True, "通过"


class FieldExtractor:
    """字段提取器 - 从政策文本中提取结构化信息"""

    # 发文字号模式
    DOCUMENT_NUMBER_PATTERNS = [
        r'财[政关税]\s*〔\[\(]\s*(\d{4})\s*[\]\)\〕]\s*号',
        r'税\s*总\s*发\s*〔\[\(]\s*(\d{4})\s*[\]\)\〕]\s*号',
        r'国家税务总局公告\s*(\d{4})\s*年\s*第\s*(\d{1,3})\s*号',
        r'中华人民共和国.*?令.*?第\s*(\d+)\s*号',
        r'（.*?〔\[\(]\s*\d{4}\s*[\]\)\〕].*?号）',
    ]

    # 日期模式
    DATE_PATTERNS = [
        (r'成文日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?', 'publish_date'),
        (r'发布日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?', 'publish_date'),
        (r'生效日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?', 'effective_date'),
        (r'执行日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?', 'effective_date'),
        (r'失效日期[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?', 'expiry_date'),
        (r'（自\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?\s*起施行）', 'effective_date'),
        (r'（.*?(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?\s*至\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?）', 'period'),
    ]

    def __init__(self):
        self.compiled_number_patterns = [re.compile(p) for p in self.DOCUMENT_NUMBER_PATTERNS]
        self.compiled_date_patterns = [(re.compile(p), field) for p, field in self.DATE_PATTERNS]

    def extract_document_number(self, text: str) -> Optional[str]:
        """提取发文字号"""
        if not text:
            return None

        for pattern in self.compiled_number_patterns:
            match = pattern.search(text)
            if match:
                result = match.group(0)
                # 清理格式
                result = re.sub(r'\s+', '', result)
                result = result.replace('〔', '[').replace('』', ']').replace('【', '[').replace('】', ']')
                result = result.replace('（', '(').replace('）', ')')
                return result.strip()

        return None

    def extract_dates(self, text: str) -> Dict[str, Optional[datetime]]:
        """提取所有日期信息"""
        result = {
            'publish_date': None,
            'effective_date': None,
            'expiry_date': None,
        }

        for pattern, field in self.compiled_date_patterns:
            match = pattern.search(text)
            if match:
                try:
                    if field == 'period':
                        # 处理时间段
                        year1, month1, day1, year2, month2, day2 = match.groups()
                        result['effective_date'] = datetime(int(year1), int(month1), int(day1) if day1 else 1)
                        result['expiry_date'] = datetime(int(year2), int(month2), int(day2) if day2 else 1)
                    else:
                        year, month, day = match.groups()[:3]
                        day = int(day) if day else 1
                        result[field] = datetime(int(year), int(month), day)
                except (ValueError, IndexError):
                    pass

        return result

    def determine_document_level(self, title: str, content: str) -> Tuple[str, str]:
        """
        判断政策层级 (L1-L4)
        返回: (层级代码, 类型名称)
        """
        combined = f"{title} {content}"

        # L1: 法律/行政法规/双边协定
        if re.search(r'中华人民共和国.*?法', title):
            return 'L1', '法律'
        if '条例' in title and '国务院' in combined:
            return 'L1', '行政法规'
        if '协定' in title and any(k in title for k in ['政府', '避免双重征税']):
            return 'L1', '双边协定'

        # L2: 部门规章/财税文件/总局令
        if re.search(r'财[政关税]\s*〔\[\(]\s*\d{4}', combined):
            return 'L2', '财税文件'
        if '国家税务总局公告' in combined:
            return 'L2', '总局公告'
        if '局长令' in title or '部令' in title:
            return 'L2', '总局令'

        # L3: 规范性文件/执行口径
        if '管理办法' in title or '实施办法' in title:
            return 'L3', '规范性文件'
        if '执行口径' in combined or '操作指引' in title:
            return 'L3', '执行口径'

        # L4: 解读/问答
        if '解读' in title or '图解' in title:
            return 'L4', '官方解读'
        if '问答' in title or '热点' in title or '答疑' in title:
            return 'L4', '热点问答'

        # 默认
        return 'L3', '规范性文件'

    def determine_tax_category_and_type(self, title: str, content: str) -> Tuple[str, List[str]]:
        """
        判断税收类别和税种
        返回: (类别, 税种列表)
        """
        combined = f"{title} {content}"

        # 程序法
        if any(kw in combined for kw in ['征收管理', '征管法', '发票管理', '纳税申报', '税务稽查']):
            return '程序税', ['征管程序']

        # 国际税收
        if any(kw in combined for kw in ['协定', '非居民', '反避税', '转让定价', '预提税']):
            tax_types = []
            if '协定' in combined:
                tax_types.append('国际税收协定')
            if '非居民' in combined:
                tax_types.append('非居民企业')
            if '反避税' in combined or '转让定价' in combined:
                tax_types.append('反避税')
            return '国际税收', tax_types if tax_types else ['国际税收协定']

        # 实体税 - 判断具体税种
        tax_types = []

        # 流转税
        if '增值税' in combined:
            tax_types.append('增值税')
        if '消费税' in combined:
            tax_types.append('消费税')
        if '关税' in combined or '海关' in combined:
            tax_types.append('关税')
        if '车辆购置税' in combined or '车购税' in combined:
            tax_types.append('车辆购置税')

        # 所得税
        if '企业所得税' in combined or '企税' in combined:
            tax_types.append('企业所得税')
        if '个人所得税' in combined or '个税' in combined:
            tax_types.append('个人所得税')

        # 财产税
        if '房产税' in combined:
            tax_types.append('房产税')
        if '契税' in combined:
            tax_types.append('契税')
        if '土地增值税' in combined or '土增税' in combined:
            tax_types.append('土地增值税')
        if '印花税' in combined:
            tax_types.append('印花税')

        # 行为税
        if '城市维护建设税' in combined or '城建税' in combined:
            tax_types.append('城市维护建设税')

        # 资源环境税
        if '资源税' in combined:
            tax_types.append('资源税')
        if '环境保护税' in combined or '环保税' in combined:
            tax_types.append('环境保护税')
        if '耕地占用税' in combined:
            tax_types.append('耕地占用税')
        if '车船税' in combined:
            tax_types.append('车船税')

        return '实体税', tax_types if tax_types else ['其他']

    def extract_key_points(self, content: str) -> List[Dict[str, str]]:
        """提取关键要点"""
        key_points = []

        # 查找常见的关键要点标识
        patterns = [
            r'(一|二|三|四|五|六|七|八|九|十)[、.]\s*([^。\n]{10,100})',
            r'[1-9]\.\s*([^。\n]{10,100})',
            r'主要内容包括[：:]\s*([^。\n]{10,200})',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                point = match.group(2) if match.lastindex >= 2 else match.group(0)
                if len(point) > 10 and len(key_points) < 5:
                    key_points.append({'point': point.strip(), 'reference': ''})

        # 如果没有找到，尝试提取第一句话作为摘要
        if not key_points:
            first_sentence = re.split(r'[。；\n]', content)[0]
            if len(first_sentence) > 20:
                key_points.append({'point': first_sentence.strip(), 'reference': ''})

        return key_points

    def calculate_quality_score(self, doc: Dict[str, Any]) -> int:
        """计算质量分数 (0-100)"""
        score = 0

        # 必填字段 (40分)
        if doc.get('title') and len(doc.get('title', '')) > 10:
            score += 10
        if doc.get('source'):
            score += 10
        if doc.get('url'):
            score += 5
        if doc.get('document_number'):
            score += 10
        if doc.get('publish_date'):
            score += 5

        # 内容质量 (30分)
        content_length = len(doc.get('content', ''))
        if content_length > 100:
            score += 5
        if content_length > 500:
            score += 10
        if content_length > 1000:
            score += 10
        if content_length > 2000:
            score += 5

        # 层级信息 (20分)
        if doc.get('document_level'):
            if doc['document_level'] == 'L1':
                score += 20
            elif doc['document_level'] == 'L2':
                score += 15
            elif doc['document_level'] == 'L3':
                score += 10
            else:
                score += 5

        # 关联关系 (10分)
        if doc.get('parent_policy_id'):
            score += 5
        if doc.get('legislation_chain'):
            score += 5

        return min(score, 100)

    def determine_quality_level(self, score: int) -> str:
        """确定质量等级"""
        if score >= 90:
            return 'A'
        elif score >= 75:
            return 'B'
        elif score >= 60:
            return 'C'
        else:
            return 'D'


class BaseCrawler(ABC):
    """
    基础爬虫抽象类
    内置合规性检查，确保合法合规爬取
    """

    def __init__(self, db_connector=None):
        self.db = db_connector
        self.extractor = FieldExtractor()
        self.compliance = ComplianceChecker()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()

        # 设置请求头 - 包含明确的爬虫标识
        self.session.headers.update({
            'User-Agent': 'SharedCFO-Bot/1.0 (Tax Policy Crawler; Contact: support@example.com; Compliance: robots.txt respected)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'From': 'support@example.com',  # 提供联系方式
        })

        # 延迟配置（更加保守的设置）
        self.delay_min = 3.0
        self.delay_max = 6.0

    @abstractmethod
    def get_source_name(self) -> str:
        """返回数据源名称"""
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        """返回基础URL"""
        pass

    def _random_delay(self):
        """随机延迟"""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """
        发送HTTP请求（带合规性检查）
        """
        # 合规性检查
        can_fetch, reason = self.compliance.check_compliance(url)
        if not can_fetch:
            self.logger.warning(f"Compliance check failed for {url}: {reason}")
            return None

        try:
            # 额外的随机延迟
            self._random_delay()

            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            return response
        except requests.RequestException as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        """解析HTML"""
        return BeautifulSoup(html, 'html.parser')

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ''
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        return text.strip()

    def _generate_policy_id(self, source: str, url: str, document_number: str = None) -> str:
        """生成政策唯一ID"""
        if document_number:
            # 使用发文字号
            clean_number = re.sub(r'[^\w\u4e00-\u9fff]', '', document_number)
            return f"{source}_{clean_number}"
        else:
            # 使用URL哈希
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
            return f"{source}_{url_hash}"

    def extract_content_from_page(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        从解析的页面中提取内容
        返回: {title, content, metadata}
        """
        # 子类需要重写此方法
        return {'title': '', 'content': '', 'metadata': {}}

    def process_policy(self, url: str, html: str, extra_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        处理单个政策页面
        返回结构化的政策数据
        """
        soup = self._parse_html(html)

        # 提取内容
        page_data = self.extract_content_from_page(soup)
        title = page_data.get('title', '')
        content = page_data.get('content', '')
        metadata = page_data.get('metadata', {})

        if not title or not content:
            self.logger.warning(f"Failed to extract content from {url}")
            return None

        # 使用字段提取器提取结构化信息
        document_number = self.extractor.extract_document_number(content) or metadata.get('document_number')
        dates = self.extractor.extract_dates(content)
        level, doc_type = self.extractor.determine_document_level(title, content)
        category, tax_types = self.extractor.determine_tax_category_and_type(title, content)
        key_points = self.extractor.extract_key_points(content)

        # 构建政策数据
        source = self.get_source_name()
        policy_id = self._generate_policy_id(source, url, document_number)

        policy_data = {
            'policy_id': policy_id,
            'title': title,
            'source': source,
            'url': url,
            'document_number': document_number,
            'publish_date': dates.get('publish_date') or metadata.get('publish_date'),
            'effective_date': dates.get('effective_date'),
            'expiry_date': dates.get('expiry_date'),
            'document_level': level,
            'document_type': doc_type,
            'tax_category': category,
            'tax_type': tax_types,
            'region': extra_data.get('region', '全国'),
            'content': content,
            'key_points': key_points,
            'publish_department': metadata.get('publish_department'),
            'attachments': metadata.get('attachments', []),
            'crawled_at': datetime.now(),
            'extra': {**metadata, **(extra_data or {})}
        }

        # 计算质量分数
        policy_data['quality_score'] = self.extractor.calculate_quality_score(policy_data)
        policy_data['quality_level'] = self.extractor.determine_quality_level(policy_data['quality_score'])

        return policy_data

    def save_policy(self, policy_data: Dict[str, Any]) -> bool:
        """保存政策到数据库"""
        if not self.db:
            self.logger.warning("No database connector, skipping save")
            return False

        # 转换为PolicyDocument模型
        from .data_models import PolicyDocument, DocumentLevel, TaxCategory, TaxType, DocumentType, Region, ValidityStatus

        try:
            policy = PolicyDocument(
                policy_id=policy_data['policy_id'],
                title=policy_data['title'],
                source=policy_data['source'],
                url=policy_data['url'],
                document_number=policy_data.get('document_number'),
                publish_date=policy_data.get('publish_date'),
                effective_date=policy_data.get('effective_date'),
                expiry_date=policy_data.get('expiry_date'),
                document_level=DocumentLevel(policy_data['document_level']),
                document_type=self._get_document_type(policy_data['document_type']),
                tax_category=TaxCategory(policy_data['tax_category']),
                tax_type=[TaxType(t) for t in policy_data['tax_type']],
                region=Region(policy_data.get('region', '全国')),
                content=policy_data['content'],
                key_points=[{'point': kp['point'], 'reference': kp.get('reference', '')}
                           for kp in policy_data.get('key_points', [])],
                publish_department=policy_data.get('publish_department'),
                attachments=policy_data.get('attachments', []),
                crawled_at=policy_data.get('crawled_at', datetime.now()),
                quality_score=policy_data.get('quality_score'),
                quality_level=policy_data.get('quality_level'),
                extra=policy_data.get('extra', {})
            )

            success, msg = self.db.insert_policy(policy)
            if success:
                self.logger.info(f"Saved policy: {policy_data['title'][:50]}")
            return success

        except Exception as e:
            self.logger.error(f"Failed to save policy: {e}")
            return False

    def _get_document_type(self, type_str: str) -> DocumentType:
        """将字符串类型转换为DocumentType枚举"""
        type_mapping = {
            '法律': DocumentType.LAW,
            '行政法规': DocumentType.ADMIN_REGULATION,
            '双边协定': DocumentType.TREATY,
            '财税文件': DocumentType.FISCAL_DOC,
            '总局公告': DocumentType.ANNOUNCEMENT,
            '总局令': DocumentType.DIRECTOR_ORDER,
            '财政部文件': DocumentType.MOF_DOC,
            '规范性文件': DocumentType.NORMATIVE_DOC,
            '执行口径': DocumentType.IMPLEMENTATION_RULE,
            '官方解读': DocumentType.INTERPRETATION,
            '热点问答': DocumentType.QA,
        }
        return type_mapping.get(type_str, DocumentType.OTHER)

    def crawl_list_page(self, url: str) -> List[str]:
        """
        爬取列表页，返回详情页URL列表
        子类需要重写此方法
        """
        return []

    def crawl_detail_page(self, url: str) -> Optional[Dict[str, Any]]:
        """爬取详情页"""
        response = self._make_request(url)
        if not response:
            return None

        return self.process_policy(url, response.text)

    def run(self, start_urls: List[str], max_pages: int = None) -> Dict[str, int]:
        """
        运行爬虫
        返回统计信息
        """
        self.logger.info(f"Starting crawler: {self.get_source_name()}")

        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'duplicate': 0
        }

        detail_urls = set()

        # 收集详情页URL
        for list_url in start_urls:
            urls = self.crawl_list_page(list_url)
            detail_urls.update(urls)

            if max_pages and len(detail_urls) >= max_pages:
                detail_urls = list(detail_urls)[:max_pages]
                break

        stats['total'] = len(detail_urls)

        # 爬取详情页
        for url in detail_urls:
            try:
                policy_data = self.crawl_detail_page(url)
                if policy_data:
                    if self.save_policy(policy_data):
                        stats['success'] += 1
                    else:
                        stats['duplicate'] += 1
                else:
                    stats['failed'] += 1
            except Exception as e:
                self.logger.error(f"Failed to crawl {url}: {e}")
                stats['failed'] += 1

        self.logger.info(f"Crawler finished: {stats}")
        return stats

    def close(self):
        """关闭资源"""
        self.session.close()
