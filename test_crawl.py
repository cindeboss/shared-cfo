#!/usr/bin/env python3
"""
简化的爬虫测试脚本 - 跳过项目跟踪器
"""

import logging
import sys
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("TestCrawl")

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from crawler.database_v2 import MongoDBConnectorV2
from crawler.chinatax_crawler_v4 import ChinaTaxCrawler
from crawler.crawler_12366_v2 import Crawler12366
from crawler.relationship_builder import PolicyRelationshipBuilder


def main():
    logger.info("=" * 60)
    logger.info("开始爬虫测试")
    logger.info("=" * 60)

    # 连接数据库
    logger.info("连接数据库...")
    db = MongoDBConnectorV2()

    # 测试爬取少量数据
    logger.info("\n[1/3] 测试国家税务总局爬虫...")
    chinatax_crawler = ChinaTaxCrawler(db)

    try:
        # 只爬1页测试
        stats = chinatax_crawler.crawl_laws(max_pages=1)
        logger.info(f"国家税务总局爬虫结果: {stats}")
    except Exception as e:
        logger.error(f"国家税务总局爬虫错误: {e}")
    finally:
        chinatax_crawler.close()

    # 测试12366爬虫
    logger.info("\n[2/3] 测试12366爬虫...")
    qa_crawler = Crawler12366(db)

    try:
        # 只爬5条测试
        stats = qa_crawler.crawl_hot_questions('增值税', max_results=5)
        logger.info(f"12366爬虫结果: {stats}")
    except Exception as e:
        logger.error(f"12366爬虫错误: {e}")
    finally:
        qa_crawler.close()

    # 构建关联关系
    logger.info("\n[3/3] 构建政策关联关系...")
    builder = PolicyRelationshipBuilder(db)

    try:
        stats = builder.build_all_relationships(batch_size=10)
        logger.info(f"关联关系构建结果: {stats}")
    except Exception as e:
        logger.error(f"关联关系构建错误: {e}")

    # 获取最终统计
    logger.info("\n" + "=" * 60)
    logger.info("最终数据统计:")
    final_stats = db.get_stats()
    logger.info(f"  总政策数: {final_stats['total']}")
    logger.info(f"  按来源:")
    for source_stat in final_stats.get('by_source', [])[:5]:
        logger.info(f"    - {source_stat['_id']}: {source_stat['count']}条")
    logger.info("=" * 60)

    # 关闭数据库
    db.close()

    logger.info("\n测试完成!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
