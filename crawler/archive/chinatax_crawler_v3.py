#!/usr/bin/env python3
"""
国家税务总局政策爬虫 - 改进版
使用多种策略绕过反爬虫
"""
import logging
import random
import time
from datetime import datetime
from urllib.parse import urljoin, quote_plus

from pymongo import MongoClient
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


class TaxCrawler:
    # 多个User-Agent轮换
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    ]

    def __init__(self):
        self.base_url = 'https://fgk.chinatax.gov.cn'
        self.mongo_uri = f'mongodb://cfo_user:{quote_plus("840307@whY")}@localhost:27017/shared_cfo?authSource=admin'

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/opt/shared-cfo/logs/crawler.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # 连接MongoDB
        self.logger.info('连接MongoDB...')
        self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=10000)
        self.db = self.client['shared_cfo']
        self.collection = self.db['policies']
        self.client.admin.command('ping')
        self.logger.info('MongoDB连接成功')

        # 配置requests会话
        self._init_session()

    def _init_session(self):
        """初始化requests会话"""
        self.session = requests.Session()

        # 配置重试
        retry = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # 随机User-Agent
        user_agent = random.choice(self.USER_AGENTS)
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigation',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        })

    def _get_random_headers(self):
        """获取随机请求头"""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
        }

    def delay(self, min_sec=3.0, max_sec=8.0):
        """随机延迟"""
        time.sleep(random.uniform(min_sec, max_sec))

    def _fetch_with_retry(self, url, max_retries=3):
        """带重试的请求"""
        for attempt in range(max_retries):
            try:
                # 每次重试使用不同的User-Agent
                headers = self._get_random_headers()

                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=30,
                    allow_redirects=True
                )

                if response.status_code == 403:
                    self.logger.warning(f'403错误，等待后重试 ({attempt+1}/{max_retries})')
                    time.sleep(random.uniform(10, 20))
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                self.logger.warning(f'请求失败，重试中: {e}')
                time.sleep(random.uniform(5, 10))

        return None

    def crawl_main_page(self, limit=20):
        """爬取主页获取政策链接"""
        self.logger.info(f'爬取主页: {self.base_url}')

        try:
            response = self._fetch_with_retry(self.base_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            policies = []

            # 查找所有政策相关链接
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').strip()
                title = link.get_text(strip=True)

                if not href or not title or len(title) < 5:
                    continue

                # 过滤政策链接
                if any(kw in title for kw in ['税', '政策', '公告', '通知', '增值税', '所得税', '所得', '印花税', '企业所得税']):
                    # 只收录站内链接
                    if '/zcfgk/' in href or href.startswith('/zcfgk/'):
                        if not href.startswith('http'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href

                        # 去重
                        if not any(p['url'] == full_url for p in policies):
                            policies.append({
                                'title': title[:100],
                                'url': full_url
                            })

                            if len(policies) >= limit:
                                break

            self.logger.info(f'找到 {len(policies)} 条政策链接')
            return policies

        except Exception as e:
            self.logger.error(f'爬取主页失败: {e}')
            return []

    def crawl_detail(self, url, title=None):
        """爬取政策详情"""
        try:
            self.delay(2, 5)
            response = self._fetch_with_retry(url)

            if not response:
                return 'error'

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取标题
            if not title:
                # 尝试多种方式获取标题
                title_elem = (
                    soup.find('h1') or
                    soup.find('h2') or
                    soup.find('title') or
                    soup.find('div', class_='title')
                )
                title = title_elem.get_text(strip=True) if title_elem else url.split('/')[-1]

            # 提取内容 - 尝试多种容器
            content_div = (
                soup.find('div', class_='content') or
                soup.find('div', class_='article-content') or
                soup.find('div', id='content') or
                soup.find('div', class_='txt') or
                soup.find('article') or
                soup.find('div', class_='text')
            )

            if content_div:
                content = content_div.get_text(separator='\n', strip=True)
            else:
                # 从整个body提取
                body = soup.find('body')
                content = body.get_text(separator='\n', strip=True) if body else ''

            # 清理内容
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            content = '\n'.join(lines)

            # 生成policy_id
            policy_id = url.split('/')[-1].replace('.shtml', '').replace('.htm', '')
            if not policy_id:
                policy_id = f"doc_{int(time.time())}"

            # 构造文档
            doc = {
                'policy_id': policy_id,
                'title': title,
                'source': '国家税务总局',
                'url': url,
                'content': content[:50000],
                'crawled_at': datetime.now(),
                'region': '全国',
                'document_type': self._detect_doc_type(title),
                'tax_type': self._detect_tax_type(title),
            }

            # 保存到数据库
            self.collection.insert_one(doc)
            self.logger.info(f'✓ 保存: {title[:40]}')
            return 'success'

        except Exception as e:
            error_str = str(e).lower()
            if 'duplicate' in error_str or 'e11000' in error_str:
                return 'duplicate'
            self.logger.error(f'✗ 失败 ({url[:50]}...): {e}')
            return 'error'

    def _detect_doc_type(self, title):
        """检测文档类型"""
        if '公告' in title:
            return '公告'
        elif '通知' in title:
            return '通知'
        elif '解读' in title:
            return '解读'
        elif '指引' in title:
            return '指引'
        else:
            return '其他'

    def _detect_tax_type(self, title):
        """检测税种"""
        tax_types = []
        if '增值税' in title:
            tax_types.append('增值税')
        if '所得税' in title or '企业所得税' in title:
            tax_types.append('企业所得税')
        if '个人所得税' in title:
            tax_types.append('个人所得税')
        if '印花税' in title:
            tax_types.append('印花税')
        return tax_types if tax_types else ['其他']

    def crawl(self, limit=20):
        """主爬取方法"""
        self.logger.info('=' * 50)
        self.logger.info('共享CFO税务政策爬虫启动')
        self.logger.info('=' * 50)

        # 先访问主页建立会话
        self.delay(2, 4)

        # 爬取主页获取链接
        policies = self.crawl_main_page(limit * 2)  # 多获取一些，因为可能有些会失败

        if not policies:
            self.logger.warning('未找到政策链接，尝试备用方案...')

            # 备用：使用预定义的一些政策URL
            policies = self._get_fallback_policies()

        # 爬取详情
        success = duplicate = error = 0
        actual_limit = min(len(policies), limit)

        for idx, policy in enumerate(policies[:actual_limit], 1):
            title = policy['title']
            url = policy['url']

            self.logger.info(f'[{idx}/{actual_limit}] {title[:50]}')

            result = self.crawl_detail(url, title)
            if result == 'success':
                success += 1
            elif result == 'duplicate':
                duplicate += 1
            else:
                error += 1

        self.logger.info('=' * 50)
        self.logger.info(f'完成 - 成功:{success}, 重复:{duplicate}, 失败:{error}')
        self.logger.info(f'数据库总数: {self.collection.count_documents({})}')
        self.logger.info('=' * 50)

        return success

    def _get_fallback_policies(self):
        """备用政策列表（手动维护的一些重要政策URL）"""
        return [
            {'title': '关于增值税小规模纳税人减免增值税政策的公告', 'url': 'https://fgk.chinatax.gov.cn/zcfgk/zcfb/202401/t20240118_某某.shtml'},
            # 这里可以添加更多已知的政策URL
        ]

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


if __name__ == '__main__':
    crawler = None
    try:
        crawler = TaxCrawler()
        crawler.crawl(limit=20)
    except KeyboardInterrupt:
        print('\n用户中断')
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if crawler:
            crawler.close()
        print('完成!')
