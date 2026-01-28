"""
爬虫控制 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import asyncio
import logging

from ...database.mongo import mongo

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 数据模型 ====================

class CrawlStartRequest(BaseModel):
    """启动爬虫请求"""
    phase: str = "test"  # test, week1, week2, week3, complete
    limit: Optional[int] = None


class CrawlResponse(BaseModel):
    """爬虫响应"""
    task_id: str
    status: str
    message: str
    phase: str


class CrawlerStats(BaseModel):
    """爬虫统计"""
    total_policies: int
    by_level: Dict[str, int]
    by_source: Dict[str, int]
    by_tax_type: Dict[str, int]
    recent_policies: List[Dict[str, Any]]
    crawl_rate: float


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: str
    level: str
    message: str


class ActivityItem(BaseModel):
    """活动项"""
    id: str
    icon: str
    title: str
    time: str


# ==================== 爬虫任务管理 ====================

class CrawlerTaskManager:
    """爬虫任务管理器"""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.current_task: Optional[str] = None
        self.crawl_status = "idle"  # idle, running, paused, stopped
        self.progress = 0

    def create_task(self, phase: str) -> str:
        """创建新任务"""
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.tasks[task_id] = {
            "id": task_id,
            "phase": phase,
            "status": "pending",
            "created_at": datetime.now(),
            "progress": 0,
            "policies_crawled": 0,
        }
        return task_id

    def start_task(self, task_id: str):
        """启动任务"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "running"
            self.tasks[task_id]["started_at"] = datetime.now()
            self.current_task = task_id
            self.crawl_status = "running"

    def pause_task(self, task_id: str):
        """暂停任务"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "paused"
            self.crawl_status = "paused"

    def stop_task(self, task_id: str):
        """停止任务"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "stopped"
            self.tasks[task_id]["stopped_at"] = datetime.now()
            self.crawl_status = "stopped"

    def complete_task(self, task_id: str):
        """完成任务"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["completed_at"] = datetime.now()
            self.crawl_status = "idle"
            self.current_task = None

    def update_progress(self, task_id: str, progress: int, policies_crawled: int):
        """更新任务进度"""
        if task_id in self.tasks:
            self.tasks[task_id]["progress"] = progress
            self.tasks[task_id]["policies_crawled"] = policies_crawled
            self.progress = progress


# 全局任务管理器
task_manager = CrawlerTaskManager()

# 模拟日志存储
log_entries: List[LogEntry] = [
    LogEntry(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level="info", message="系统初始化完成"),
    LogEntry(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level="info", message="连接到 MongoDB: localhost:27017"),
    LogEntry(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level="success", message="数据库连接成功"),
]

# 模拟活动列表
activities: List[ActivityItem] = [
    ActivityItem(id="1", icon="✓", title="爬虫成功完成 test 阶段", time="2 分钟前"),
    ActivityItem(id="2", icon="🔗", title="构建了 15 条政策关联关系", time="15 分钟前"),
    ActivityItem(id="3", icon="⚠", title="检测到 3 条重复政策", time="1 小时前"),
    ActivityItem(id="4", icon="▶", title="启动爬虫 - 阶段: test", time="2 小时前"),
]


# ==================== API 端点 ====================

@router.get("/stats", response_model=CrawlerStats)
async def get_crawler_stats() -> CrawlerStats:
    """获取爬虫统计数据"""
    try:
        if not mongo.client or not mongo.database:
            raise HTTPException(status_code=503, detail="数据库未连接")

        policies_collection = mongo.database.get_collection("policies")

        # 总政策数
        total_policies = policies_collection.count_documents({})

        # 按层级统计
        pipeline_level = [
            {"$group": {"_id": "$level", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_level_raw = list(policies_collection.aggregate(pipeline_level))
        by_level = {item["_id"] or "未知": item["count"] for item in by_level_raw}

        # 按来源统计
        pipeline_source = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_source_raw = list(policies_collection.aggregate(pipeline_source))
        by_source = {item["_id"] or "未知": item["count"] for item in by_source_raw}

        # 按税种统计
        pipeline_tax = [
            {"$unwind": "$tax_type"},
            {"$group": {"_id": "$tax_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_tax_type_raw = list(policies_collection.aggregate(pipeline_tax))
        by_tax_type = {item["_id"] or "未知": item["count"] for item in by_tax_type_raw}

        # 最近的政策
        recent_policies = list(
            policies_collection
            .find({}, {"title": 1, "source": 1, "level": 1, "publish_date": 1, "crawled_at": 1})
            .sort("crawled_at", -1)
            .limit(10)
        )

        # 转换 ObjectId
        for policy in recent_policies:
            policy["_id"] = str(policy["_id"])

        return CrawlerStats(
            total_policies=total_policies,
            by_level=by_level,
            by_source=by_source,
            by_tax_type=by_tax_type,
            recent_policies=recent_policies,
            crawl_rate=2.3  # 可以从任务历史计算
        )

    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=CrawlResponse)
async def start_crawl(request: CrawlStartRequest, background_tasks: BackgroundTasks) -> CrawlResponse:
    """启动爬虫"""
    try:
        if task_manager.crawl_status == "running":
            raise HTTPException(status_code=400, detail="爬虫正在运行中")

        task_id = task_manager.create_task(request.phase)
        task_manager.start_task(task_id)

        # 添加日志
        add_log(f"启动爬虫 - 阶段: {request.phase}", "info")
        add_activity("▶", f"启动爬虫 - 阶段: {request.phase}")

        # 后台执行爬虫任务（模拟）
        background_tasks.add_task(
            simulate_crawl_task,
            task_id,
            request.phase
        )

        return CrawlResponse(
            task_id=task_id,
            status="running",
            message=f"爬虫已启动，阶段: {request.phase}",
            phase=request.phase
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动爬虫失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause")
async def pause_crawl() -> Dict[str, Any]:
    """暂停爬虫"""
    if task_manager.current_task:
        task_manager.pause_task(task_manager.current_task)
        add_log("爬虫已暂停", "warning")
        add_activity("⏸", "暂停爬虫")
        return {"status": "paused", "message": "爬虫已暂停"}
    raise HTTPException(status_code=400, detail="没有运行中的爬虫任务")


@router.post("/stop")
async def stop_crawl() -> Dict[str, Any]:
    """停止爬虫"""
    if task_manager.current_task:
        task_manager.stop_task(task_manager.current_task)
        add_log("爬虫已停止", "error")
        add_activity("⏹", "停止爬虫")
        return {"status": "stopped", "message": "爬虫已停止"}
    raise HTTPException(status_code=400, detail="没有运行中的爬虫任务")


@router.get("/status")
async def get_crawler_status() -> Dict[str, Any]:
    """获取爬虫状态"""
    return {
        "status": task_manager.crawl_status,
        "current_task": task_manager.current_task,
        "progress": task_manager.progress,
        "tasks": list(task_manager.tasks.values())
    }


@router.get("/logs", response_model=List[LogEntry])
async def get_logs(limit: int = 50) -> List[LogEntry]:
    """获取日志"""
    return log_entries[-limit:]


@router.post("/logs/clear")
async def clear_logs() -> Dict[str, str]:
    """清除日志"""
    log_entries.clear()
    add_log("日志已清除", "info")
    return {"message": "日志已清除"}


@router.get("/activities", response_model=List[ActivityItem])
async def get_activities(limit: int = 10) -> List[ActivityItem]:
    """获取活动列表"""
    return activities[-limit:]


@router.get("/policies/recent")
async def get_recent_policies(limit: int = 10) -> Dict[str, Any]:
    """获取最近的政策"""
    try:
        if not mongo.client or not mongo.database:
            raise HTTPException(status_code=503, detail="数据库未连接")

        policies_collection = mongo.database.get_collection("policies")

        policies = list(
            policies_collection
            .find({}, {
                "policy_id": 1,
                "title": 1,
                "source": 1,
                "level": 1,
                "publish_date": 1,
                "document_number": 1,
                "crawled_at": 1
            })
            .sort("crawled_at", -1)
            .limit(limit)
        )

        # 转换 ObjectId
        for policy in policies:
            policy["_id"] = str(policy["_id"])

        return {
            "total": len(policies),
            "policies": policies
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最近政策失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relationships/build")
async def build_relationships(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """构建政策关联关系"""
    add_log("开始构建政策关联关系...", "info")
    add_activity("🔗", "构建政策关联关系")

    # 后台任务（这里可以调用 relationship_builder.py）
    background_tasks.add_task(simulate_relationship_build)

    return {"message": "正在构建政策关联关系", "status": "running"}


@router.post("/data/validate")
async def validate_data(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """验证数据质量"""
    add_log("开始数据质量验证...", "info")
    add_activity("✓", "验证数据质量")

    # 后台任务（这里可以调用 quality_validator.py）
    background_tasks.add_task(simulate_data_validation)

    return {"message": "正在验证数据质量", "status": "running"}


@router.get("/export")
async def export_data(format: str = "json") -> Dict[str, Any]:
    """导出数据"""
    try:
        if not mongo.client or not mongo.database:
            raise HTTPException(status_code=503, detail="数据库未连接")

        policies_collection = mongo.database.get_collection("policies")

        policies = list(
            policies_collection
            .find({})
            .limit(1000)  # 限制导出数量
        )

        # 转换 ObjectId
        for policy in policies:
            policy["_id"] = str(policy["_id"])

        add_log(f"数据导出完成！格式: {format}, 数量: {len(policies)}", "success")
        add_activity("📥", f"导出数据 - {len(policies)} 条")

        return {
            "format": format,
            "count": len(policies),
            "data": policies
        }

    except Exception as e:
        logger.error(f"导出数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 辅助函数 ====================

def add_log(message: str, level: str = "info"):
    """添加日志"""
    log_entries.append(
        LogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            level=level,
            message=message
        )
    )
    # 限制日志数量
    if len(log_entries) > 500:
        log_entries.pop(0)


def add_activity(icon: str, title: str):
    """添加活动"""
    activity_id = str(len(activities) + 1)
    activities.append(
        ActivityItem(
            id=activity_id,
            icon=icon,
            title=title,
            time="刚刚"
        )
    )
    # 限制活动数量
    if len(activities) > 50:
        activities.pop(0)


async def simulate_crawl_task(task_id: str, phase: str):
    """模拟爬虫任务（实际应该调用 orchestrator.py）"""
    try:
        total_steps = 100
        for i in range(total_steps + 1):
            if task_manager.tasks[task_id]["status"] == "stopped":
                break

            if task_manager.tasks[task_id]["status"] == "paused":
                await asyncio.sleep(1)
                continue

            progress = int((i / total_steps) * 100)
            task_manager.update_progress(task_id, progress, i)

            if i % 20 == 0 and i > 0:
                add_log(f"爬取进度: {progress}%, 已获取 {i} 条政策", "info")

            await asyncio.sleep(0.5)  # 模拟爬取延迟

        task_manager.complete_task(task_id)
        add_log(f"爬虫任务完成！阶段: {phase}, 总计: {total_steps} 条", "success")
        add_activity("✓", f"爬虫成功完成 {phase} 阶段")

    except Exception as e:
        logger.error(f"爬虫任务执行失败: {e}")
        add_log(f"爬虫任务失败: {e}", "error")


async def simulate_relationship_build():
    """模拟构建关联关系"""
    await asyncio.sleep(3)
    add_log("关联关系构建完成！处理了 15 条政策", "success")
    add_activity("✓", "关联关系构建完成")


async def simulate_data_validation():
    """模拟数据验证"""
    await asyncio.sleep(2)
    add_log("数据验证完成！发现 3 个问题", "warning")
    add_activity("✓", "数据验证完成")
