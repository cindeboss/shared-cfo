"""
爬虫主入口
"""

import logging
import sys
from datetime import datetime
from typing import List, Dict, Any

from .config import SOURCES, crawler_config
from .chinatax_crawler import ChinaTaxCrawler
from .local_tax_crawler import BeijingTaxCrawler, ShanghaiTaxCrawler, GuangdongTaxCrawler
from .database import MongoDBConnector
from .data_models import CrawlTask


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, crawler_config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(crawler_config.log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def run_crawler(source_name: str, channels: List[str] = None, **kwargs):
    """运行指定数据源的爬虫

    Args:
        source_name: 数据源名称 (chinatax, 12366, beijing, shanghai, guangdong)
        channels: 要爬取的栏目列表
        **kwargs: 额外参数
    """
    logger = logging.getLogger("Main")
    logger.info(f"Starting crawler for: {source_name}")

    # 创建爬虫实例
    crawlers = {
        'chinatax': ChinaTaxCrawler(),
        'beijing': BeijingTaxCrawler(),
        'shanghai': ShanghaiTaxCrawler(),
        'guangdong': GuangdongTaxCrawler(),
    }

    if source_name not in crawlers:
        logger.error(f"Unknown source: {source_name}")
        return

    crawler = crawlers[source_name]

    # 创建数据库连接
    db = MongoDBConnector()

    # 创建爬取任务
    task_id = f"{source_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    task = CrawlTask(
        task_id=task_id,
        source=source_name,
        status='running',
        start_time=datetime.now()
    )
    db.save_crawl_task(task)

    try:
        # 确定要爬取的栏目
        if channels is None:
            channels = ['all']

        # 爬取数据
        all_documents = []

        for channel in channels:
            logger.info(f"Crawling channel: {channel}")
            documents = crawler.crawl_channel(channel, **kwargs)
            all_documents.extend(documents)

            # 批量保存到数据库
            if documents:
                stats = db.insert_policies(documents)
                logger.info(f"Channel {channel} saved to DB: {stats}")

        # 更新任务状态
        crawler_stats = crawler.get_stats()
        db.update_crawl_task(task_id, {
            'status': 'completed',
            'end_time': datetime.now(),
            'total_count': crawler_stats['total'],
            'success_count': crawler_stats['success'],
            'failed_count': crawler_stats['failed']
        })

        # 输出统计
        db_stats = db.get_stats()
        logger.info(f"Crawl completed for {source_name}")
        logger.info(f"Crawler stats: {crawler_stats}")
        logger.info(f"DB stats: total={db_stats['total']}")

    except Exception as e:
        logger.error(f"Crawl failed: {e}", exc_info=True)
        db.update_crawl_task(task_id, {
            'status': 'failed',
            'end_time': datetime.now(),
            'error_message': str(e)
        })

    finally:
        db.close()


def run_all(**kwargs):
    """运行所有爬虫"""
    sources = ['chinatax', 'beijing', 'shanghai', 'guangdong']

    for source in sources:
        try:
            run_crawler(source, **kwargs)
        except Exception as e:
            logging.getLogger("Main").error(f"Failed to crawl {source}: {e}")


def main():
    """主函数"""
    setup_logging()

    import argparse

    parser = argparse.ArgumentParser(description='税务政策爬虫')
    parser.add_argument('--source', type=str, default='chinatax',
                        help='数据源 (chinatax, beijing, shanghai, guangdong, all)')
    parser.add_argument('--channel', type=str, default='all',
                        help='栏目名称 (all, interpretation, hot_qa, etc.)')
    parser.add_argument('--start-year', type=int, default=2022,
                        help='起始年份')
    parser.add_argument('--end-year', type=int, default=2025,
                        help='结束年份')
    parser.add_argument('--limit', type=int, default=20,
                        help='每次获取数量')

    args = parser.parse_args()

    if args.source == 'all':
        run_all(
            start_year=args.start_year,
            end_year=args.end_year,
            limit=args.limit
        )
    else:
        run_crawler(
            args.source,
            channels=[args.channel],
            start_year=args.start_year,
            end_year=args.end_year,
            limit=args.limit
        )


if __name__ == '__main__':
    main()
