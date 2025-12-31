import aiohttp
import asyncio
import time
import json
from typing import List, Set
from loguru import logger

class NewsMonitor:
    """
    雷达模块 v3 (Pro): 聚合新浪、东财、界面
    """
    def __init__(self):
        self.seen_urls: Set[str] = set()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://finance.sina.com.cn/"
        }

    async def scan_sina_7x24(self, session: aiohttp.ClientSession) -> List[str]:
        """
        新浪财经 7x24 (A股信息密度最高的地方)
        """
        # 新浪的 API 时间戳参数
        ts = int(time.time() * 1000)
        api_url = f"https://zhibo.sina.com.cn/api/zhibo/feed?callback=&page=1&page_size=20&zhibo_id=152&tag_id=0&dire=f&dpc=1&type=0&_={ts}"
        new_links = []
        try:
            async with session.get(api_url, headers=self.headers, timeout=10) as resp:
                text = await resp.text()
                data = json.loads(text)
                items = data.get('result', {}).get('data', {}).get('feed', {}).get('list', [])
                
                for item in items:
                    # 新浪快讯往往没有独立 URL，只有 docurl
                    url = item.get('docurl')
                    # 如果没有 docurl，我们构造一个伪 ID URL 防止重复处理
                    if not url and item.get('id'):
                        # 对于纯快讯（无文章），我们可以构造一个 text payload 传给下游
                        # 但为了保持架构统一，我们这里暂时只取有详情页的
                        pass 
                    
                    if url and url not in self.seen_urls:
                        new_links.append(url)
                        self.seen_urls.add(url)
        except Exception as e:
            logger.error(f"Sina Scan Error: {e}")
        return new_links

    async def scan_eastmoney_kuaixun(self, session: aiohttp.ClientSession) -> List[str]:
        """
        东方财富 7x24
        """
        api_url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html"
        new_links = []
        try:
            async with session.get(api_url, headers=self.headers, timeout=10) as resp:
                text = await resp.text()
                # 暴力解析 var ajaxResult = {...}
                try:
                    json_str = text[text.find('{'):text.rfind('}')+1]
                    data = json.loads(json_str)
                    for item in data.get('LivesList', []):
                        url = item.get('url_unique')
                        if url and url not in self.seen_urls:
                            new_links.append(url)
                            self.seen_urls.add(url)
                except: pass
        except Exception: pass
        return new_links

    async def scan_jiemian(self, session: aiohttp.ClientSession) -> List[str]:
        """
        界面新闻 (深度报道)
        """
        # ... (保持之前的逻辑，略，请保留原本的 BeautifulSoup 代码) ...
        # 这里为了节省篇幅，假设你保留了之前的 scan_jiemian 代码
        return [] 

    async def harvest(self) -> List[str]:
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.scan_sina_7x24(session),
                self.scan_eastmoney_kuaixun(session),
                # self.scan_jiemian(session) # 记得加上这个
            ]
            results = await asyncio.gather(*tasks)
            all_urls = [u for sub in results for u in sub]
            
            # 去重过滤
            valid_urls = [u for u in all_urls if u.startswith("http")]
            
            if valid_urls:
                logger.info(f"📡 Radar V3 detected {len(valid_urls)} signals.")
            return valid_urls