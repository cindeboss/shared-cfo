"""
健康检查路由
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
from ...database.mongo import mongo, get_mongo

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查"""
    mongo_connected = mongo.client is not None
    mongo_db = None

    if mongo_connected:
        try:
            # 测试数据库连接
            mongo_db = mongo.database.name if mongo.database else None
            if mongo_db:
                mongo.client.admin.command('ping')
        except:
            mongo_connected = False

    return {
        "status": "healthy" if mongo_connected else "degraded",
        "version": "1.0.0",
        "mongo_connected": mongo_connected,
        "mongo_database": mongo_db,
    }


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """获取系统统计信息"""
    stats = {
        "mongo_connected": mongo.client is not None,
    }

    if mongo.client and mongo.database:
        try:
            # 获取政策数据统计
            policies_collection = mongo.database.get_collection("policies")
            total_policies = policies_collection.count_documents({})
            stats["total_policies"] = total_policies

            # 按来源统计
            pipeline = [
                {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            by_source = list(policies_collection.aggregate(pipeline))
            stats["by_source"] = {item["_id"]: item["count"] for item in by_source}

        except Exception as e:
            stats["error"] = str(e)

    return stats
