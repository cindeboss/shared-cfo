"""
Qdrant向量数据库连接模块
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Any, Optional
from ..config import settings
from loguru import logger


class QdrantDB:
    """Qdrant向量数据库客户端"""

    client: Optional[QdrantClient] = None

    async def connect(self):
        """连接Qdrant"""
        if self.client:
            return

        try:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.QDRANT_API_KEY,
            )

            # 检查集合是否存在，不存在则创建
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if settings.QDRANT_COLLECTION not in collection_names:
                self.create_collection(settings.QDRANT_COLLECTION)

            logger.info(f"Qdrant连接成功: {settings.QDRANT_COLLECTION}")

        except Exception as e:
            logger.error(f"Qdrant连接失败: {e}")
            raise

    async def disconnect(self):
        """断开连接"""
        if self.client:
            self.client.close()
            logger.info("Qdrant连接已关闭")

    def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1024,
    ):
        """创建集合"""
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"创建Qdrant集合: {collection_name}")

        except Exception as e:
            logger.warning(f"创建集合失败或已存在: {e}")

    def insert_points(
        self,
        collection_name: str,
        points: List[PointStruct],
    ):
        """插入向量点"""
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(f"插入{len(points)}个向量点")

        except Exception as e:
            logger.error(f"插入向量点失败: {e}")
            raise

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """向量搜索"""
        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
            )
            return results

        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []

    def get_point(self, collection_name: str, point_id: str) -> Optional[Dict]:
        """获取单个点"""
        try:
            result = self.client.retrieve(
                collection_name=collection_name,
                ids=[point_id],
            )
            if result:
                return result[0]
            return None

        except Exception as e:
            logger.error(f"获取向量点失败: {e}")
            return None

    def delete_collection(self, collection_name: str):
        """删除集合"""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"删除集合: {collection_name}")

        except Exception as e:
            logger.error(f"删除集合失败: {e}")


# 全局实例
qdrant = QdrantDB()


async def get_qdrant():
    """依赖注入：获取Qdrant实例"""
    if not qdrant.client:
        await qdrant.connect()
    return qdrant
