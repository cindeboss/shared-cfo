#!/usr/bin/env python3
"""
共享CFO - 税务政策爬虫系统主入口

根据《共享CFO - 爬虫模块需求文档 v3.0》实现

功能：
1. 爬取国家税务总局政策法规库
2. 爬取12366纳税服务平台热点问答
3. 建立政策关联关系和立法链路
4. 数据质量验证和去重
5. 生成数据统计报告

合规性：
- 遵守robots.txt协议
- 限制访问频率，避免对服务器造成负担
- 只爬取公开的政府政策信息
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from crawler.database import MongoDBConnector
from crawler.orchestrator import CrawlerOrchestrator
from crawler.relationship_builder import PolicyRelationshipBuilder
from crawler.quality_validator import DataQualityValidator
from project_tracker import get_tracker


def setup_logging(level: str = "INFO"):
    """设置日志"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(project_root / 'logs' / f'crawler_{datetime.now().strftime("%Y%m%d")}.log',
                               encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # 确保日志目录存在
    (project_root / 'logs').mkdir(exist_ok=True)


def cmd_crawl(args):
    """执行爬取任务"""
    tracker = get_tracker()
    tracker.add_note(f"开始爬取任务: phase={args.phase}")

    db = MongoDBConnector()
    orchestrator = CrawlerOrchestrator(db)

    try:
        if args.phase == 'test':
            results = orchestrator.run_quick_test()
            tracker.complete_task("quick_test", f"测试完成，成功爬取 {results.get('total_success', 0)} 条")
        elif args.phase == 'week1':
            results = orchestrator.run_phase1_week1()
            tracker.complete_task("phase1_week1", f"Week 1完成，成功爬取 {results.get('total_success', 0)} 条")
        elif args.phase == 'week2':
            results = orchestrator.run_phase1_week2()
            tracker.complete_task("phase1_week2", f"Week 2完成，成功爬取 {results.get('total_success', 0)} 条")
        elif args.phase == 'week3':
            results = orchestrator.run_phase1_week3()
            tracker.complete_task("phase1_week3", f"Week 3完成，成功爬取 {results.get('total_success', 0)} 条")
        elif args.phase == 'complete':
            results = orchestrator.run_phase1_complete()
            tracker.complete_task("phase1_complete", f"Phase 1完成，成功爬取 {results.get('total_success', 0)} 条")
        else:
            print(f"Unknown phase: {args.phase}")
            return 1

        # 更新数据统计
        stats = db.get_stats()
        tracker.update_data_stats(stats)

        print(f"\n爬取任务完成！")
        print(f"总计: {results.get('total_success', 0)} 条成功")
        print_results(results)

    finally:
        db.close()

    return 0


def cmd_build_relationships(args):
    """构建政策关联关系"""
    tracker = get_tracker()
    tracker.add_note("开始构建政策关联关系")

    db = MongoDBConnector()
    builder = PolicyRelationshipBuilder(db)

    try:
        results = builder.build_all_relationships(batch_size=args.batch_size)
        tracker.complete_task("build_relationships", f"关联关系构建完成")

        print(f"\n关联关系构建完成！")
        print(f"  总计处理: {results['total']} 条")
        print(f"  建立上位法关系: {results['with_parent']} 条")
        print(f"  构建立法链路: {results['with_chain']} 条")
        print(f"  建立相关关联: {results['with_related']} 条")
        print(f"  问答关联原文: {results['qa_linked']} 条")

    finally:
        db.close()

    return 0


def cmd_validate(args):
    """验证数据质量"""
    tracker = get_tracker()
    tracker.add_note("开始验证数据质量")

    db = MongoDBConnector()
    validator = DataQualityValidator(db)

    try:
        results = validator.validate_all()

        print(f"\n数据质量验证完成！")
        print(f"  总政策数: {results['total_policies']}")
        print(f"  有效政策: {results['valid_policies']}")
        print(f"  问题政策: {results['invalid_policies']}")
        print(f"  质量分数: {results['quality_score']:.1f}%")

        if results['issues_by_type']:
            print(f"\n问题分布:")
            for issue_type, count in results['issues_by_type'].items():
                print(f"  {issue_type}: {count}")

    finally:
        db.close()

    return 0


def cmd_deduplicate(args):
    """数据去重"""
    tracker = get_tracker()
    tracker.add_note("开始数据去重")

    db = MongoDBConnector()
    validator = DataQualityValidator(db)

    try:
        results = validator.deduplicate_policies()

        print(f"\n去重完成！")
        print(f"  总政策数: {results['total']}")
        print(f"  URL重复: {results['url_duplicates']}")
        print(f"  标题+日期重复: {results['title_date_duplicates']}")
        print(f"  内容重复: {results['content_duplicates']}")
        print(f"  删除重复: {results['removed']}")

    finally:
        db.close()

    return 0


def cmd_status(args):
    """查看系统状态"""
    db = MongoDBConnector()

    try:
        report = CrawlerOrchestrator(db).get_progress_report()

        print(f"\n【共享CFO - 爬虫系统状态】")
        print(f"生成时间: {report['timestamp']}\n")

        print(f"数据统计:")
        stats = report['data_stats']
        print(f"  总政策数: {stats['total']}")

        if stats.get('by_level'):
            print(f"  按层级:")
            for level, count in stats['by_level'].items():
                print(f"    {level}: {count} 条")

        if stats.get('by_category'):
            print(f"  按类别:")
            for category, count in stats['by_category'].items():
                print(f"    {category}: {count} 条")

        print(f"\n质量报告:")
        quality = report['quality_report']
        print(f"  总政策数: {quality['total_policies']}")
        print(f"  质量等级: {quality['overall_quality_level']}")

        if quality['issues']:
            print(f"  问题:")
            for issue in quality['issues'][:5]:
                print(f"    - {issue}")

    finally:
        db.close()

    return 0


def cmd_export(args):
    """导出数据报告"""
    db = MongoDBConnector()

    try:
        quality_report = db.get_quality_report()

        output_file = args.output or project_root / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 共享CFO - 税务政策数据报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("## 数据统计\n\n")
            f.write(f"- 总政策数: {quality_report.total_policies}\n")

            f.write("\n## 按层级统计\n\n")
            for level, count in quality_report.by_level.items():
                f.write(f"- {level}: {count} 条\n")

            f.write("\n## 按类别统计\n\n")
            for category, count in quality_report.by_category.items():
                f.write(f"- {category}: {count} 条\n")

            f.write("\n## 质量评分\n\n")
            f.write(f"- 完整性: {quality_report.completeness_score:.1f}%\n")
            f.write(f"- 权威性: {quality_report.authority_score:.1f}%\n")
            f.write(f"- 关联性: {quality_report.relationship_score:.1f}%\n")
            f.write(f"- 时效性: {quality_report.timeliness_score:.1f}%\n")
            f.write(f"- 内容质量: {quality_report.content_quality_score:.1f}%\n")
            f.write(f"- 总体等级: {quality_report.overall_quality_level}\n")

            if quality_report.issues:
                f.write("\n## 发现的问题\n\n")
                for issue in quality_report.issues:
                    f.write(f"- {issue}\n")

        print(f"\n报告已导出到: {output_file}")

    finally:
        db.close()

    return 0


def print_results(results: dict):
    """打印结果摘要"""
    if 'tasks' in results:
        for task in results['tasks']:
            name = task.get('name', '未知')
            stats = task.get('stats', {})
            print(f"  {name}: 成功={stats.get('success', 0)}, "
                  f"失败={stats.get('failed', 0)}, "
                  f"重复={stats.get('duplicate', 0)}")


def main():
    """主函数"""
    # 启动项目跟踪器
    tracker = get_tracker()
    tracker.add_note("系统启动")

    parser = argparse.ArgumentParser(
        description='共享CFO - 税务政策爬虫系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行快速测试
  python run_crawler.py crawl --phase test

  # 运行Phase 1 Week 1
  python run_crawler.py crawl --phase week1

  # 构建关联关系
  python run_crawler.py build-relationships

  # 验证数据质量
  python run_crawler.py validate

  # 查看系统状态
  python run_crawler.py status

  # 导出报告
  python run_crawler.py export -o report.md
        """
    )

    parser.add_argument('--log-level', default='INFO',
                       help='日志级别 (DEBUG, INFO, WARNING, ERROR)')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # crawl命令
    crawl_parser = subparsers.add_parser('crawl', help='执行爬取任务')
    crawl_parser.add_argument('--phase', choices=['test', 'week1', 'week2', 'week3', 'complete'],
                             default='test', help='爬取阶段')

    # build-relationships命令
    rel_parser = subparsers.add_parser('build-relationships', help='构建政策关联关系')
    rel_parser.add_argument('--batch-size', type=int, default=100,
                           help='批处理大小')

    # validate命令
    subparsers.add_parser('validate', help='验证数据质量')

    # deduplicate命令
    subparsers.add_parser('deduplicate', help='数据去重')

    # status命令
    subparsers.add_parser('status', help='查看系统状态')

    # export命令
    export_parser = subparsers.add_parser('export', help='导出数据报告')
    export_parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    # 设置日志
    setup_logging(args.log_level)

    if not args.command:
        parser.print_help()
        return 0

    # 执行命令
    commands = {
        'crawl': cmd_crawl,
        'build-relationships': cmd_build_relationships,
        'validate': cmd_validate,
        'deduplicate': cmd_deduplicate,
        'status': cmd_status,
        'export': cmd_export,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return cmd_func(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
