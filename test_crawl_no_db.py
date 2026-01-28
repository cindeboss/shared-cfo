#!/usr/bin/env python3
"""
爬虫测试脚本 - 不使用数据库，仅测试爬取功能
"""

import logging
import sys
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("TestCrawl")

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_chinatax_crawler():
    """测试国家税务总局爬虫"""
    logger.info("=" * 60)
    logger.info("测试国家税务总局爬虫")
    logger.info("=" * 60)

    from crawler.chinatax_crawler_v4 import ChinaTaxCrawler

    # 不传入数据库连接
    crawler = ChinaTaxCrawler(db_connector=None)

    try:
        # 测试爬取法律列表页
        logger.info("\n[1] 测试爬取列表页...")
        list_url = "https://fgk.chinatax.gov.cn/zcfgk/c100001/listflfg.html"
        urls = crawler.crawl_list_page(list_url)
        logger.info(f"找到 {len(urls)} 个详情页链接")

        # 打印前几个链接
        for i, url in enumerate(urls[:3]):
            logger.info(f"  [{i+1}] {url}")

        if urls:
            # 测试爬取详情页
            logger.info("\n[2] 测试爬取详情页...")
            detail_url = urls[0]
            response = crawler._make_request(detail_url)

            if response:
                logger.info(f"成功获取详情页: {detail_url[:60]}...")

                # 测试内容提取
                logger.info("\n[3] 测试内容提取...")
                soup = crawler._parse_html(response.text)
                page_data = crawler.extract_content_from_page(soup)

                logger.info(f"  标题: {page_data.get('title', 'N/A')[:60]}...")
                logger.info(f"  内容长度: {len(page_data.get('content', ''))} 字符")

                # 测试字段提取
                logger.info("\n[4] 测试字段提取...")
                policy_data = crawler.process_policy(detail_url, response.text)

                if policy_data:
                    logger.info(f"  政策ID: {policy_data.get('policy_id')}")
                    logger.info(f"  文件层级: {policy_data.get('document_level')}")
                    logger.info(f"  文件类型: {policy_data.get('document_type')}")
                    logger.info(f"  税收类别: {policy_data.get('tax_category')}")
                    logger.info(f"  税种: {policy_data.get('tax_type')}")
                    logger.info(f"  质量分数: {policy_data.get('quality_score')}/100")
                    logger.info("\n[OK] 爬虫测试成功!")
                else:
                    logger.error("[FAIL] 未能提取政策数据")
            else:
                logger.error("[FAIL] 无法获取详情页")
        else:
            logger.warning("[WARN] 未找到任何详情页链接")

    except Exception as e:
        logger.error(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        crawler.close()

    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == '__main__':
    test_chinatax_crawler()
