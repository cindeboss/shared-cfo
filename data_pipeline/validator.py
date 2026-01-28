"""
数据质量校验器
验证获取的数据是否满足质量标准
"""

import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """数据质量校验器"""

    def check_completeness(self, data: Dict[str, Any]) -> bool:
        """
        完整性检查
        
        检查必需字段是否存在
        """
        required_fields = ['title', 'content', 'source']
        for field in required_fields:
            if not data.get(field):
                logger.warning(f"缺失必需字段: {field}")
                return False
        return True

    def check_content_quality(self, data: Dict[str, Any]) -> bool:
        """
        内容质量检查
        
        - 内容长度足够（>500字符）
        - 不包含页面导航元素
        - 包含条文格式
        """
        content = data.get('content', '')
        
        # 检查内容长度
        if len(content) < 500:
            logger.warning(f"内容过短: {len(content)} 字符")
            return False
        
        # 检查是否包含页面噪音
        noise_patterns = [
            '网站导航', '首页', '登录', '菜单', '-footer',
            '中国政府网', '中央人民政府'
        ]
        for pattern in noise_patterns:
            if pattern in content:
                logger.warning(f"包含页面噪音: {pattern}")
                return False
        
        # 检查条文格式
        article_pattern = r'第[一二三四五六七八九十百千零壹贰叁肆伍陆柒捌玖]+条'
        if not re.search(article_pattern, content):
            # 检查阿拉伯数字条文
            article_pattern_arabic = r'第\d+条'
            if not re.search(article_pattern_arabic, content):
                logger.warning("未发现条文格式")
                return False
        
        logger.info("内容质量检查通过")
        return True

    def check_source_authority(self, data: Dict[str, Any]) -> bool:
        """
        数据源权威性检查
        
        检查数据来源是否为权威官方源
        """
        authoritative_sources = [
            '全国人大', 'npc.gov.cn',
            '国务院', 'gov.cn',
            '国家税务总局', 'chinatax.gov.cn'
        ]
        
        source = data.get('source', '')
        url = data.get('url', '')
        
        # 检查来源或URL是否包含权威关键词
        for auth in authoritative_sources:
            if auth in source or auth in url:
                logger.info(f"数据源权威: {source}")
                return True
        
        logger.warning(f"数据源非权威: {source}")
        return False

    def validate(self, data: Dict[str, Any]) -> bool:
        """
        综合验证
        
        运行所有检查并返回结果
        """
        checks = [
            ('完整性', self.check_completeness(data)),
            ('内容质量', self.check_content_quality(data)),
            ('权威性', self.check_source_authority(data))
        ]
        
        all_passed = all(passed for _, passed in checks)
        
        # 计算质量分数
        score = sum(1 for _, passed in checks if passed)
        data['quality_score'] = score
        
        logger.info(f"验证结果: {score}/3 通过")
        return all_passed
