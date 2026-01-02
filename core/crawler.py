import aiohttp
import asyncio
import json
from typing import Optional, List, Union
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from config.settings import settings
from core.schema import NewsPayload

class AsyncCrawler:
    """
    异步数据采集器 - 增强版
    支持HTML和JSON两种数据源
    """
    def __init__(self):
        self.semaphore = asyncio.Semaphore(settings.MAX_CRAWLER_CONCURRENCY)
        self.headers = {
            "User-Agent": "FinNewsMasterV1/1.0 (Quant Research; SJTU Physics)"
        }

    def _is_json_api(self, url: str) -> bool:
        """
        判断是否为JSON API (而非普通网页)
        """
        json_indicators = [
            'api.eastmoney.com',
            'newsapi.eastmoney.com',
            'zhibo.sina.com.cn/api',
            '/api/',
            'getlist',
            'ajaxResult'
        ]
        return any(indicator in url for indicator in json_indicators)

    async def fetch_json_api(self, session: aiohttp.ClientSession, url: str) -> List[NewsPayload]:
        """
        直接解析JSON API返回的快讯数据
        返回 NewsPayload 列表
        """
        news_list = []
        async with self.semaphore:
            try:
                # API 通常响应快，不需要太长 timeout
                async with session.get(url, headers=self.headers, timeout=15) as response:
                    response.raise_for_status()
                    text = await response.text()
                    
                    # 东方财富的数据可能包裹在 var ajaxResult={...} 中
                    if 'var ajaxResult=' in text:
                        json_str = text.split('var ajaxResult=')[1].strip()
                        if json_str.endswith(';'):
                            json_str = json_str[:-1]
                    else:
                        json_str = text
                    
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        # 尝试只截取 {} 部分
                        start = text.find('{')
                        end = text.rfind('}') + 1
                        if start != -1 and end != -1:
                            data = json.loads(text[start:end])
                        else:
                            raise

                    # 1. 解析东方财富快讯格式
                    if 'LivesList' in data:
                        items = data['LivesList']
                        for item in items:
                            payload = NewsPayload(
                                url=item.get('url_unique', url), # 如果没有独立URL，就用API URL作为占位，或者构造一个唯一ID
                                title=item.get('simtitle', item.get('title', 'Unknown')),
                                content=item.get('digest', item.get('simdigest', '')),
                                source='EastMoney_API'
                            )
                            news_list.append(payload)
                            
                    # 2. 解析新浪财经 7x24 格式
                    elif 'result' in data and 'data' in data['result']:
                         items = data['result']['data']['feed']['list']
                         for item in items:
                             payload = NewsPayload(
                                 url=item.get('docurl', url),
                                 title=item.get('rich_text', item.get('plain_text', 'Unknown'))[:50], # 新浪快讯往往没有标题，截取内容前段
                                 content=item.get('rich_text', item.get('plain_text', '')),
                                 source='Sina_API'
                             )
                             news_list.append(payload)

                    logger.info(f"📦 Parsed {len(news_list)} news items from JSON API: {url[:30]}...")
                    return news_list
                    
            except Exception as e:
                logger.error(f"JSON API parse error for {url}: {e}")
                return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(aiohttp.ClientError)
    )
    async def fetch_jina_markdown(self, session: aiohttp.ClientSession, url: str) -> str:
        target_url = f"{settings.JINA_READER_BASE}{url}"
        async with self.semaphore:
            # 修改点：timeout 从 15 改成 30
            async with session.get(target_url, headers=self.headers, timeout=30) as response:
                response.raise_for_status()
                return await response.text()

    async def process_url(self, url: str) -> Union[NewsPayload, List[NewsPayload], None]:
        """
        单一 URL 处理流程 - 自动识别JSON/HTML
        """
        async with aiohttp.ClientSession() as session:
            try:
                # 1. 如果是JSON API,直接解析
                if self._is_json_api(url):
                    logger.info(f"🔍 Detected JSON API: {url[:50]}...")
                    return await self.fetch_json_api(session, url)

                # 2. 否则走Jina Reader (普通网页)
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
