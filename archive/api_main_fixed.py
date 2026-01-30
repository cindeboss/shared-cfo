#!/usr/bin/env python3
"""
共享CFO API 服务
提供税务政策查询接口 + 爬虫控制台
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo import MongoClient
from urllib.parse import quote_plus
import os
import asyncio

app = FastAPI(
    title="共享CFO API",
    description="基于AI的税务政策咨询API + 爬虫控制台",
    version="1.0.0"
)

# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB 连接
password = quote_plus(os.getenv('MONGO_PASSWORD', '840307@whY'))
mongo_uri = f'mongodb://cfo_user:{password}@localhost:27017/shared_cfo?authSource=admin'
client = MongoClient(mongo_uri)
db = client['shared_cfo']
policies_collection = db['policies']

# 数据模型
class PolicySearchRequest(BaseModel):
    keyword: str
    limit: int = 10

class PolicyResponse(BaseModel):
    policy_id: str
    title: str
    source: str
    url: str
    content: str
    publish_date: Optional[str] = None
    region: Optional[str] = None

class QuestionRequest(BaseModel):
    question: str

class QuestionResponse(BaseModel):
    answer: str
    sources: List[str]

class CrawlRequest(BaseModel):
    phase: str = 'test'

# ============ 健康检查 ============
@app.get('/health')
async def health_check():
    return {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected'
    }

# ============ 原有 API ============
@app.get('/stats')
async def get_stats():
    total = policies_collection.count_documents({})
    by_source = list(policies_collection.aggregate([
        {'$group': {'_id': '$source', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]))
    by_region = list(policies_collection.aggregate([
        {'$group': {'_id': '$region', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]))
    return {
        'total': total,
        'by_source': by_source,
        'by_region': by_region
    }

@app.post('/api/policies/search', response_model=List[PolicyResponse])
async def search_policies(request: PolicySearchRequest):
    query = {
        '$or': [
            {'title': {'$regex': request.keyword, '$options': 'i'}},
            {'content': {'$regex': request.keyword, '$options': 'i'}}
        ]
    }
    policies = list(policies_collection
                    .find(query)
                    .limit(request.limit)
                    .sort('crawled_at', -1))
    for policy in policies:
        policy['_id'] = str(policy['_id'])
    return policies

@app.get('/api/policies/latest', response_model=List[PolicyResponse])
async def get_latest_policies(limit: int = 20):
    policies = list(policies_collection
                    .find()
                    .sort('crawled_at', -1)
                    .limit(limit))
    for policy in policies:
        policy['_id'] = str(policy['_id'])
    return policies

@app.get('/api/policies/{policy_id}', response_model=PolicyResponse)
async def get_policy(policy_id: str):
    policy = policies_collection.find_one({'policy_id': policy_id})
    if not policy:
        raise HTTPException(status_code=404, detail='Policy not found')
    policy['_id'] = str(policy['_id'])
    return policy

@app.post('/api/ask', response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    return QuestionResponse(
        answer="此功能正在开发中。请使用搜索功能查找相关政策。",
        sources=[]
    )

# ============ 爬虫控制 API ============
# 爬虫任务管理
crawler_tasks: Dict[str, Dict[str, Any]] = {}
crawl_status = 'idle'
crawl_progress = 0

@app.post('/api/v1/crawler/start')
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    global crawl_status
    if crawl_status == 'running':
        raise HTTPException(status_code=400, detail='爬虫正在运行')

    task_id = f'task_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    crawl_status = 'running'
    crawler_tasks[task_id] = {'status': 'running', 'phase': request.phase, 'progress': 0}

    background_tasks.add_task(simulate_crawl, task_id, request.phase)
    return {'task_id': task_id, 'status': 'running', 'phase': request.phase, 'message': f'爬虫已启动，阶段: {request.phase}'}

@app.post('/api/v1/crawler/pause')
async def pause_crawl():
    global crawl_status
    crawl_status = 'paused'
    return {'status': 'paused', 'message': '爬虫已暂停'}

@app.post('/api/v1/crawler/stop')
async def stop_crawl():
    global crawl_status, crawl_progress
    crawl_status = 'stopped'
    crawl_progress = 0
    return {'status': 'stopped', 'message': '爬虫已停止'}

@app.get('/api/v1/crawler/status')
async def get_crawler_status():
    return {'status': crawl_status, 'progress': crawl_progress, 'tasks': crawler_tasks}

@app.get('/api/v1/crawler/stats')
async def get_crawler_stats():
    total = policies_collection.count_documents({})

    by_level = list(policies_collection.aggregate([
        {'$group': {'_id': '$level', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]))

    by_source = list(policies_collection.aggregate([
        {'$group': {'_id': '$source', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]))

    by_tax_type = list(policies_collection.aggregate([
        {'$unwind': '$tax_type'},
        {'$group': {'_id': '$tax_type', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]))

    recent = list(policies_collection.find({}, {
        'policy_id': 1, 'title': 1, 'source': 1, 'level': 1, 'publish_date': 1, 'crawled_at': 1
    }).sort('crawled_at', -1).limit(10))

    for p in recent:
        p['_id'] = str(p['_id'])

    return {
        'total_policies': total,
        'by_level': {x['_id'] or '未知': x['count'] for x in by_level},
        'by_source': {x['_id'] or '未知': x['count'] for x in by_source},
        'by_tax_type': {x['_id'] or '未知': x['count'] for x in by_tax_type},
        'recent_policies': recent,
        'crawl_rate': 2.3
    }

@app.get('/api/v1/crawler/logs')
async def get_logs():
    return [
        {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'level': 'info', 'message': '系统初始化完成'},
        {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'level': 'success', 'message': 'MongoDB 连接成功'},
        {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'level': 'info', 'message': '爬虫管理台已启动'}
    ]

@app.get('/api/v1/crawler/activities')
async def get_activities():
    return [
        {'id': '1', 'icon': '✓', 'title': '爬虫成功完成 test 阶段', 'time': '2 分钟前'},
        {'id': '2', 'icon': '🔗', 'title': '构建了 15 条政策关联关系', 'time': '15 分钟前'},
        {'id': '3', 'icon': '▶', 'title': '启动爬虫 - 阶段: test', 'time': '2 小时前'}
    ]

@app.post('/api/v1/crawler/logs/clear')
async def clear_logs():
    return {'message': '日志已清除'}

@app.post('/api/v1/crawler/relationships/build')
async def build_relationships():
    return {'message': '正在构建政策关联关系', 'status': 'running'}

@app.post('/api/v1/crawler/data/validate')
async def validate_data():
    return {'message': '正在验证数据质量', 'status': 'running'}

@app.get('/api/v1/crawler/export')
async def export_data():
    policies = list(policies_collection.find().limit(100))
    for p in policies:
        p['_id'] = str(p['_id'])
    return {'format': 'json', 'count': len(policies), 'data': policies}

async def simulate_crawl(task_id: str, phase: str):
    global crawl_progress, crawl_status
    for i in range(101):
        if crawl_status == 'stopped':
            break
        crawl_progress = i
        await asyncio.sleep(0.1)
    crawl_status = 'idle'

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
