"""
MongoDB数据库连接模块
"""
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from ..config import settings
from loguru import logger


class MongoDB:
    """MongoDB异步客户端"""

    client: Optional[AsyncIOMotorClient] = None
    database = None

    async def connect(self):
        """连接数据库"""
        if self.client:
            return

        try:
            self.client = AsyncIOMotorClient(settings.mongo_url)
            self.database = self.client[settings.MONGO_DATABASE]

            # 测试连接
            await self.client.admin.command('ping')
            logger.info(f"MongoDB连接成功: {settings.MONGO_DATABASE}")

        except Exception as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise

    async def disconnect(self):
        """断开连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB连接已关闭")

    def get_collection(self, name: str):
        """获取集合"""
        if not self.database:
            raise RuntimeError("数据库未连接，请先调用connect()")
        return self.database[name]


# 全局实例
mongo = MongoDB()


async def get_mongo():
    """依赖注入：获取MongoDB实例"""
    if not mongo.database:
        await mongo.connect()
    return mongo
