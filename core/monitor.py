import aiohttp
import asyncio
import feedparser
import time
import json
from typing import List, Set
from loguru import logger

class NewsMonitor:
    """
    雷达模块 v4 (Ultimate): RSS矩阵 + API直连
    """
    def __init__(self):
        self.seen_urls: Set[str] = set()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # === 核心资产：这是你要的“足够多的网站” ===
        # 这些是标准 RSS 链接，直接能用，无需插件
        self.rss_sources = [
            # 1. 21世纪经济报道 (最稳的宏观/金融源)
            "http://www.21jingji.com/rss/21jingji/finance.xml", 
            "http://www.21jingji.com/rss/21jingji/macro.xml",
            
            # 2. 财新网 (虽然有付费墙，但RSS能抓到摘要和链接，部分免费)
            "http://ma.caixin.com/rss/finance.xml",
            
            # 3. 虎嗅 (科技与商业，质量很高)
            "https://www.huxiu.com/rss/0.xml",
            
            # 4. 36氪 (一级市场、TMT)
            "https://www.36kr.com/feed",
            
            # 5. FT中文网 (全球视野)
            "http://www.ftchinese.com/rss/news",
            "http://www.ftchinese.com/rss/markets",
            
            # 6. 界面新闻 (通过 RSS 抓比爬网页更稳)
            "https://a.jiemian.com/index.php?m=article&a=rss&cid=4", # 界面-证券
            
            # 7. 搜狐财经 (老牌，量大)
            "http://business.sohu.com/rss/scroll.xml",
            
            # 8. 联合早报-财经 (亚太视角)
            "https://www.zaobao.com.sg/finance/rss.xml",
            
            # 9. 智通财经 (港美股)
            "https://www.zhitongcaijing.com/rss.xml",
            
            # 10. 华尔街见闻 (注意：这是第三方维护的源，如果失效可以删掉)
            # 这种 rsshub 开头的如果本地没网可能连不上，你可以试一下
            "https://rsshub.app/wallstreetcn/news/global" 
        ]

    async def scan_rss_feed(self, url: str) -> List[str]:
        """
        通用 RSS 扫描器
        """
        new_links = []
        try:
            # feedparser 是同步 IO，为了不阻塞主循环，丢到线程池运行
            feed = await asyncio.to_thread(feedparser.parse, url)
            
            if hasattr(feed, 'entries'):
                for entry in feed.entries:
                    link = entry.link
                    # 简单过滤：只保留 http 开头的有效链接
                    if link and link.startswith('http') and link not in self.seen_urls:
                        new_links.append(link)
                        self.seen_urls.add(link)
                        
        except Exception as e:
            # RSS 偶尔连接超时很正常，不用 print stack trace，太吵
            logger.warning(f"RSS Feed requires check: {url} | {str(e)[:50]}")
        
        return new_links

    async def scan_sina_7x24(self, session: aiohttp.ClientSession) -> List[str]:
        # (保留你之前的代码，这是个好接口)
        ts = int(time.time() * 1000)
        api_url = f"https://zhibo.sina.com.cn/api/zhibo/feed?callback=&page=1&page_size=20&zhibo_id=152&tag_id=0&dire=f&dpc=1&type=0&_={ts}"
        new_links = []
        try:
            async with session.get(api_url, headers=self.headers, timeout=10) as resp:
                text = await resp.text()
                data = json.loads(text)
                items = data.get('result', {}).get('data', {}).get('feed', {}).get('list', [])
                for item in items:
                    url = item.get('docurl')
                    if url and url not in self.seen_urls:
                        new_links.append(url)
                        self.seen_urls.add(url)
        except Exception: pass
        return new_links

    async def scan_eastmoney_kuaixun(self, session: aiohttp.ClientSession) -> List[str]:
        # (保留你之前的代码)
        api_url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html"
        new_links = []
        try:
            async with session.get(api_url, headers=self.headers, timeout=10) as resp:
                text = await resp.text()
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

    async def harvest(self) -> List[str]:
        """
        全火力覆盖扫描
        """
        async with aiohttp.ClientSession() as session:
            # 1. 启动 API 任务
            tasks = [
                self.scan_sina_7x24(session),
                self.scan_eastmoney_kuaixun(session)
            ]
            
            # 2. 启动所有 RSS 任务
            for rss_url in self.rss_sources:
                tasks.append(self.scan_rss_feed(rss_url))
            
            # 3. 并发等待
            results = await asyncio.gather(*tasks)
            
            # 4. 展平结果
            all_urls = [u for sub in results for u in sub]
            
            # 调试打印
            if all_urls:
                logger.info(f"📡 Radar Detected {len(all_urls)} URLs from {len(self.rss_sources) + 2} sources.")
            
            return all_urls