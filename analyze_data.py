from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['shared_cfo']
coll = db['policies']

print('=' * 60)
print('ECS MongoDB 数据分析报告')
print('=' * 60)
print()

# 总数据量
total = coll.count_documents({})
print(f'总数据量: {total} 条')
print()

# 按层级统计
print('按层级统计:')
for level in ['L1', 'L2', 'L3', 'L4', 'L5', 'L6']:
    count = coll.count_documents({'document_level': level})
    if count > 0:
        print(f'  {level}: {count} 条')
print()

# 按类型统计
print('按类型统计:')
for doc_type in ['法律', '行政法规', '部门规章', '规范性文件', '政策解读']:
    count = coll.count_documents({'document_type': doc_type})
    if count > 0:
        print(f'  {doc_type}: {count} 条')
print()

# 有效数据详情
print('有效法律和行政法规:')
print('-' * 60)

invalid_titles = ['测试', '14', '税务部门规章']
valid_count = 0

for doc in coll.find({}).sort('crawled_at', -1):
    title = doc.get('title', '')
    is_valid = not any(inv in title for inv in invalid_titles)

    if is_valid:
        content_len = len(doc.get('content', ''))
        print(f"[{doc['document_level']}] {title}")
        print(f"  类型: {doc.get('document_type', 'N/A')}")
        tax_types = doc.get('tax_type', [])
        print(f"  税种: {', '.join(tax_types) if tax_types else 'N/A'}")
        print(f"  内容长度: {content_len} 字符")
        if content_len > 0:
            preview = doc.get('content', '')[:100].replace('\n', ' ')
            print(f"  预览: {preview}...")
        print()
        valid_count += 1

print('-' * 60)
print(f'有效数据: {valid_count} 条')
print(f'测试/无效数据: {total - valid_count} 条')
