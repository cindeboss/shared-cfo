#!/usr/bin/env python3
"""
12366纳税服务平台爬虫
更容易爬取，数据质量高
"""
import logging
import random
import time
from datetime import datetime
from urllib.parse import urljoin, quote_plus

from pymongo import MongoClient
import requests
from bs4 import BeautifulSoup


class TaxCrawler12366:
    """12366纳税服务平台爬虫"""

    BASE_URL = "https://12366.chinatax.gov.cn"

    def __init__(self):
        self.mongo_uri = f'mongodb://cfo_user:{quote_plus("840307@whY")}@localhost:27017/shared_cfo?authSource=admin'

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/opt/shared-cfo/logs/crawler_12366.log', encoding='utf-8'),
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

        # 配置session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

    def delay(self, min_sec=2, max_sec=5):
        """随机延迟"""
        time.sleep(random.uniform(min_sec, max_sec))

    def crawl_hot_questions(self, limit=30):
        """爬取热点问题"""
        self.logger.info('爬取12366热点问题...')

        # 尝试多个可能的热点问题URL
        hot_urls = [
            f'{self.BASE_URL}/portal/search/kwd?keyword=增值税',
            f'{self.BASE_URL}/',
        ]

        all_policies = []

        for url in hot_urls:
            self.logger.info(f'访问: {url}')
            self.delay()

            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找问题链接
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '').strip()
                    title = link.get_text(strip=True)

                    if not href or not title or len(title) < 10:
                        continue

                    # 过滤问答相关链接
                    if any(kw in title for kw in ['增值税', '所得税', '个税', '企业', '税收', '税率', '减免']):
                        if not href.startswith('http'):
                            full_url = urljoin(self.BASE_URL, href)
                        else:
                            full_url = href

                        # 去重
                        if not any(p['url'] == full_url for p in all_policies):
                            all_policies.append({
                                'title': title[:150],
                                'url': full_url
                            })

                            if len(all_policies) >= limit:
                                break

                if len(all_policies) >= limit:
                    break

            except Exception as e:
                self.logger.warning(f'访问 {url} 失败: {e}')

        self.logger.info(f'找到 {len(all_policies)} 条问答')

        # 爬取详情
        success = duplicate = error = 0
        for idx, policy in enumerate(all_policies[:limit], 1):
            self.logger.info(f'[{idx}/{min(limit, len(all_policies))}] {policy["title"][:60]}')
            result = self.crawl_detail(policy['url'], policy['title'])
            if result == 'success':
                success += 1
            elif result == 'duplicate':
                duplicate += 1
            else:
                error += 1

        self.logger.info(f'完成 - 成功:{success}, 重复:{duplicate}, 失败:{error}')
        return success

    def crawl_detail(self, url, title=None):
        """爬取详情页"""
        try:
            self.delay()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取标题
            if not title:
                title_elem = soup.find('h1') or soup.find('h2') or soup.find('title')
                title = title_elem.get_text(strip=True) if title_elem else url.split('/')[-1]

            # 提取内容
            content_div = (
                soup.find('div', class_='content') or
                soup.find('div', class_='answer') or
                soup.find('div', class_='detail') or
                soup.find('div', id='content') or
                soup.find('article')
            )

            if content_div:
                content = content_div.get_text(separator='\n', strip=True)
            else:
                body = soup.find('body')
                content = body.get_text(separator='\n', strip=True) if body else ''

            # 清理内容
            lines = [line.strip() for line in content.split('\n') if line.strip() and len(line) > 3]
            content = '\n'.join(lines)

            # 生成ID
            policy_id = url.split('/')[-1].replace('.shtml', '').replace('.htm', '').replace('?', '')
            if not policy_id:
                policy_id = f"12366_{int(time.time())}"

            # 检测税种
            tax_types = []
            if '增值税' in title or '增值税' in content:
                tax_types.append('增值税')
            if '所得税' in title or '企业所得税' in title:
                tax_types.append('企业所得税')
            if '个人所得税' in title or '个税' in title:
                tax_types.append('个人所得税')

            # 构造文档
            doc = {
                'policy_id': policy_id,
                'title': title,
                'source': '12366纳税服务平台',
                'url': url,
                'content': content[:50000],
                'crawled_at': datetime.now(),
                'region': '全国',
                'document_type': '问答',
                'tax_type': tax_types if tax_types else ['其他'],
                'qa_pairs': [{'question': title, 'answer': content[:1000]}]
            }

            self.collection.insert_one(doc)
            self.logger.info(f'✓ 保存成功')
            return 'success'

        except Exception as e:
            if 'duplicate' in str(e).lower() or 'E11000' in str(e):
                return 'duplicate'
            self.logger.error(f'✗ 失败: {e}')
            return 'error'

    def crawl_local_tax_bureaus(self, limit=20):
        """爬取地方税务局"""
        # 北京税务局热点问题
        beijing_urls = [
            'http://beijing.chinatax.gov.cn/',
            'http://beijing.chinatax.gov.cn/bjswj/sszc/zcjd/',
        ]

        all_policies = []

        for url in beijing_urls:
            self.logger.info(f'访问北京税务: {url}')
            self.delay()

            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    title = link.get_text(strip=True)

                    if not href or not title or len(title) < 8:
                        continue

                    if any(kw in title for kw in ['税', '政策', '公告', '通知', '解读']):
                        if not href.startswith('http'):
                            full_url = urljoin(url, href)
                        else:
                            full_url = href

                        if not any(p['url'] == full_url for p in all_policies):
                            all_policies.append({
                                'title': title[:100],
                                'url': full_url,
                                'region': '北京'
                            })

                            if len(all_policies) >= limit:
                                break

                if len(all_policies) >= limit:
                    break

            except Exception as e:
                self.logger.warning(f'访问北京税务失败: {e}')

        self.logger.info(f'找到 {len(all_policies)} 条地方政策')

        # 爬取详情
        success = 0
        for idx, policy in enumerate(all_policies[:limit], 1):
            self.logger.info(f'[{idx}/{min(limit, len(all_policies))}] {policy["title"][:50]}')
            result = self.crawl_detail_local(policy['url'], policy['title'], policy.get('region', '全国'))
            if result == 'success':
                success += 1

        return success

    def crawl_detail_local(self, url, title=None, region='全国'):
        """爬取地方政策详情"""
        try:
            self.delay()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            if not title:
                title_elem = soup.find('h1') or soup.find('title')
                title = title_elem.get_text(strip=True) if title_elem else url.split('/')[-1]

            content_div = soup.find('div', class_='content') or soup.find('div', class_='article-content') or soup.find('body')
            content = content_div.get_text(separator='\n', strip=True) if content_div else ''

            policy_id = url.split('/')[-1].replace('.shtml', '').replace('.htm', '')

            doc = {
                'policy_id': policy_id,
                'title': title,
                'source': f'{region}税务局',
                'url': url,
                'content': content[:50000],
                'crawled_at': datetime.now(),
                'region': region,
                'document_type': '政策',
                'tax_type': ['其他'],
            }

            self.collection.insert_one(doc)
            self.logger.info(f'✓ 保存成功')
            return 'success'

        except Exception as e:
            if 'duplicate' in str(e).lower():
                return 'duplicate'
            return 'error'

    def crawl(self, limit=30):
        """主爬取方法"""
        self.logger.info('=' * 50)
        self.logger.info('12366纳税服务平台爬虫启动')
        self.logger.info('=' * 50)

        # 爬取12366
        count1 = self.crawl_hot_questions(limit)

        # 爬取地方税务局
        count2 = self.crawl_local_tax_bureaus(limit)

        total = count1 + count2
        self.logger.info(f'数据库总数: {self.collection.count_documents({})}')
        self.logger.info(f'本次爬取: {total} 条')
        self.logger.info('=' * 50)

        return total

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()


if __name__ == '__main__':
    crawler = None
    try:
        crawler = TaxCrawler12366()
        crawler.crawl(limit=30)
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
