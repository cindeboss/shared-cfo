"""
爬虫编排器 - 协调所有爬虫的运行
按照《共享CFO - 爬虫模块需求文档 v3.0》的阶段目标执行
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from threading import Thread
import time

from .database_v2 import MongoDBConnectorV2
from .chinatax_crawler_v4 import ChinaTaxCrawler
from .crawler_12366_v2 import Crawler12366
from .relationship_builder import PolicyRelationshipBuilder
from .quality_validator import DataQualityValidator
from .data_models_v2 import CrawlTask
import uuid


logger = logging.getLogger("Orchestrator")


class CrawlerOrchestrator:
    """
    爬虫编排器

    按照计划的阶段目标执行爬取任务：
    - Phase 1: 建立基础法律框架 (4周)
    - Phase 2: 完善数据体系 (3周)
    - Phase 3: 持续增量更新
    """

    def __init__(self, db_connector: MongoDBConnectorV2 = None):
        self.db = db_connector or MongoDBConnectorV2()
        self.current_task_id = None
        self.is_running = False

        # 初始化组件
        self.relationship_builder = PolicyRelationshipBuilder(self.db)
        self.quality_validator = DataQualityValidator(self.db)

    def _create_task(self, source: str, source_type: str, total_count: int = 0) -> CrawlTask:
        """创建爬取任务"""
        task_id = f"{source_type}_{uuid.uuid4().hex[:8]}"
        return CrawlTask(
            task_id=task_id,
            source=source,
            source_type=source_type,
            status="running",
            start_time=datetime.now(),
            total_count=total_count
        )

    def _update_task_progress(self, task_id: str, success_count: int = 0,
                            failed_count: int = 0, status: str = "running"):
        """更新任务进度"""
        task = self.db.get_crawl_task(task_id)
        if task:
            total_success = task.get('success_count', 0) + success_count
            total_failed = task.get('failed_count', 0) + failed_count
            total = task.get('total_count', 0)

            progress = (total_success + total_failed) / total if total > 0 else 0

            self.db.update_crawl_task(task_id, {
                'success_count': total_success,
                'failed_count': total_failed,
                'progress': progress,
                'status': status
            })

    def run_phase1_week1(self) -> Dict[str, Any]:
        """
        Phase 1 - Week 1: 实体法框架
        - 爬取国家税务总局法律（5条）
        - 爬取国家税务总局行政法规（25条）
        - 爬取国家税务总局部门规章（500条）
        - 建立L1-L2关联关系
        """
        logger.info("Starting Phase 1 - Week 1: Entity Law Framework")

        results = {
            'phase': 'Phase1-Week1',
            'start_time': datetime.now().isoformat(),
            'tasks': []
        }

        crawler = ChinaTaxCrawler(self.db)

        try:
            # 任务1: 爬取法律
            task = self._create_task('国家税务总局', 'chinatax_law', 5)
            self.db.save_crawl_task(task)

            law_stats = crawler.crawl_laws(max_pages=1)
            self._update_task_progress(task.task_id, law_stats['success'],
                                     law_stats['failed'], 'completed')
            results['tasks'].append({'name': '法律', 'stats': law_stats})

            # 任务2: 爬取行政法规
            task = self._create_task('国家税务总局', 'chinatax_regulation', 25)
            self.db.save_crawl_task(task)

            reg_stats = crawler.crawl_regulations(max_pages=2)
            self._update_task_progress(task.task_id, reg_stats['success'],
                                     reg_stats['failed'], 'completed')
            results['tasks'].append({'name': '行政法规', 'stats': reg_stats})

            # 任务3: 爬取部门规章
            task = self._create_task('国家税务总局', 'chinatax_rule', 500)
            self.db.save_crawl_task(task)

            rule_stats = crawler.crawl_rules(max_pages=5)
            self._update_task_progress(task.task_id, rule_stats['success'],
                                     rule_stats['failed'], 'completed')
            results['tasks'].append({'name': '部门规章', 'stats': rule_stats})

            # 任务4: 建立关联关系
            rel_stats = self.relationship_builder.build_all_relationships(batch_size=100)
            results['tasks'].append({'name': '关联关系', 'stats': rel_stats})

            results['end_time'] = datetime.now().isoformat()
            results['total_success'] = sum(t['stats'].get('success', 0) for t in results['tasks'])

            logger.info(f"Phase 1 - Week 1 completed: {results}")

        finally:
            crawler.close()

        return results

    def run_phase1_week2(self) -> Dict[str, Any]:
        """
        Phase 1 - Week 2: 程序法+国际税收
        - 爬取税收征管法体系（3条）
        - 爬取征管相关规章（100条）
        - 爬取主要双边协定（20条）
        - 爬取12366热点问答（1,000条）
        """
        logger.info("Starting Phase 1 - Week 2: Procedural Law + International Tax")

        results = {
            'phase': 'Phase1-Week2',
            'start_time': datetime.now().isoformat(),
            'tasks': []
        }

        # 爬取征管程序相关规章
        crawler = ChinaTaxCrawler(self.db)

        try:
            # 使用关键词搜索爬取征管相关内容
            # 这里简化处理，实际可能需要专门的搜索功能
            task = self._create_task('国家税务总局', 'chinatax_procedure', 100)
            self.db.save_crawl_task(task)

            # 爬取规范性文件（包含征管相关）
            proc_stats = crawler.crawl_normative_docs(max_pages=3)
            self._update_task_progress(task.task_id, proc_stats['success'],
                                     proc_stats['failed'], 'completed')
            results['tasks'].append({'name': '征管规章', 'stats': proc_stats})

        finally:
            crawler.close()

        # 爬取12366热点问答
        qa_crawler = Crawler12366(self.db)

        try:
            task = self._create_task('12366平台', '12366_qa', 1000)
            self.db.save_crawl_task(task)

            qa_stats = qa_crawler.crawl_all_tax_types(max_per_type=50)
            self._update_task_progress(task.task_id, qa_stats['success'],
                                     qa_stats['failed'], 'completed')
            results['tasks'].append({'name': '热点问答', 'stats': qa_stats})

        finally:
            qa_crawler.close()

        # 建立关联关系
        rel_stats = self.relationship_builder.build_all_relationships(batch_size=100)
        results['tasks'].append({'name': '关联关系', 'stats': rel_stats})

        results['end_time'] = datetime.now().isoformat()
        results['total_success'] = sum(t['stats'].get('success', 0) for t in results['tasks'])

        logger.info(f"Phase 1 - Week 2 completed: {results}")

        return results

    def run_phase1_week3(self) -> Dict[str, Any]:
        """
        Phase 1 - Week 3: 扩充实体法数据
        - 爬取国家税务总局剩余部门规章（500条）
        - 爬取12366剩余热点问答（500条）
        - 爬取财政部财税文件（300条）
        - 完善关联关系
        """
        logger.info("Starting Phase 1 - Week 3: Expand Entity Law Data")

        results = {
            'phase': 'Phase1-Week3',
            'start_time': datetime.now().isoformat(),
            'tasks': []
        }

        crawler = ChinaTaxCrawler(self.db)

        try:
            # 爬取更多财税文件
            task = self._create_task('国家税务总局', 'chinatax_fiscal', 500)
            self.db.save_crawl_task(task)

            fiscal_stats = crawler.crawl_fiscal_docs(max_pages=10)
            self._update_task_progress(task.task_id, fiscal_stats['success'],
                                     fiscal_stats['failed'], 'completed')
            results['tasks'].append({'name': '财税文件', 'stats': fiscal_stats})

        finally:
            crawler.close()

        # 爬取更多12366问答
        qa_crawler = Crawler12366(self.db)

        try:
            task = self._create_task('12366平台', '12366_qa_more', 500)
            self.db.save_crawl_task(task)

            qa_stats = qa_crawler.crawl_all_tax_types(max_per_type=30)
            self._update_task_progress(task.task_id, qa_stats['success'],
                                     qa_stats['failed'], 'completed')
            results['tasks'].append({'name': '热点问答', 'stats': qa_stats})

        finally:
            qa_crawler.close()

        # 完善关联关系
        rel_stats = self.relationship_builder.build_all_relationships(batch_size=100)
        results['tasks'].append({'name': '关联关系', 'stats': rel_stats})

        results['end_time'] = datetime.now().isoformat()
        results['total_success'] = sum(t['stats'].get('success', 0) for t in results['tasks'])

        logger.info(f"Phase 1 - Week 3 completed: {results}")

        return results

    def run_phase1_complete(self) -> Dict[str, Any]:
        """
        运行完整的Phase 1 (4周)
        """
        logger.info("Starting Phase 1 Complete (4 weeks)")

        all_results = {
            'phase': 'Phase1-Complete',
            'start_time': datetime.now().isoformat(),
            'weeks': {}
        }

        # Week 1
        all_results['weeks']['week1'] = self.run_phase1_week1()

        # Week 2
        all_results['weeks']['week2'] = self.run_phase1_week2()

        # Week 3
        all_results['weeks']['week3'] = self.run_phase1_week3()

        # 质量检查
        logger.info("Running quality validation")
        quality_report = self.quality_validator.validate_all()
        all_results['quality_report'] = quality_report

        all_results['end_time'] = datetime.now().isoformat()

        logger.info(f"Phase 1 Complete finished: {all_results}")

        return all_results

    def run_quick_test(self) -> Dict[str, Any]:
        """
        快速测试 - 爬取少量数据验证系统功能
        """
        logger.info("Running quick test")

        results = {
            'test': 'quick_test',
            'start_time': datetime.now().isoformat(),
            'tasks': []
        }

        # 爬取少量法律
        crawler = ChinaTaxCrawler(self.db)

        try:
            task = self._create_task('国家税务总局', 'test_law', 5)
            self.db.save_crawl_task(task)

            law_stats = crawler.crawl_laws(max_pages=1)
            self._update_task_progress(task.task_id, law_stats['success'],
                                     law_stats['failed'], 'completed')
            results['tasks'].append({'name': '法律测试', 'stats': law_stats})

        finally:
            crawler.close()

        # 爬取少量问答
        qa_crawler = Crawler12366(self.db)

        try:
            task = self._create_task('12366平台', 'test_qa', 5)
            self.db.save_crawl_task(task)

            qa_stats = qa_crawler.crawl_hot_questions('增值税', max_results=5)
            self._update_task_progress(task.task_id, qa_stats['success'],
                                     qa_stats['failed'], 'completed')
            results['tasks'].append({'name': '问答测试', 'stats': qa_stats})

        finally:
            qa_crawler.close()

        # 构建关联关系
        rel_stats = self.relationship_builder.build_all_relationships(batch_size=100)
        results['tasks'].append({'name': '关联关系', 'stats': rel_stats})

        # 获取数据统计
        stats = self.db.get_stats()
        results['final_stats'] = stats

        results['end_time'] = datetime.now().isoformat()

        logger.info(f"Quick test completed: {results}")

        return results

    def get_progress_report(self) -> Dict[str, Any]:
        """获取爬取进度报告"""
        stats = self.db.get_stats()
        quality_report = self.db.get_quality_report()
        recent_tasks = self.db.get_all_crawl_tasks()[:10]

        return {
            'timestamp': datetime.now().isoformat(),
            'data_stats': stats,
            'quality_report': {
                'total_policies': quality_report.total_policies,
                'by_level': quality_report.by_level,
                'by_category': quality_report.by_category,
                'overall_quality_level': quality_report.overall_quality_level,
                'issues': quality_report.issues
            },
            'recent_tasks': recent_tasks
        }


# 便捷函数
def run_crawl_phase(phase: str = 'test', db_connector: MongoDBConnectorV2 = None) -> Dict[str, Any]:
    """
    运行指定的爬取阶段

    Args:
        phase: 'test', 'week1', 'week2', 'week3', 'complete'
        db_connector: 数据库连接器
    """
    orchestrator = CrawlerOrchestrator(db_connector)

    try:
        if phase == 'test':
            return orchestrator.run_quick_test()
        elif phase == 'week1':
            return orchestrator.run_phase1_week1()
        elif phase == 'week2':
            return orchestrator.run_phase1_week2()
        elif phase == 'week3':
            return orchestrator.run_phase1_week3()
        elif phase == 'complete':
            return orchestrator.run_phase1_complete()
        else:
            return {'error': f'Unknown phase: {phase}'}
    finally:
        # 不关闭数据库连接，由调用者管理
        pass


def get_progress(db_connector: MongoDBConnectorV2 = None) -> Dict[str, Any]:
    """获取爬取进度"""
    orchestrator = CrawlerOrchestrator(db_connector)
    return orchestrator.get_progress_report()
