import aiohttp
import asyncio
import feedparser
import time
import json
from typing import List, Set
from loguru import logger

class NewsMonitor:
    """
    雷达模块 v5: 增加直接API抓取 + 统计功能
    """
    def __init__(self):
        self.seen_urls: Set[str] = set()
        self.stats = {
            'total_scanned': 0,
            'new_urls': 0,
            'rss_success': 0,
            'rss_failed': 0
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # ===== 新增: 直接API源 ===== 
        # 这些返回JSON,不经过RSS, 直接作为URL交给Crawler的JSON解析器处理
        self.api_sources = [
            # 东方财富快讯 (每次返回50条)
            "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html",
            
            # 新浪财经7x24 (可调整page_size)
            "https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size=30&zhibo_id=152",
        ]

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
                
                if new_links:
                    self.stats['rss_success'] += 1
                        
        except Exception as e:
            self.stats['rss_failed'] += 1
            # RSS 偶尔连接超时很正常，不用 print stack trace，太吵
            logger.warning(f"RSS Feed requires check: {url} | {str(e)[:50]}")
        
        return new_links

    async def scan_api_endpoint(self, session: aiohttp.ClientSession, api_url: str) -> List[str]:
        """
        扫描返回JSON的API接口
        返回的不是URL列表,而是直接把API地址加入队列
        (因为这些API本身就是数据源)
        """
        try:
            async with session.get(api_url, headers=self.headers, timeout=10) as resp:
                if resp.status == 200:
                    # 对于API URL，我们不根据内容去重（因为内容会变），而是总是允许它被处理
                    # 但是为了防止 pipeline 过于拥堵，可以做一个简单的频率限制或 hash check (这里简化处理，总是返回)
                    # 实际上，如果 API URL 本身不变，seen_urls 机制会拦截它。
                    # 所以这里有一个特殊逻辑：API URL 应该被视为“生成器”，而不是“文章”。
                    # 但是 FinNewsPipeline 的设计是 URL -> Process。
                    # 为了让 Crawler 每次都去抓新的 JSON，我们需要让 Monitor 每次都把这个 API URL 抛出去吗？
                    # 不，如果 seen_urls 记录了 api_url，下次就不抓了。
                    # **修正**: API URL 不应该加入 seen_urls，或者每次加一个时间戳参数让它不同。
                    
                    # 策略：Monitor 返回 API URL，Crawler 解析出 NewsItems。
                    # 我们需要确保 Monitor 每次都能把 API URL 报上去。
                    return [api_url] 
        except Exception as e:
            logger.debug(f"API scan skip: {api_url[:40]}... ({str(e)[:20]})")
        
        return []

    async def harvest(self) -> List[str]:
        """
        全火力扫描 + 统计报告
        """
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            # 1. 启动 API 任务 (直接把 API URL 交给 Crawler 处理)
            for api_url in self.api_sources:
                tasks.append(self.scan_api_endpoint(session, api_url))
            
            # 2. 启动所有 RSS 任务
            for rss_url in self.rss_sources:
                tasks.append(self.scan_rss_feed(rss_url))
            
            # 3. 并发等待
            results = await asyncio.gather(*tasks)
            
            # 4. 展平结果
            all_urls = [u for sub in results for u in sub]
            
            # 统计
            self.stats['total_scanned'] += 1
            self.stats['new_urls'] += len(all_urls)
            
            # 每10次扫描打印统计
            if self.stats['total_scanned'] % 10 == 0:
                logger.info(
                    f"📊 Scan Stats: "
                    f"Total={self.stats['total_scanned']} | "
                    f"NewURLs={self.stats['new_urls']} | "
                    f"RSS_OK={self.stats['rss_success']} | "
                    f"RSS_Fail={self.stats['rss_failed']}"
                )
            
            if all_urls:
                logger.info(f"📡 Detected {len(all_urls)} URLs this round")
            
            return all_urls