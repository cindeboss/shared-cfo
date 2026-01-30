#!/usr/bin/env python3
"""
共享CFO - 爬虫监控工具

实时监控爬虫运行状态，及时发现和纠正问题
"""

from pymongo import MongoClient
import argparse
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict
import subprocess


# MongoDB 配置
MONGO_CONFIG = {
    'host': 'localhost',  # Use localhost for both local and server execution
    'port': 27017,
    'database': 'shared_cfo',
    'collection': 'policies',
}


class CrawlerMonitor:
    """爬虫监控器"""

    def __init__(self, config):
        self.config = config
        self.client = None
        self.db = None
        self.collection = None

    def connect(self):
        """连接数据库"""
        try:
            uri = f"mongodb://{self.config['host']}:{self.config['port']}"
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.config['database']]
            self.collection = self.db[self.config['collection']]
            self.client.admin.command('ping')
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.client:
            self.client.close()

    def get_crawl_stats(self, hours: int = 24) -> dict:
        """获取爬取统计"""
        since = datetime.now() - timedelta(hours=hours)

        # 最近爬取的数据
        recent_policies = list(self.collection.find({'crawled_at': {'$gte': since.isoformat()}}))

        # 按时间分组统计
        hourly_stats = defaultdict(int)
        for policy in recent_policies:
            crawled_at = policy.get('crawled_at', '')
            if crawled_at:
                try:
                    dt = datetime.fromisoformat(crawled_at)
                    hour_key = dt.strftime('%Y-%m-%d %H:00')
                    hourly_stats[hour_key] += 1
                except:
                    pass

        # 按来源统计
        source_stats = defaultdict(int)
        for policy in recent_policies:
            source_stats[policy.get('source', '未知')] += 1

        # 按层级统计
        level_stats = defaultdict(int)
        for policy in recent_policies:
            level_stats[policy.get('document_level', '未知')] += 1

        # 数据质量检查
        quality_issues = {
            'missing_title': self.collection.count_documents({'title': {'$exists': False}}),
            'missing_url': self.collection.count_documents({'url': {'$exists': False}}),
            'missing_level': self.collection.count_documents({'document_level': {'$exists': False}}),
            'missing_content': self.collection.count_documents({
                'content': {'$exists': False},
                'crawled_at': {'$gte': since.isoformat()}  # 只检查最近的数据
            }),
        }

        return {
            'period_hours': hours,
            'total_recent': len(recent_policies),
            'hourly_stats': dict(hourly_stats),
            'source_stats': dict(source_stats),
            'level_stats': dict(level_stats),
            'quality_issues': quality_issues,
            'total_db': self.collection.count_documents({}),
        }

    def get_error_logs(self, hours: int = 24) -> list:
        """从日志文件获取错误信息（如果有）"""
        # 这个需要读取日志文件，暂时返回模拟数据
        return []

    def check_data_quality(self) -> dict:
        """检查数据质量"""
        total = self.collection.count_documents({})

        checks = {
            'completeness': {
                'title': self.collection.count_documents({'title': {'$exists': True, '$ne': ''}}),
                'url': self.collection.count_documents({'url': {'$exists': True, '$ne': ''}}),
                'source': self.collection.count_documents({'source': {'$exists': True, '$ne': ''}}),
                'document_level': self.collection.count_documents({'document_level': {'$exists': True, '$ne': ''}}),
            },
            'uniqueness': {
                'total': total,
                'unique_urls': len(set(p.get('url', '') for p in self.collection.find({}, {'url': 1}))),
                'unique_policy_ids': len(set(p.get('policy_id', '') for p in self.collection.find({}, {'policy_id': 1}))),
            },
            'freshness': {
                'total': total,
                'last_7_days': self.collection.count_documents({
                    'crawled_at': {'$gte': (datetime.now() - timedelta(days=7)).isoformat()}
                }),
                'last_30_days': self.collection.count_documents({
                    'crawled_at': {'$gte': (datetime.now() - timedelta(days=30)).isoformat()}
                }),
            },
        }

        # 计算完整性百分比
        checks['completeness_percentage'] = {
            field: f"{count / total * 100:.1f}%" if total > 0 else "N/A"
            for field, count in checks['completeness'].items()
        }

        return checks


def print_dashboard(stats: dict, quality: dict):
    """打印监控面板"""
    print()
    print("╔" + "═" * 76 + "╗")
    print("║" + " " * 76 + "║")
    print("║" + "        共享CFO - 爬虫监控面板".center(70) + "        ║")
    print("║" + " " * 76 + "║")
    print("╠" + "═" * 76 + "╣")
    print("║" + " " * 76 + "║")
    print("║" + f"  监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(76) + "║")
    print("║" + " " * 76 + "║")

    # 爬取统计
    print("╠" + "─" * 76 + "╣")
    print("║  📊 爬取统计 (最近 {} 小时)".format(stats['period_hours']).ljust(76) + "║")
    print("║" + " " * 76 + "║")
    print(f"║  总政策数: {stats['total_db']}".ljust(30) + f"最近爬取: {stats['total_recent']}".ljust(46) + "║")
    print("║" + " " * 76 + "║")

    # 按来源统计
    print("║  📌 按数据来源:".ljust(76) + "║")
    for source, count in sorted(stats['source_stats'].items(), key=lambda x: -x[1]):
        print(f"║    {source.ljust(20)} {count} 条".ljust(52) + "║")

    print("║" + " " * 76 + "║")

    # 按层级统计
    print("║  📚 按层级:".ljust(76) + "║")
    for level, count in sorted(stats['level_stats'].items()):
        print(f"║    {level.ljust(20)} {count} 条".ljust(52) + "║")

    print("║" + " " * 76 + "║")

    # 数据质量
    print("║" + "  ✅ 数据质量检查:".ljust(76) + "║")
    print("║" + " " * 76 + "║")
    print(f"║    缺少标题: {quality['completeness']['title']} / {stats['total_db']}".ljust(76) + "║")
    print(f"║    缺少URL: {quality['completeness']['url']} / {stats['total_db']}".ljust(76) + "║")
    print(f"║    缺少层级: {quality['completeness']['document_level']} / {stats['total_db']}".ljust(76) + "║")
    print(f"║    唯一URL: {quality['uniqueness']['unique_urls']}".ljust(76) + "║")
    print(f"║    唯一ID: {quality['uniqueness']['unique_policy_ids']}".ljust(76) + "║")

    print("║" + " " * 76 + "║")

    # 最近爬取趋势
    print("║  📈 最近爬取趋势:".ljust(76) + "║")
    print("║" + " " * 76 + "║")
    for hour, count in sorted(stats['hourly_stats'].items())[-10:]:
        print(f"║    {hour}: {count} 条".ljust(70) + "║")

    print("╚" + "═" * 76 + "╝")
    print()


def print_issues(quality: dict):
    """打印问题清单"""
    issues = []

    if quality['completeness']['title'] > 0:
        issues.append(f"⚠️  {quality['completeness']['title']} 条政策缺少标题")

    if quality['completeness']['url'] > 0:
        issues.append(f"⚠️  {quality['completeness']['url']} 条政策缺少URL")

    if quality['uniqueness']['unique_urls'] < quality['uniqueness']['total']:
        duplicate = quality['uniqueness']['total'] - quality['uniqueness']['unique_urls']
        issues.append(f"⚠️  发现 {duplicate} 条重复的URL")

    if quality['freshness']['last_7_days'] == 0:
        issues.append("⚠️  最近7天没有新数据爬取")

    if quality['freshness']['last_30_days'] == 0:
        issues.append("⚠️  最近30天没有新数据爬取")

    if issues:
        print("\n🚨 发现的问题:")
        print("-" * 50)
        for issue in issues:
            print(issue)
        print()
    else:
        print("\n✅ 没有发现明显问题")


def cmd_monitor(args):
    """监控命令"""
    monitor = CrawlerMonitor(MONGO_CONFIG)
    if not monitor.connect():
        return 1

    try:
        # 获取统计
        stats = monitor.get_crawl_stats(hours=args.hours)
        quality = monitor.check_data_quality()

        # 显示面板
        print_dashboard(stats, quality)

        # 显示问题
        print_issues(quality)

        # 建议
        print("💡 建议:")
        print("-" * 50)
        print("1. 定期运行此监控工具检查爬虫状态")
        print("2. 如发现重复数据，运行去重: python policy_query.py search '' | sort | uniq -d")
        print("3. 如发现数据质量下降，检查爬虫日志")
        print("4. 关注爬取趋势，及时调整爬取策略")

    finally:
        monitor.disconnect()

    return 0


def cmd_watch(args):
    """实时监控模式"""
    monitor = CrawlerMonitor(MONGO_CONFIG)
    if not monitor.connect():
        return 1

    try:
        print(f"🔄 实时监控模式 (每 {args.interval} 秒刷新，按 Ctrl+C 退出)")
        print()

        iteration = 0
        while True:
            iteration += 1
            print(f"\n[{iteration}] 刷新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            stats = monitor.get_crawl_stats(hours=1)
            quality = monitor.check_data_quality()

            # 简化显示
            print(f"  总数: {stats['total_db']} | 最近1小时: {stats['total_recent']} 条")
            print(f"  来源: {', '.join(f'{k}:{v}' for k, v in stats['source_stats'].items())}")
            print(f"  层级: {', '.join(f'{k}:{v}' for k, v in stats['level_stats'].items())}")

            # 检查问题
            issues = []
            if quality['completeness']['title'] > 10:
                issues.append("缺少标题")
            if quality['uniqueness']['unique_urls'] < quality['uniqueness']['total'] * 0.95:
                issues.append("有重复URL")

            if issues:
                print(f"  ⚠️  问题: {', '.join(issues)}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\n监控已停止")
    finally:
        monitor.disconnect()

    return 0


def cmd_crawler_status(args):
    """检查爬虫服务状态"""
    print("🔍 检查爬虫服务状态...")
    print()

    # 检查 MongoDB
    try:
        uri = f"mongodb://{MONGO_CONFIG['host']}:{MONGO_CONFIG['port']}"
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✅ MongoDB 连接正常")
        client.close()
    except:
        print("❌ MongoDB 连接失败")
        return 1

    # 检查 systemd 服务
    try:
        # 检查本地爬虫服务状态
        import subprocess
        try:
            result = subprocess.run(['systemctl', 'status', 'shared-cfo-crawler'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("\n✅ 爬虫服务状态:")
                for line in result.stdout.split('\n')[:10]:
                    print(f"   {line}")
            else:
                print("\n⚠️  爬虫服务未运行或未安装")
                print("   安装命令: systemctl enable /opt/shared_cfo/scrapy_crawler.service")
        except Exception as e:
            print(f"\n⚠️  无法检查服务状态: {e}")
        print(f"\n📋 查看爬虫日志:")
        print(f"   tail -50 /opt/shared_cfo/logs/crawler.log")
    except Exception as e:
        print(f"⚠️  无法检查服务状态: {e}")

    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='共享CFO - 爬虫监控工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--host', default=MONGO_CONFIG['host'], help='MongoDB 主机')
    parser.add_argument('--port', type=int, default=MONGO_CONFIG['port'], help='MongoDB 端口')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # monitor 命令
    monitor_parser = subparsers.add_parser('monitor', help='监控爬虫状态')
    monitor_parser.add_argument('--hours', type=int, default=24, help='统计时间范围（小时）')

    # watch 命令
    watch_parser = subparsers.add_parser('watch', help='实时监控')
    watch_parser.add_argument('--interval', type=int, default=30, help='刷新间隔（秒）')

    # status 命令
    subparsers.add_parser('status', help='检查爬虫服务状态')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # 更新配置
    MONGO_CONFIG['host'] = args.host
    MONGO_CONFIG['port'] = args.port

    commands = {
        'monitor': cmd_monitor,
        'watch': cmd_watch,
        'status': cmd_crawler_status,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return cmd_func(args)

    return 0


if __name__ == '__main__':
    sys.exit(main())
