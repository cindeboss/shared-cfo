"""
政策字段提取模块
从政策文本中提取关键信息：文号、日期、有效期、文号等
"""
import re
from datetime import datetime
from typing import Optional, List, Tuple
from enum import Enum

from .policy_schema import PolicyLevel


class FieldType(Enum):
    """字段类型"""
    DOCUMENT_NUMBER = "document_number"       # 发文字号
    PUBLISH_DATE = "publish_date"           # 发布日期
    EFFECTIVE_DATE = "effective_date"       # 生效日期
    EXPIRY_DATE = "expiry_date"             # 失效日期
    TAX_TYPE = "tax_type"                   # 税种
    TARGET_TAXPAYER = "target_taxpayer"     # 适用对象
    AUTHORITY = "issuing_authority"         # 制定机关


class FieldExtractor:
    """字段提取器"""

    # 发文字号模式
    DOCUMENT_NUMBER_PATTERNS = [
        # 财政部文号
        r'财[政关税]\s*〔\[]?\s*(\d{4})\s*\]?\s*号',
        r'财[政关税]\s*〔\[]?\s*(\d{1,2})\s*\]?\s*号',
        # 税务总局文号
        r'税\s*总\s*发\s*〔\[]?\s*(\d{4})\s*\]?\s*号',
        r'税\s*总\s*〔\[]?\s*(\d{1,2})\s*\]?\s*号',
        r'国家税务总局公告\s*(\d{4})\s*年\s*第\s*(\d{1,3})\s*号',
        # 国务院令
        r'国务院令\s*第\s*([\d\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u4e03\u4ebf\u96f6]+)\s*号',
        # 部委令
        r'(财政部|国家税务总局|发展改革委)\s*令\s*第\s*([\d\u4e00\u4e8c\u4e09\u56db\u4e94\u4e03\u4ebf\u96f6]+)\s*号',
        # 一般公告格式
        r'(公告|通知)\s*(\d{4})\s*年\s*第?\s*(\d{1,3})\s*号',
    ]

    # 日期模式
    DATE_PATTERNS = [
        # 成文日期
        r'成文日期\s*[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
        # 发布日期
        r'发布日期\s*[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
        r'印发日期\s*[：:]\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
        # 文中日期
        r'(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日',
    ]

    # 有效期模式
    EXPIRY_PATTERNS = [
        # 执行期限
        r'执行期限\s*[：:]\s*(.*?)(?=。|；|\n|$)',
        # 自...起
        r'自\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日.*?起\s*(至|至\s*?)(\d{4})[年\-]?\s*(\d{1,2})?[月\-]?\s*(\d{1,2})?日?',
        # 截止日期
        r'(截止|有效期至|执行期至)\s*(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})日?',
        # 长期有效
        r'(长期|无限期|永久|长期有效)',
    ]

    # 制定机关模式
    AUTHORITY_PATTERNS = [
        (r'全国人民代表大会', PolicyLevel.LAW),
        (r'全国人大常委会', PolicyLevel.LAW),
        (r'国务院', PolicyLevel.REGULATION),
        (r'财政部\s*、?\s*税务总局', PolicyLevel.NORMATIVE),
        (r'财政部', PolicyLevel.RULE),
        (r'国家税务总局', PolicyLevel.RULE),
        (r'国家税务总局.*?税务局', PolicyLevel.GUIDANCE),
    ]

    # 税种模式
    TAX_TYPE_PATTERNS = {
        '增值税': r'增值税',
        '企业所得税': r'企业所得税',
        '个人所得税': r'个人所得税|个税',
        '印花税': r'印花税',
        '土地增值税': r'土地增值税|土增税',
        '房产税': r'房产税',
        '城镇土地使用税': r'城镇土地使用税',
        '城市维护建设税': r'城市维护建设税|城建税',
        '车船税': r'车船税',
        '车辆购置税': r'车辆购置税',
        '消费税': r'消费税',
        '资源税': r'资源税',
        '环境保护税': r'环境保护税|环保税',
    }

    # 文档类型模式
    DOCUMENT_TYPE_PATTERNS = {
        '法律': (r'中华人民共和国.*?法$', PolicyLevel.LAW),
        '实施条例': (r'实施条例$', PolicyLevel.REGULATION),
        '办法': (r'(?!.*?试行.*?办法)(.*?办法)$', PolicyLevel.RULE),
        '规定': (r'规定$', PolicyLevel.RULE),
        '细则': (r'细则$', PolicyLevel.RULE),
        '公告': (r'公告$', PolicyLevel.NORMATIVE),
        '通知': (r'通知$', PolicyLevel.NORMATIVE),
        '批复': (r'批复$', PolicyLevel.NORMATIVE),
        '解读': (r'解读$', PolicyLevel.INTERPRETATION),
        '答记者问': (r'答记者问$', PolicyLevel.INTERPRETATION),
    }

    def extract_document_number(self, text: str) -> Optional[str]:
        """提取发文字号"""
        if not text:
            return None

        for pattern in self.DOCUMENT_NUMBER_PATTERNS:
            match = re.search(pattern, text)
            if match:
                result = match.group(0)
                # 清理结果
                result = re.sub(r'\s+', '', result)
                result = result.replace('〔', '[').replace('〕', ']')
                return result.strip()

        return None

    def extract_dates(self, text: str) -> dict:
        """提取所有日期信息"""
        result = {
            'publish_date': None,
            'effective_date': None,
            'expiry_date': None,
        }

        if not text:
            return result

        for pattern in self.DATE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    # 处理中文日期
                    year = int(re.search(r'(\d{4})', match[0]).group(1))
                    month = int(re.search(r'(\d{1,2})', match[0] if len(match) > 1 else match[1]).group(1))
                    day = int(re.search(r'(\d{1,2})', match[2] if len(match) > 2 else match[2]).group(1))

                    date_obj = datetime(year, month, day)

                    # 根据关键词判断日期类型
                    context = text[text.find(match[0])-20:text.find(match[0])+20] if match[0] in text else ''
                    if '成文日期' in context or '发布日期' in context:
                        result['publish_date'] = date_obj
                    elif '生效' in context or '施行' in context:
                        result['effective_date'] = date_obj
                    elif not result['publish_date']:
                        result['publish_date'] = date_obj

                except (ValueError, AttributeError, IndexError):
                    continue

        # 提取有效期信息
        for pattern in self.EXPIRY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                expiry_text = match.group(0)

                # 处理长期有效
                if re.search(r'(长期|无限期|永久)', expiry_text):
                    result['expiry_date'] = None
                    result['validity_status'] = 'long_term'
                    continue

                # 处理截止日期
                date_match = re.search(r'(\d{4})[年\-](\d{1,2})[月\-]?\s*(\d{1,2})?日?', expiry_text)
                if date_match:
                    try:
                        year = int(date_match.group(1))
                        month = int(date_match.group(2)) if date_match.group(2) else 12
                        day = int(date_match.group(3)) if date_match.group(3) else 31
                        result['expiry_date'] = datetime(year, month, day)
                    except ValueError:
                        pass

                # 检查是否已过期
                if result['expiry_date'] and result['expiry_date'] < datetime.now():
                    result['validity_status'] = 'expired'
                elif result['effective_date'] and result['effective_date'] > datetime.now():
                    result['validity_status'] = 'future'
                else:
                    result['validity_status'] = 'valid'

                break

        # 如果没有提取到有效期，根据发布日期推断
        if result['publish_date'] and not result.get('validity_status'):
            # 一般政策有效期3-5年
            if result['publish_date'].year < datetime.now().year - 5:
                result['validity_status'] = 'possibly_expired'
            else:
                result['validity_status'] = 'valid'

        return result

    def determine_tax_type(self, title: str, content: str) -> List[str]:
        """判断税种"""
        tax_types = []
        combined_text = f"{title} {content}"

        for tax_name, pattern in self.TAX_TYPE_PATTERNS.items():
            if re.search(pattern, combined_text):
                if tax_name not in tax_types:
                    tax_types.append(tax_name)

        # 如果没有匹配到，设为"其他"
        if not tax_types:
            tax_types = ['其他']

        return tax_types

    def determine_authority(self, text: str, url: str = '') -> Tuple[str, str]:
        """判断制定机关和机关类型"""
        authority = "未知"
        authority_type = "未知"

        for pattern, level in self.AUTHORITY_PATTERNS:
            if re.search(pattern, text):
                authority = pattern
                break

        # 根据层级确定机关类型
        if '人大' in authority:
            authority_type = "立法机关"
        elif '国务院' in authority:
            authority_type = "行政机关"
        elif '财政部' in authority or '税务总局' in authority:
            authority_type = "行政机关"
        elif '税务局' in authority:
            authority_type = "地方机关"

        # 尝试从URL推断
        if not authority or authority == "未知":
            if 'chinatax.gov.cn' in url:
                authority = "国家税务总局"
                authority_type = "行政机关"
            elif 'beijing.chinatax.gov.cn' in url:
                authority = "北京市税务局"
                authority_type = "地方机关"
            elif 'shanghai.chinatax.gov.cn' in url:
                authority = "上海市税务局"
                authority_type = "地方机关"

        return authority, authority_type

    def determine_level(self, title: str, content: str) -> int:
        """判断政策层级"""
        level = determine_policy_level({
            'title': title,
            'content': content
        })
        return level.value

    def determine_document_type(self, title: str) -> tuple:
        """判断文档类型"""
        for doc_type, (pattern, level) in self.DOCUMENT_TYPE_PATTERNS.items():
            if re.search(pattern, title):
                return doc_type, level.value

        return "其他", PolicyLevel.NORMATIVE.value

    def extract_key_points(self, content: str) -> List[str]:
        """提取关键要点"""
        key_points = []

        if not content:
            return key_points

        # 尝试按条、款、项分割
        article_pattern = r'(第[一二三四五六七八九十百千\d]+[条款项])'
        articles = re.split(article_pattern, content)

        for article in articles:
            article = article.strip()
            if len(article) > 20 and len(article) < 500:
                key_points.append(article)

        # 如果没有找到条目，按段落分割
        if len(key_points) < 3:
            paragraphs = re.split(r'[。\n]{2,}', content)
            for para in paragraphs:
                para = para.strip()
                if len(para) > 50 and len(para) < 300:
                    key_points.append(para)

        # 限制数量
        return key_points[:10]

    def extract_all_fields(self, title: str, content: str, url: str, source: str) -> dict:
        """提取所有字段"""
        result = {
            'title': title,
            'content': content,
            'url': url,
            'source': source,
        }

        # 1. 提取发文字号
        result['document_number'] = self.extract_document_number(content)

        # 2. 提取日期
        dates = self.extract_dates(f"{title} {content}")
        result.update(dates)

        # 3. 判断税种
        result['tax_type'] = self.determine_tax_type(title, content)

        # 4. 判断制定机关
        authority, authority_type = self.determine_authority(content, url)
        result['issuing_authority'] = authority
        result['authority_type'] = authority_type

        # 5. 判断层级
        result['policy_level'] = self.determine_level(title, content)

        # 6. 判断文档类型
        doc_type, level = self.determine_document_type(title)
        result['document_type'] = doc_type

        # 7. 提取关键要点
        result['key_points'] = self.extract_key_points(content)

        # 8. 内容长度
        result['content_length'] = len(content)

        # 9. 质量分数
        result['quality_score'] = calculate_quality_score(result)

        # 10. 质量等级
        result['quality_level'] = determine_quality_level(result['quality_score'])

        return result


# ==================== 辅助函数 ====================

def calculate_quality_score(doc: dict) -> int:
    """计算质量分数"""
    from .policy_schema import calculate_quality_score as calc
    return calc(doc)


def determine_quality_level(score: int) -> int:
    """确定质量等级"""
    from .policy_schema import determine_quality_level as det
    return det(score)


def determine_policy_level(doc: dict) -> PolicyLevel:
    """判断政策层级"""
    from .policy_schema import determine_policy_level as det
    return det(doc)


# 创建全局实例
field_extractor = FieldExtractor()
