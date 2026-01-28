#!/usr/bin/env python3
"""
共享CFO - Web版查询监控工具
Flask Web服务器
"""

from flask import Flask, render_template, jsonify, request, send_file
from pymongo import MongoClient
from datetime import datetime, timedelta
from collections import defaultdict
import io

app = Flask(__name__)

# MongoDB 配置
MONGO_CONFIG = {
    'host': 'localhost',  # 在服务器上使用localhost
    'port': 27017,
    'database': 'shared_cfo',
    'collection': 'policies',
}


def get_collection():
    """获取MongoDB集合"""
    client = MongoClient(f"mongodb://{MONGO_CONFIG['host']}:{MONGO_CONFIG['port']}", serverSelectionTimeoutMS=5000)
    db = client[MONGO_CONFIG['database']]
    return db[MONGO_CONFIG['collection']], client


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/stats')
def api_stats():
    """获取数据统计"""
    collection, client = get_collection()
    try:
        total = collection.count_documents({})

        # 按层级统计
        pipeline_level = [
            {"$group": {"_id": "$level", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        by_level = {r['_id'] or '未知': r['count'] for r in collection.aggregate(pipeline_level)}

        # 按分类统计
        pipeline_category = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_category = {r['_id'] or '未知': r['count'] for r in collection.aggregate(pipeline_category)}

        # 按来源统计
        pipeline_source = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_source = {r['_id'] or '未知': r['count'] for r in collection.aggregate(pipeline_source)}

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'by_level': by_level,
                'by_category': by_category,
                'by_source': by_source,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        client.close()


@app.route('/api/search')
def api_search():
    """搜索政策"""
    collection, client = get_collection()
    try:
        keyword = request.args.get('keyword', '')
        level = request.args.get('level', '')
        source = request.args.get('source', '')
        limit = int(request.args.get('limit', 20))

        query = {}
        if keyword:
            query['$or'] = [
                {'title': {'$regex': keyword, '$options': 'i'}},
                {'content': {'$regex': keyword, '$options': 'i'}},
            ]
        if level:
            query['level'] = level
        if source:
            query['source'] = source

        policies = list(collection.find(query)
                       .sort([('crawled_at', -1)])
                       .limit(limit))

        # 转换ObjectId为字符串
        for p in policies:
            p['_id'] = str(p.get('_id', ''))

        return jsonify({
            'success': True,
            'data': {
                'count': len(policies),
                'policies': policies
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        client.close()


@app.route('/api/policy/<policy_id>')
def api_policy_detail(policy_id):
    """获取政策详情"""
    collection, client = get_collection()
    try:
        policy = collection.find_one({'policy_id': policy_id})
        if policy:
            policy['_id'] = str(policy.get('_id', ''))
            return jsonify({'success': True, 'data': policy})
        else:
            return jsonify({'success': False, 'error': '未找到该政策'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        client.close()


@app.route('/api/recent')
def api_recent():
    """获取最近政策"""
    collection, client = get_collection()
    try:
        limit = int(request.args.get('limit', 20))
        policies = list(collection.find()
                       .sort([('crawled_at', -1)])
                       .limit(limit))

        for p in policies:
            p['_id'] = str(p.get('_id', ''))

        return jsonify({
            'success': True,
            'data': {
                'count': len(policies),
                'policies': policies
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        client.close()


@app.route('/api/monitor')
def api_monitor():
    """获取监控数据"""
    collection, client = get_collection()
    try:
        hours = int(request.args.get('hours', 24))
        since = datetime.now() - timedelta(hours=hours)

        # 最近爬取的数据
        recent_policies = list(collection.find({'crawled_at': {'$gte': since.isoformat()}}))

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
            level_stats[policy.get('level', '未知')] += 1

        # 数据质量检查
        total_db = collection.count_documents({})
        quality_issues = {
            'missing_title': collection.count_documents({'title': {'$exists': False}}),
            'missing_url': collection.count_documents({'url': {'$exists': False}}),
            'missing_level': collection.count_documents({'level': {'$exists': False}}),
            'missing_content': collection.count_documents({
                'content': {'$exists': False},
                'crawled_at': {'$gte': since.isoformat()}
            }),
        }

        return jsonify({
            'success': True,
            'data': {
                'period_hours': hours,
                'total_recent': len(recent_policies),
                'total_db': total_db,
                'hourly_stats': dict(hourly_stats),
                'source_stats': dict(source_stats),
                'level_stats': dict(level_stats),
                'quality_issues': quality_issues,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        client.close()


@app.route('/api/export')
def api_export():
    """导出数据"""
    collection, client = get_collection()
    try:
        keyword = request.args.get('keyword', '')
        level = request.args.get('level', '')
        limit = int(request.args.get('limit', 100))

        query = {}
        if keyword:
            query['$or'] = [
                {'title': {'$regex': keyword, '$options': 'i'}},
                {'content': {'$regex': keyword, '$options': 'i'}},
            ]
        if level:
            query['level'] = level

        policies = list(collection.find(query).limit(limit))

        # 生成Markdown
        output = io.StringIO()
        output.write("# 共享CFO - 政策文件导出\n\n")
        output.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write(f"文件数量: {len(policies)}\n\n")
        output.write("---\n\n")

        for i, policy in enumerate(policies, 1):
            output.write(f"## [{i}] {policy.get('title', 'N/A')}\n\n")

            output.write("**基本信息**\n\n")
            output.write(f"- Policy ID: {policy.get('policy_id', 'N/A')}\n")
            output.write(f"- 来源: {policy.get('source', 'N/A')}\n")
            output.write(f"- 层级: {policy.get('level', 'N/A')}\n")
            output.write(f"- 分类: {policy.get('category', 'N/A')}\n")

            if policy.get('url'):
                output.write(f"- 原文链接: {policy.get('url')}\n")

            output.write(f"- 爬取时间: {policy.get('crawled_at', 'N/A')}\n\n")

            content = policy.get('content', '')
            if content:
                output.write("**正文内容**\n\n")
                display_content = content[:5000] if len(content) > 5000 else content
                output.write(f"{display_content}\n\n")
                if len(content) > 5000:
                    output.write(f"(内容已截断，完整长度: {len(content)} 字符)\n\n")

            output.write("---\n\n")

        # 生成文件
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/markdown',
            as_attachment=True,
            download_name=f'export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        client.close()


if __name__ == '__main__':
    print("=" * 60)
    print("  共享CFO - Web查询监控工具")
    print("=" * 60)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    print()

    app.run(host='0.0.0.0', port=5000, debug=True)
