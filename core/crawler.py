import aiohttp
import asyncio
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from config.settings import settings
from core.schema import NewsPayload

class AsyncCrawler:
    """
    异步数据采集器 (利用 i9 处理网络 I/O)
    """
    def __init__(self):
        # 信号量控制并发数，防止触发对方反爬
        self.semaphore = asyncio.Semaphore(settings.MAX_CRAWLER_CONCURRENCY)
        self.headers = {
            "User-Agent": "FinNewsMasterV1/1.0 (Quant Research; SJTU Physics)"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(aiohttp.ClientError)
    )
    async def fetch_jina_markdown(self, session: aiohttp.ClientSession, url: str) -> str:
        """
        通过 Jina Reader 获取清洗后的 Markdown
        """
        target_url = f"{settings.JINA_READER_BASE}{url}"
        async with self.semaphore:
            async with session.get(target_url, headers=self.headers, timeout=15) as response:
                response.raise_for_status()
                return await response.text()

    async def process_url(self, url: str) -> Optional[NewsPayload]:
        """
        单一 URL 处理流程
        """
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Downloading signal: {url}")
                content = await self.fetch_jina_markdown(session, url)
                
                # 简单提取标题 (Jina 返回的 Markdown 第一行通常是标题)
                lines = content.split('\n')
                title = lines[0].strip('# ').strip() if lines else "Unknown Title"
                
                return NewsPayload(
                    url=url,
                    title=title,
                    content=content
                )
            except Exception as e:
                logger.error(f"Signal Loss for {url}: {e}")
                return None
