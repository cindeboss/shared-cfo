"""
项目状态跟踪器
自动记录项目进度，每小时更新一次
支持项目启动时自动加载和记录状态
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger("ProjectTracker")


class ProjectStatusTracker:
    """项目状态跟踪器"""

    def __init__(self, project_root: str = None):
        if project_root is None:
            # 自动检测项目根目录
            current_path = Path(__file__).parent
            self.project_root = current_path.parent
        else:
            self.project_root = Path(project_root)

        # 状态文件路径
        self.status_file = self.project_root / "project_status.json"
        self.log_file = self.project_root / "project_progress.md"

        # 线程控制
        self._running = False
        self._timer_thread = None
        self._lock = threading.Lock()

        # 加载现有状态
        self.status = self._load_status()

        # 记录本次会话开始
        self._record_session_start()

    def _load_status(self) -> Dict[str, Any]:
        """加载现有状态"""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load status file: {e}")

        # 默认状态
        return {
            "project_name": "共享CFO - 爬虫模块",
            "created_at": datetime.now().isoformat(),
            "last_updated": None,
            "total_sessions": 0,
            "current_session": {
                "start_time": datetime.now().isoformat(),
                "tasks_completed": [],
                "files_created": [],
                "files_modified": [],
                "notes": []
            },
            "milestones": {
                "database_design": False,
                "base_crawler": False,
                "chinatax_crawler": False,
                "mof_crawler": False,
                "12366_crawler": False,
                "international_crawler": False,
                "provincial_crawlers": False,
                "relationship_builder": False,
                "quality_validator": False,
                "update_scheduler": False,
                "api_endpoints": False,
            },
            "data_stats": {
                "total_policies": 0,
                "by_level": {"L1": 0, "L2": 0, "L3": 0, "L4": 0},
                "by_category": {"实体税": 0, "程序税": 0, "国际税收": 0},
            },
            "issues": [],
            "next_steps": []
        }

    def _save_status(self):
        """保存状态到文件"""
        with self._lock:
            self.status["last_updated"] = datetime.now().isoformat()
            try:
                with open(self.status_file, 'w', encoding='utf-8') as f:
                    json.dump(self.status, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to save status: {e}")

    def _record_session_start(self):
        """记录会话开始"""
        session = self.status["current_session"]
        session["start_time"] = datetime.now().isoformat()

        # 写入进度日志
        self._append_to_log(f"\n## 会话开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 更新总会话数
        self.status["total_sessions"] = self.status.get("total_sessions", 0) + 1
        self._save_status()

        # 打印项目状态
        self._print_status()

    def _print_status(self):
        """打印项目状态"""
        print("\n" + "=" * 80)
        print("[共享CFO - 爬虫模块项目状态]")
        print("=" * 80)

        # 总体进度
        milestones = self.status.get("milestones", {})
        completed = sum(1 for v in milestones.values() if v)
        total = len(milestones)
        progress = (completed / total * 100) if total > 0 else 0

        print(f"\n[总体进度] {progress:.1f}% ({completed}/{total} 里程碑完成)")
        self._print_progress_bar(progress)

        # 里程碑状态
        print("\n[里程碑状态]:")
        milestone_names = {
            "database_design": "数据库设计",
            "base_crawler": "基础爬虫框架",
            "chinatax_crawler": "国家税务总局爬虫",
            "mof_crawler": "财政部爬虫",
            "12366_crawler": "12366平台爬虫",
            "international_crawler": "国际税收爬虫",
            "provincial_crawlers": "地方税务局爬虫",
            "relationship_builder": "政策关联构建器",
            "quality_validator": "数据质量验证器",
            "update_scheduler": "增量更新调度器",
            "api_endpoints": "API接口",
        }

        for key, name in milestone_names.items():
            status = "[完成]" if milestones.get(key, False) else "[待办]"
            print(f"  {status} {name}")

        # 数据统计
        stats = self.status.get("data_stats", {})
        total_policies = stats.get("total_policies", 0)
        print(f"\n[数据统计] 共 {total_policies} 条政策")

        by_level = stats.get("by_level", {})
        if by_level:
            print(f"  按层级: L1={by_level.get('L1', 0)}, L2={by_level.get('L2', 0)}, "
                  f"L3={by_level.get('L3', 0)}, L4={by_level.get('L4', 0)}")

        # 下一步
        next_steps = self.status.get("next_steps", [])
        if next_steps:
            print(f"\n[下一步计划]:")
            for step in next_steps[:5]:
                print(f"  - {step}")

        # 问题
        issues = self.status.get("issues", [])
        if issues:
            print(f"\n[待解决问题]:")
            for issue in issues[:3]:
                print(f"  - {issue}")

        print("\n" + "=" * 80 + "\n")

    def _print_progress_bar(self, progress: float, width: int = 40):
        """打印进度条"""
        filled = int(width * progress / 100)
        bar = "=" * filled + "-" * (width - filled)
        print(f"  [{bar}] {progress:.1f}%")

    def _append_to_log(self, content: str):
        """追加内容到进度日志"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")

    def _get_emoji(self, text: str) -> str:
        """根据文本返回对应的表情符号（如果支持的话）"""
        emoji_map = {
            'complete': '[OK]',
            'done': '[OK]',
            'success': '[OK]',
            'file': '[FILE]',
            'note': '[NOTE]',
            'warning': '[!]',
            'info': '[i]',
            'error': '[X]',
            'step': '->',
            'next': '->',
        }
        return emoji_map.get(text.lower(), '')

    def complete_task(self, task_name: str, details: str = ""):
        """标记任务完成"""
        with self._lock:
            session = self.status["current_session"]
            if task_name not in session.get("tasks_completed", []):
                session.setdefault("tasks_completed", []).append(task_name)

            # 如果是里程碑，更新里程碑状态
            if task_name in self.status.get("milestones", {}):
                self.status["milestones"][task_name] = True

            if details:
                self._append_to_log(f"[OK] 完成: {task_name}\n{details}\n")

            self._save_status()

    def create_file(self, file_path: str, description: str = ""):
        """记录创建文件"""
        with self._lock:
            session = self.status["current_session"]
            files = session.setdefault("files_created", [])
            if file_path not in files:
                files.append(file_path)

            if description:
                self._append_to_log(f"[FILE] 创建文件: {file_path}\n  {description}\n")

            self._save_status()

    def modify_file(self, file_path: str, description: str = ""):
        """记录修改文件"""
        with self._lock:
            session = self.status["current_session"]
            files = session.setdefault("files_modified", [])
            if file_path not in files:
                files.append(file_path)

            if description:
                self._append_to_log(f"[EDIT] 修改文件: {file_path}\n  {description}\n")

            self._save_status()

    def add_note(self, note: str):
        """添加笔记"""
        with self._lock:
            session = self.status["current_session"]
            session.setdefault("notes", []).append({
                "time": datetime.now().isoformat(),
                "content": note
            })

            self._append_to_log(f"[NOTE] {note}\n")
            self._save_status()

    def update_data_stats(self, stats: Dict[str, Any]):
        """更新数据统计"""
        with self._lock:
            self.status["data_stats"] = stats
            self._save_status()

    def add_issue(self, issue: str):
        """添加问题"""
        with self._lock:
            issues = self.status.setdefault("issues", [])
            if issue not in issues:
                issues.append(issue)
            self._save_status()

    def resolve_issue(self, issue: str):
        """解决问题"""
        with self._lock:
            issues = self.status.get("issues", [])
            if issue in issues:
                issues.remove(issue)
            self._save_status()

    def set_next_steps(self, steps: List[str]):
        """设置下一步计划"""
        with self._lock:
            self.status["next_steps"] = steps
            self._save_status()

    def start_auto_save(self, interval_minutes: int = 60):
        """启动自动保存"""
        if self._running:
            return

        self._running = True

        def auto_save_loop():
            while self._running:
                time.sleep(interval_minutes * 60)
                if self._running:
                    self._auto_save_snapshot()

        self._timer_thread = threading.Thread(target=auto_save_loop, daemon=True)
        self._timer_thread.start()
        logger.info(f"Auto-save started (interval: {interval_minutes} minutes)")

    def _auto_save_snapshot(self):
        """自动保存快照"""
        with self._lock:
            snapshot_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            snapshot = {
                "timestamp": snapshot_time,
                "session_tasks": len(self.status["current_session"].get("tasks_completed", [])),
                "session_files_created": len(self.status["current_session"].get("files_created", [])),
                "session_files_modified": len(self.status["current_session"].get("files_modified", [])),
            }

            self._append_to_log(f"\n### 自动保存快照 - {snapshot_time}\n")
            self._append_to_log(f"- 本会话完成任务: {snapshot['session_tasks']}\n")
            self._append_to_log(f"- 创建文件: {snapshot['session_files_created']}\n")
            self._append_to_log(f"- 修改文件: {snapshot['session_files_modified']}\n")
            self._append_to_log(f"- 总数据量: {self.status['data_stats']['total_policies']} 条\n")

            logger.info(f"Auto-save snapshot completed at {snapshot_time}")

    def stop_auto_save(self):
        """停止自动保存"""
        self._running = False
        if self._timer_thread:
            self._timer_thread.join(timeout=5)
        logger.info("Auto-save stopped")

    def export_progress_report(self) -> str:
        """导出进度报告"""
        report = []
        report.append("# 共享CFO - 爬虫模块项目进度报告\n")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append("---\n")

        # 总体进度
        milestones = self.status.get("milestones", {})
        completed = sum(1 for v in milestones.values() if v)
        total = len(milestones)
        progress = (completed / total * 100) if total > 0 else 0

        report.append(f"## 总体进度: {progress:.1f}%\n\n")

        # 里程碑详情
        report.append("## 里程碑状态\n\n")
        milestone_names = {
            "database_design": "数据库设计",
            "base_crawler": "基础爬虫框架",
            "chinatax_crawler": "国家税务总局爬虫",
            "mof_crawler": "财政部爬虫",
            "12366_crawler": "12366平台爬虫",
            "international_crawler": "国际税收爬虫",
            "provincial_crawlers": "地方税务局爬虫",
            "relationship_builder": "政策关联构建器",
            "quality_validator": "数据质量验证器",
            "update_scheduler": "增量更新调度器",
            "api_endpoints": "API接口",
        }

        for key, name in milestone_names.items():
            status = "✅ 已完成" if milestones.get(key, False) else "⏳ 进行中"
            report.append(f"- {status} {name}\n")

        # 数据统计
        report.append("\n## 数据统计\n\n")
        stats = self.status.get("data_stats", {})
        report.append(f"- 总政策数: {stats.get('total_policies', 0)} 条\n")
        by_level = stats.get("by_level", {})
        report.append(f"- L1层级: {by_level.get('L1', 0)} 条\n")
        report.append(f"- L2层级: {by_level.get('L2', 0)} 条\n")
        report.append(f"- L3层级: {by_level.get('L3', 0)} 条\n")
        report.append(f"- L4层级: {by_level.get('L4', 0)} 条\n")

        # 下一步
        report.append("\n## 下一步计划\n\n")
        for step in self.status.get("next_steps", []):
            report.append(f"- {step}\n")

        # 问题
        if self.status.get("issues"):
            report.append("\n## 待解决问题\n\n")
            for issue in self.status.get("issues", []):
                report.append(f"- {issue}\n")

        # 本次会话
        session = self.status.get("current_session", {})
        report.append(f"\n## 当前会话\n\n")
        report.append(f"- 开始时间: {session.get('start_time', 'N/A')}\n")
        report.append(f"- 完成任务: {len(session.get('tasks_completed', []))} 个\n")
        report.append(f"- 创建文件: {len(session.get('files_created', []))} 个\n")
        report.append(f"- 修改文件: {len(session.get('files_modified', []))} 个\n")

        return "".join(report)


# 全局实例
_tracker = None


def get_tracker() -> ProjectStatusTracker:
    """获取项目跟踪器实例"""
    global _tracker
    if _tracker is None:
        # 获取项目根目录
        import os
        current_file = Path(__file__)
        project_root = current_file.parent.parent
        _tracker = ProjectStatusTracker(str(project_root))
        _tracker.start_auto_save(interval_minutes=60)
    return _tracker


def on_project_enter():
    """项目启动时调用"""
    tracker = get_tracker()
    tracker.add_note("项目会话开始，自动记录已启用")
    return tracker


if __name__ == "__main__":
    # 测试代码
    tracker = get_tracker()

    # 模拟一些操作
    tracker.complete_task("database_design", "完成数据库schema设计")
    tracker.create_file("data_models_v2.py", "数据模型定义文件")
    tracker.add_note("开始实现国家税务总局爬虫")

    # 导出报告
    print(tracker.export_progress_report())
