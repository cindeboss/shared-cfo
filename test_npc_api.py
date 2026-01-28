"""
测试国家法律法规数据库API
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.npc_database import NPCDatabaseAPI
from data_pipeline.pipeline import DataAcquisitionPipeline


async def test_api_connection():
    """测试API连接"""
    print("=" * 60)
    print("测试国家法律法规数据库API连接")
    print("=" * 60)
    
    api = NPCDatabaseAPI()
    
    try:
        # 测试获取法律列表
        print("\n[测试1] 获取法律列表...")
        laws = await api.get_laws(page=1, per_page=5)
        
        if laws:
            print(f"✓ 成功获取 {len(laws)} 条法律:")
            for law in laws[:3]:
                print(f"  - {law.get('title', 'Unknown')[:50]}")
        else:
            print("✗ 未获取到法律数据")
            return
        
        # 测试搜索具体法律
        print("\n[测试2] 搜索增值税法...")
        api_result = await api.get_law_by_name("增值税法")
        
        if api_result:
            print(f"✓ 找到增值税法")
            print(f"  标题: {api_result.get('title', '')}")
            print(f"  内容长度: {len(api_result.get('content', ''))} 字符")
            print(f"  来源: {api_result.get('source', '')}")
        else:
            print("✗ 未找到增值税法")
        
        # 测试批量获取
        print("\n[测试3] 批量获取法律...")
        pipeline = DataAcquisitionPipeline()
        
        test_laws = ["增值税法", "个人所得税法", "企业所得税法"]
        results = await pipeline.fetch_multiple_laws(test_laws)
        
        print(f"✓ 批量获取完成:")
        print(f"  成功: {results['success']} 条")
        print(f"  失败: {results['failed']} 条")
        print(f"  总计: {results['total']} 条")
        
        # 显示统计
        stats = pipeline.get_stats()
        print(f"\n[统计]")
        print(f"  API成功: {stats['api_success']} 条")
        print(f"  搜索成功: {stats['search_success']} 条")
        
        pipeline.close()
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api.close()


if __name__ == '__main__':
    asyncio.run(test_api_connection())
