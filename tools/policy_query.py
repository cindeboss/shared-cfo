#!/usr/bin/env python3
"""
共享CFO - 政策文件本地查询工具

用于查询和管理爬取的税务政策数据
"""

from pymongo import MongoClient
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any
from textwrap import fill
import json


# MongoDB 配置
MONGO_CONFIG = {
    'host': 'localhost',  # Use localhost for both local and server execution
    'port': 27017,
    'database': 'shared_cfo',
    'collection': 'policies',
    'username': '',
    'password': '',
}


class PolicyQueryTool:
    """政策查询工具"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.db = None
        self.collection = None

    def connect(self):
        """连接数据库"""
        try:
            if self.config['username']:
                uri = f"mongodb://{self.config['username']}:{self.config['password']}@{self.config['host']}:{self.config['port']}"
            else:
                uri = f"mongodb://{self.config['host']}:{self.config['port']}"

            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.config['database']]
            self.collection = self.db[self.config['collection']]

            # 测试连接
            self.client.admin.command('ping')
            return True
        except Exception as e:
            print(f"❌ 连接数据库失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.client:
            self.client.close()

    def get_stats(self) -> Dict[str, Any]:
        """获取数据统计"""
        total = self.collection.count_documents({})

        # 按层级统计
        pipeline_level = [
            {"$group": {"_id": "$document_level", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        by_level = {r['_id'] or '未知': r['count'] for r in self.collection.aggregate(pipeline_level)}

        # 按分类统计
        pipeline_category = [
            {"$group": {"_id": "$tax_category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_category = {r['_id'] or '未知': r['count'] for r in self.collection.aggregate(pipeline_category)}

        # 按来源统计
        pipeline_source = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_source = {r['_id'] or '未知': r['count'] for r in self.collection.aggregate(pipeline_source)}

        return {
            'total': total,
            'by_level': by_level,
            'by_category': by_category,
            'by_source': by_source,
        }

    def search(self, keyword: str, level: str = None, category: str = None, limit: int = 20) -> List[Dict]:
        """搜索政策"""
        query = {}

        # 关键词搜索（标题或内容）
        if keyword:
            query['$or'] = [
                {'title': {'$regex': keyword, '$options': 'i'}},
                {'content': {'$regex': keyword, '$options': 'i'}},
            ]

        # 层级过滤
        if level:
            query['document_level'] = level

        # 分类过滤
        if category:
            query['tax_category'] = category

        # 执行查询
        policies = list(self.collection.find(query)
                       .sort([('crawled_at', -1)])
                       .limit(limit))

        return policies

    def get_by_id(self, policy_id: str) -> Dict:
        """根据ID获取政策"""
        return self.collection.find_one({'policy_id': policy_id})

    def list_recent(self, limit: int = 20) -> List[Dict]:
        """列出最近爬取的政策"""
        return list(self.collection.find()
                       .sort([('crawled_at', -1)])
                       .limit(limit))

    def export_to_file(self, policies: List[Dict], filename: str):
        """导出到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# 共享CFO - 政策文件导出\n\n")
                f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"文件数量: {len(policies)}\n\n")
                f.write("---\n\n")

                for i, policy in enumerate(policies, 1):
                    f.write(f"## [{i}] {policy.get('title', 'N/A')}\n\n")

                    # 基本信息
                    f.write("**基本信息**\n\n")
                    f.write(f"- Policy ID: {policy.get('policy_id', 'N/A')}\n")
                    f.write(f"- 来源: {policy.get('source', 'N/A')}\n")
                    f.write(f"- 层级: {policy.get('document_level', 'N/A')}\n")
                    f.write(f"- 分类: {policy.get('tax_category', 'N/A')}\n")

                    if policy.get('document_type'):
                        f.write(f"- 文档类型: {policy.get('document_type', 'N/A')}\n")

                    if policy.get('url'):
                        f.write(f"- 原文链接: {policy.get('url')}\n")

                    f.write(f"- 爬取时间: {policy.get('crawled_at', 'N/A')}\n\n")

                    # 正文内容
                    content = policy.get('content', '')
                    if content:
                        f.write("**正文内容**\n\n")
                        # 限制内容长度
                        display_content = content[:5000] if len(content) > 5000 else content
                        f.write(f"{display_content}\n\n")
                        if len(content) > 5000:
                            f.write(f"(内容已截断，完整长度: {len(content)} 字符)\n\n")

                    f.write("---\n\n")

            print(f"✅ 已导出 {len(policies)} 条政策到: {filename}")
            return True
        except Exception as e:
            print(f"❌ 导出失败: {e}")
            return False


def print_policy(policy: Dict, show_content: bool = False, content_length: int = 500):
    """打印政策信息"""
    print()
    print("=" * 70)
    print(f"  {policy.get('title', 'N/A')}")
    print("=" * 70)

    print(f"Policy ID:  {policy.get('policy_id', 'N/A')}")
    print(f"来源:        {policy.get('source', 'N/A')}")
    print(f"层级:        {policy.get('document_level', 'N/A')}")
    print(f"分类:        {', '.join(policy.get('tax_category', []))}")
    print(f"文档类型:    {policy.get('document_type', 'N/A')}")

    if policy.get('url'):
        print(f"原文链接:    {policy.get('url')}")

    print(f"爬取时间:    {policy.get('crawled_at', 'N/A')}")

    # 显示正文
    if show_content and policy.get('content'):
        content = policy['content']
        print()
        print("正文内容:")
        print("-" * 70)

        # 格式化显示正文
        display_content = content[:content_length] if len(content) > content_length else content
        print(display_content)

        if len(content) > content_length:
            print()
            print(f"(内容已截断，完整长度: {len(content)} 字符)")

    print("=" * 70)
    print()


def print_stats(stats: Dict[str, Any]):
    """打印统计信息"""
    print()
    print("=" * 50)
    print("  数据统计")
    print("=" * 50)
    print(f"总政策数: {stats['total']}")
    print()

    print("按层级:")
    for level, count in sorted(stats['by_level'].items()):
        print(f"  {level or '未知'}: {count} 条")
    print()

    print("按分类:")
    for category, count in sorted(stats['by_category'].items()):
        print(f"  {category or '未知'}: {count} 条")
    print()

    print("按来源:")
    for source, count in sorted(stats['by_source'].items()):
        print(f"  {source}: {count} 条")

    print("=" * 50)
    print()


def cmd_stats(args):
    """统计数据命令"""
    tool = PolicyQueryTool(MONGO_CONFIG)
    if not tool.connect():
        return 1

    try:
        stats = tool.get_stats()
        print_stats(stats)
    finally:
        tool.disconnect()

    return 0


def cmd_search(args):
    """搜索命令"""
    tool = PolicyQueryTool(MONGO_CONFIG)
    if not tool.connect():
        return 1

    try:
        print(f"🔍 搜索关键词: {args.keyword}")
        if args.level:
            print(f"   层级过滤: {args.level}")
        if args.category:
            print(f"   分类过滤: {args.category}")
        print()

        results = tool.search(
            keyword=args.keyword,
            level=args.level,
            category=args.category,
            limit=args.limit
        )

        if not results:
            print("❌ 未找到匹配的政策")
            return 0

        print(f"✅ 找到 {len(results)} 条匹配的政策")
        print()

        for i, policy in enumerate(results, 1):
            print(f"[{i}] {policy.get('title', 'N/A')}")
            print(f"    Policy ID: {policy.get('policy_id', 'N/A')}")
            print(f"    来源: {policy.get('source', 'N/A')}")
            print(f"    层级: {policy.get('document_level', 'N/A')}")
            print(f"    爬取时间: {policy.get('crawled_at', 'N/A')}")
            print()

        # 询问是否查看详情
        if args.interactive and len(results) > 0:
            try:
                choice = input("输入编号查看详情 (0=退出): ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(results):
                    policy = results[int(choice) - 1]
                    print_policy(policy, show_content=True, content_length=args.content_length)
            except (KeyboardInterrupt, EOFError):
                print("\n")

    finally:
        tool.disconnect()

    return 0


def cmd_list(args):
    """列表命令"""
    tool = PolicyQueryTool(MONGO_CONFIG)
    if not tool.connect():
        return 1

    try:
        print(f"📋 最近爬取的政策 (前 {args.limit} 条)")
        print()

        policies = tool.list_recent(limit=args.limit)

        if not policies:
            print("❌ 数据库中没有政策")
            return 0

        for i, policy in enumerate(policies, 1):
            print(f"[{i}] {policy.get('title', 'N/A')}")
            print(f"    Policy ID: {policy.get('policy_id', 'N/A')}")
            print(f"    来源: {policy.get('source', 'N/A')}")
            print(f"    层级: {policy.get('document_level', 'N/A')}")
            print()

        print(f"共 {len(policies)} 条，使用 search 命令搜索具体内容")

    finally:
        tool.disconnect()

    return 0


def cmd_view(args):
    """查看详情命令"""
    tool = PolicyQueryTool(MONGO_CONFIG)
    if not tool.connect():
        return 1

    try:
        policy = tool.get_by_id(args.policy_id)

        if not policy:
            print(f"❌ 未找到 Policy ID: {args.policy_id}")
            return 1

        print_policy(policy, show_content=True, content_length=args.content_length)

    finally:
        tool.disconnect()

    return 0


def cmd_export(args):
    """导出命令"""
    tool = PolicyQueryTool(MONGO_CONFIG)
    if not tool.connect():
        return 1

    try:
        # 构建查询
        policies = tool.search(
            keyword=args.keyword if hasattr(args, 'keyword') and args.keyword else None,
            level=args.level if hasattr(args, 'level') and args.level else None,
            category=args.category if hasattr(args, 'category') and args.category else None,
            limit=args.limit or 100
        )

        if not policies:
            print("❌ 没有数据可导出")
            return 1

        tool.export_to_file(policies, args.output)

    finally:
        tool.disconnect()

    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='共享CFO - 政策文件本地查询工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看数据统计
  python policy_query.py stats

  # 搜索包含"增值税"的政策
  python policy_query.py search 增值税

  # 按层级搜索
  python policy_query.py search 增值税 --level L1

  # 列出最近的政策
  python policy_query.py list --limit 10

  # 查看指定政策详情
  python policy_query.py view TEST_001

  # 导出搜索结果
  python policy_query.py export 增值税 -o 增值税政策.md

  # 交互式搜索
  python policy_query.py search 企业所得税 --interactive
        """
    )

    # 全局参数
    parser.add_argument('--host', default=MONGO_CONFIG['host'], help='MongoDB 主机')
    parser.add_argument('--port', type=int, default=MONGO_CONFIG['port'], help='MongoDB 端口')
    parser.add_argument('--database', default=MONGO_CONFIG['database'], help='数据库名')

    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # stats 命令
    subparsers.add_parser('stats', help='数据统计')

    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索政策')
    search_parser.add_argument('keyword', help='搜索关键词')
    search_parser.add_argument('--level', help='层级过滤 (L1/L2/L3/L4)')
    search_parser.add_argument('--category', help='分类过滤')
    search_parser.add_argument('--limit', type=int, default=20, help='返回数量限制')
    search_parser.add_argument('--interactive', '-i', action='store_true', help='交互式查看详情')
    search_parser.add_argument('--content-length', type=int, default=1000, help='显示正文字符数')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出政策')
    list_parser.add_argument('--limit', type=int, default=20, help='显示数量')

    # view 命令
    view_parser = subparsers.add_parser('view', help='查看政策详情')
    view_parser.add_argument('policy_id', help='Policy ID')
    view_parser.add_argument('--content-length', type=int, default=2000, help='显示正文字符数')

    # export 命令
    export_parser = subparsers.add_parser('export', help='导出数据')
    export_parser.add_argument('keyword', nargs='?', help='搜索关键词')
    export_parser.add_argument('--level', help='层级过滤')
    export_parser.add_argument('--category', help='分类过滤')
    export_parser.add_argument('--limit', type=int, default=100, help='导出数量限制')
    export_parser.add_argument('-o', '--output', required=True, help='输出文件名')

    args = parser.parse_args()

    # 更新配置
    MONGO_CONFIG['host'] = args.host
    MONGO_CONFIG['port'] = args.port
    MONGO_CONFIG['database'] = args.database

    if not args.command:
        parser.print_help()
        return 0

    # 执行命令
    commands = {
        'stats': cmd_stats,
        'search': cmd_search,
        'list': cmd_list,
        'view': cmd_view,
        'export': cmd_export,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return cmd_func(args)
    else:
        print(f"未知命令: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
