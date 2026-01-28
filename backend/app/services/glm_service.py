"""
智谱GLM服务模块
"""
import httpx
from typing import List, Dict, Any, Optional
from ..config import settings
from loguru import logger


class GLMService:
    """智谱GLM API服务"""

    def __init__(self):
        self.api_key = settings.GLM_API_KEY
        self.base_url = settings.GLM_BASE_URL
        self.model = settings.GLM_MODEL
        self.embedding_model = settings.GLM_EMBEDDING_MODEL

    async def _call_api(
        self,
        endpoint: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """调用GLM API"""
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"GLM API调用失败: {e}")
                raise

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        model: Optional[str] = None,
    ) -> str:
        """
        对话接口

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大token数
            model: 模型名称

        Returns:
            AI回复内容
        """
        data = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            result = await self._call_api("chat/completions", data)

            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"GLM响应格式异常: {result}")
                return "抱歉，AI服务暂时不可用。"

        except Exception as e:
            logger.error(f"GLM聊天失败: {e}")
            return f"AI服务出错: {str(e)}"

    async def embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> List[float]:
        """
        文本向量化

        Args:
            text: 输入文本
            model: 模型名称

        Returns:
            向量列表
        """
        data = {
            "model": model or self.embedding_model,
            "input": text,
        }

        try:
            result = await self._call_api("embeddings", data)

            if "data" in result and len(result["data"]) > 0:
                return result["data"][0]["embedding"]
            else:
                logger.error(f"GLM Embedding响应格式异常: {result}")
                return []

        except Exception as e:
            logger.error(f"GLM向量化失败: {e}")
            return []

    async def batch_embedding(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """
        批量文本向量化

        Args:
            texts: 文本列表
            model: 模型名称

        Returns:
            向量列表
        """
        data = {
            "model": model or self.embedding_model,
            "input": texts,
        }

        try:
            result = await self._call_api("embeddings", data)

            if "data" in result:
                # 按原始顺序排序
                embeddings = [item["embedding"] for item in result["data"]]
                return embeddings
            else:
                logger.error(f"GLM批量Embedding响应格式异常: {result}")
                return []

        except Exception as e:
            logger.error(f"GLM批量向量化失败: {e}")
            return []


# 全局实例
glm_service = GLMService()


async def get_glm_service():
    """依赖注入：获取GLM服务"""
    return glm_service
